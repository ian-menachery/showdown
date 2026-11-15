"""The heads-up preflop model above 20 bb (SCOPE A7, DECISIONS 33 and 34).

Blinds are 0.5 and 1 bb, with no ante. S is the effective stack before the
blinds. Hands are bucketed into the 169 classes, dealt as class pairs weighted
by their non-conflicting combo counts, as in `games/pushfold.py`.

    SB first in:      fold | raise to 2.5 | all-in
    BB vs the raise:  fold | call | 3-bet to 7.5 | all-in
    SB vs the 3-bet:  fold | call | all-in
    any player vs an all-in: fold | call

Payoffs to the SB, in bb:
- a fold loses what the folder put in;
- a called all-in nets S(2E − 1), with E the exact all-in equity of the pair;
- a called raise or 3-bet sees a flop that is not played. With c bb in from
  each player, the SB nets c(2·share − 1), with share = 1 − R_oop·(1 − E).
  The BB is out of position after the flop, so it realizes R_oop of its
  equity, and what it forfeits goes to the SB.

The model's postflop line is an assumption (R), not a solved game, so its
charts are labelled "model chart" (DECISIONS 33).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from showdown.equity.cards import CLASS_NAMES
from showdown.equity.matrix import PreflopMatrix
from showdown.games.base import CHANCE, TERMINAL

FOLD, CALL, RAISE, JAM = 0, 1, 2, 3
ACTION_NAMES = ("fold", "call", "raise", "all-in")
CODE = "fcrj"
OPEN_TO = 2.5
THREEBET_TO = 3 * OPEN_TO

ACTIONS: dict[tuple[int, ...], tuple[int, ...]] = {
    (): (FOLD, RAISE, JAM),
    (RAISE,): (FOLD, CALL, RAISE, JAM),
    (RAISE, RAISE): (FOLD, CALL, JAM),
    (RAISE, RAISE, JAM): (FOLD, CALL),
    (RAISE, JAM): (FOLD, CALL),
    (JAM,): (FOLD, CALL),
}
NODES: dict[str, str] = {
    "": "SB first in",
    "r": "BB vs the 2.5 bb raise",
    "rr": "SB vs the 3-bet",
    "rrj": "BB vs the SB's 4-bet jam",
    "rj": "SB vs the BB's jam",
    "j": "BB vs the SB's first-in jam",
}
"""Decision nodes by history code (f c r j), with the player to act implied by its length."""


def history_code(history: tuple[int, ...]) -> str:
    return "".join(CODE[a] for a in history)


@dataclass(frozen=True, eq=False)
class _Table:
    raises: bool
    allin: np.ndarray
    flop_open: np.ndarray
    flop_3bet: np.ndarray
    outcomes: tuple[tuple[int, float], ...]


@dataclass(frozen=True)
class PreflopState:
    table: _Table
    deal: int = -1
    history: tuple[int, ...] = ()

    def current_player(self) -> int:
        if self.deal < 0:
            return CHANCE
        if self.history and self.history[-1] in (FOLD, CALL):
            return TERMINAL
        return len(self.history) % 2

    def legal_actions(self) -> tuple[int, ...]:
        if not self.history and not self.table.raises:
            return (FOLD, JAM)
        return ACTIONS[self.history]

    def chance_outcomes(self) -> tuple[tuple[int, float], ...]:
        return self.table.outcomes

    def child(self, action: int) -> PreflopState:
        if self.deal < 0:
            return PreflopState(self.table, action)
        return PreflopState(self.table, self.deal, self.history + (action,))

    def returns(self) -> tuple[float, float]:
        h, t = self.history, self.table
        ij = divmod(self.deal, 169)
        if h[-1] == FOLD:
            u = {
                (FOLD,): -0.5,
                (RAISE, FOLD): 1.0,
                (JAM, FOLD): 1.0,
                (RAISE, RAISE, FOLD): -OPEN_TO,
                (RAISE, JAM, FOLD): -OPEN_TO,
                (RAISE, RAISE, JAM, FOLD): THREEBET_TO,
            }[h]
        elif h == (RAISE, CALL):
            u = float(t.flop_open[ij])
        elif h == (RAISE, RAISE, CALL):
            u = float(t.flop_3bet[ij])
        else:  # a called all-in
            u = float(t.allin[ij])
        return (u, -u)

    def information_state(self) -> str:
        sb, bb = divmod(self.deal, 169)
        player = len(self.history) % 2
        name = CLASS_NAMES[sb] if player == 0 else CLASS_NAMES[bb]
        return f"{('SB', 'BB')[player]}:{name}:{history_code(self.history)}"


class PreflopGame:
    """The preflop model at `stack` bb, with the BB realizing `r_oop` of its equity postflop."""

    name = "preflop-model"

    def __init__(
        self, stack: float, matrix: PreflopMatrix, *, r_oop: float = 0.9, raises: bool = True
    ) -> None:
        if raises and stack <= THREEBET_TO:
            raise ValueError(f"the 3-bet to {THREEBET_TO} bb needs a stack above it")
        if not 0 < r_oop <= 1:
            raise ValueError("r_oop must be in (0, 1]")
        weights = matrix.pair_counts.astype(np.int64)
        total = int(weights.sum())
        outcomes = tuple(
            (169 * i + j, int(weights[i, j]) / total) for i in range(169) for j in range(169)
        )
        e = matrix.equity
        share = 1.0 - r_oop * (1.0 - e)
        self.stack, self.r_oop, self.raises = float(stack), float(r_oop), raises
        self._table = _Table(
            raises=raises,
            allin=self.stack * (2 * e - 1),
            flop_open=OPEN_TO * (2 * share - 1),
            flop_3bet=THREEBET_TO * (2 * share - 1),
            outcomes=outcomes,
        )

    def initial_state(self) -> PreflopState:
        return PreflopState(self._table)

    def action_name(self, action: int) -> str:
        return ACTION_NAMES[action]
