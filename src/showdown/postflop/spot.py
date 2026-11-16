"""A heads-up flop spot for the solver, with the preflop model's ranges (DECISIONS 35, 40).

Postflop the BB is out of position (player 0) and the SB in position (player 1).
Chips are 0.1 bb so that bet sizes round finely.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass

from showdown import preflop_model as pm
from showdown.equity.cards import CLASS_NAMES, cards_str, parse_cards
from showdown.equity.matrix import PreflopMatrix
from showdown.games.preflop import OPEN_TO, THREEBET_TO

CHIPS_PER_BB = 10
REACH_MIN = 0.001
"""The same reach rule as the advisor (DECISIONS 35)."""
PUT_IN = {"srp": OPEN_TO, "3bp": THREEBET_TO}
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
def _model() -> tuple[pm.PreflopModel, PreflopMatrix]:
    return pm.PreflopModel.load(), PreflopMatrix.load(pm.DEFAULT_MATRIX)


def model_range(depth: float, pot_type: str, seat: str) -> str:
    """One seat's weighted range along the pot's preflop line, in the solver's syntax."""
    sb, bb = _model()[0].at(depth).line_factors(LINES[pot_type])
    weights = sb if seat == "sb" else bb
    parts = []
    for name, w in zip(CLASS_NAMES, weights, strict=True):
        if w >= 0.0005:
            parts.append(name if w >= 0.99995 else f"{name}:{w:.4f}")
    return ",".join(parts)


@dataclass(frozen=True)
class FlopSpot:
    pot_type: str
    stack_bb: float
    """The effective stack before the blinds."""
    flop: str
    depth: float
    """The model depth whose ranges are used."""

    @classmethod
    def make(cls, pot_type: str, stack_bb: float, flop: str) -> FlopSpot:
        if pot_type not in PUT_IN:
            raise SpotError("pot type must be srp or 3bp")
        if stack_bb <= PUT_IN[pot_type]:
            raise SpotError(f"a {pot_type} needs a stack above {PUT_IN[pot_type]:g} bb")
        cards = parse_cards(flop)
        if len(cards) != 3 or len(set(cards)) != 3:
            raise SpotError("the flop is three different cards, e.g. Kc7d6c")
        depth = pm.PreflopModel.depth_for(stack_bb) or pm.GRID[0]
        model, matrix = _model()
        if model.at(depth).reach(LINES[pot_type], matrix.pair_counts) < REACH_MIN:
            raise SpotError(f"the preflop model almost never reaches a {pot_type} at {depth:g} bb")
        return cls(pot_type, float(stack_bb), cards_str(cards), depth)

    @property
    def pot_chips(self) -> int:
        return round(2 * PUT_IN[self.pot_type] * CHIPS_PER_BB)

    @property
    def stack_chips(self) -> int:
        return round((self.stack_bb - PUT_IN[self.pot_type]) * CHIPS_PER_BB)

    def spec(self, *, locks: list[dict] = (), report: list[list[str]] = ()) -> dict:
        return {
            "oop_range": model_range(self.depth, self.pot_type, "bb"),
            "ip_range": model_range(self.depth, self.pot_type, "sb"),
            "flop": self.flop,
            "starting_pot": self.pot_chips,
            "effective_stack": self.stack_chips,
            **TREE_T1,
            **SETTINGS,
            "locks": list(locks),
            "report": [list(p) for p in report],
        }
