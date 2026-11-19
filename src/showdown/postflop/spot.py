"""A heads-up flop spot for the solver, with the preflop model's ranges (DECISIONS 35, 40, 49).

Postflop the BB is out of position (player 0) and the SB in position (player 1).
Chips are 0.1 bb so that bet sizes round finely.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path

from showdown import preflop_model as pm
from showdown.equity.cards import CLASS_NAMES, cards_str, parse_cards
from showdown.equity.matrix import PreflopMatrix
from showdown.games.preflop import OPEN_TO, POTS, THREEBET_TO

CHIPS_PER_BB = 10
REACH_MIN = 0.001
"""The same reach rule as the advisor (DECISIONS 35)."""
PUT_IN = {"srp": OPEN_TO, "3bp": THREEBET_TO}
"""Version 1's put-in per pot type; version 2's 3-bet pot uses its line's (`pot_line`)."""
LINES = {"srp": "rc", "3bp": "rrc"}
TREE_T1 = {
    "flop_bet": "33%, a",
    "flop_raise": "60%, a",
    "turn_bet": "66%, a",
    "turn_raise": "60%, a",
    "river_bet": "75%, a",
    "river_raise": "60%, a",
    "river_donk": "75%",
}
SETTINGS = {"target_pct": 2.0, "max_iterations": 1000, "compress_over_gb": 10.0}
SEAT_PLAYER = {"bb": 0, "sb": 1}
"""Postflop, the BB acts first (out of position)."""


class SpotError(ValueError):
    """A flop spot the solver cannot take as given."""


@functools.cache
def _model(path: str = pm.DEFAULT_MODEL) -> tuple[pm.PreflopModel, PreflopMatrix]:
    return pm.PreflopModel.load(path), PreflopMatrix.load(pm.ROOT / pm.DEFAULT_MATRIX)


def pot_line(
    depth: float, pot_type: str, model: str | Path = pm.DEFAULT_MODEL
) -> tuple[str, float]:
    """(the preflop line, the bb each player put in) for a pot type at a model depth.

    In version 2 a 3-bet pot takes the 3-bet size the BB makes more often at that
    depth (DECISIONS 49: the library's 3BP100).
    """
    found, matrix = _model(str(model))
    if pot_type == "3bp" and found.version == 2:
        size = found.at(depth).more_often_3bet(matrix.pair_counts)
        return pm.POT_LINES[size], POTS[size]
    return LINES[pot_type], PUT_IN[pot_type]


def range_text(weights) -> str:
    """Per-class weights in the solver's range syntax, to 4 decimals (DECISIONS 40)."""
    parts = []
    for name, w in zip(CLASS_NAMES, weights, strict=True):
        if w >= 0.0005:
            parts.append(name if w >= 0.99995 else f"{name}:{w:.4f}")
    return ",".join(parts)


def model_range(
    depth: float, pot_type: str, seat: str, model: str | Path = pm.DEFAULT_MODEL
) -> str:
    """One seat's weighted range along the pot's preflop line, in the solver's syntax."""
    line, _ = pot_line(depth, pot_type, model)
    sb, bb = _model(str(model))[0].at(depth).line_factors(line)
    return range_text(sb if seat == "sb" else bb)


@dataclass(frozen=True)
class FlopSpot:
    pot_type: str
    stack_bb: float
    """The effective stack before the blinds."""
    flop: str
    depth: float
    """The model depth whose ranges are used."""
    model: str = pm.DEFAULT_MODEL
    """The preflop model file the ranges come from."""
    put_in: float = OPEN_TO
    """What each player put in preflop, in bb."""

    @classmethod
    def make(
        cls, pot_type: str, stack_bb: float, flop: str, model: str | Path = pm.DEFAULT_MODEL
    ) -> FlopSpot:
        if pot_type not in PUT_IN:
            raise SpotError("pot type must be srp or 3bp")
        cards = parse_cards(flop)
        if len(cards) != 3 or len(set(cards)) != 3:
            raise SpotError("the flop is three different cards, e.g. Kc7d6c")
        depth = pm.PreflopModel.depth_for(stack_bb) or pm.GRID[0]
        line, put_in = pot_line(depth, pot_type, model)
        if stack_bb <= put_in:
            raise SpotError(f"a {pot_type} needs a stack above {put_in:g} bb")
        found, matrix = _model(str(model))
        if found.at(depth).reach(line, matrix.pair_counts) < REACH_MIN:
            raise SpotError(f"the preflop model almost never reaches a {pot_type} at {depth:g} bb")
        return cls(pot_type, float(stack_bb), cards_str(cards), depth, str(model), put_in)

    @property
    def pot_chips(self) -> int:
        return round(2 * self.put_in * CHIPS_PER_BB)

    @property
    def stack_chips(self) -> int:
        return round((self.stack_bb - self.put_in) * CHIPS_PER_BB)

    def spec(self, *, locks: list[dict] = (), report: list[list[str]] = ()) -> dict:
        return {
            "oop_range": model_range(self.depth, self.pot_type, "bb", self.model),
            "ip_range": model_range(self.depth, self.pot_type, "sb", self.model),
            "flop": self.flop,
            "starting_pot": self.pot_chips,
            "effective_stack": self.stack_chips,
            **TREE_T1,
            **SETTINGS,
            "locks": list(locks),
            "report": [list(p) for p in report],
        }
