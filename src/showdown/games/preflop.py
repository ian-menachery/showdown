"""The heads-up preflop model above 20 bb (SCOPE A7, A10; DECISIONS 33, 34, 49).

Blinds are 0.5 and 1 bb, with no ante. S is the effective stack before the
blinds. Hands are bucketed into the 169 classes, dealt as class pairs weighted
by their non-conflicting combo counts, as in `games/pushfold.py`.

DECISIONS 34's tree (`r_oop`, one R for every pot):

    SB first in:      fold | raise to 2.5 | all-in
    BB vs the raise:  fold | call | 3-bet to 7.5 | all-in
    SB vs the 3-bet:  fold | call | all-in
    any player vs an all-in: fold | call

DECISIONS 49's tree (`r`, an R per pot) adds a second 3-bet size:

    BB vs the raise:  fold | call | 3-bet to 7.5 | 3-bet to 10 | all-in
    SB vs either 3-bet: fold | call | all-in

Payoffs to the SB, in bb:
- a fold loses what the folder put in;
- a called all-in nets S(2E − 1), with E the exact all-in equity of the pair;
- a called raise or 3-bet sees a flop that is not played. With c bb in from
  each player, the SB nets c(2·share − 1), with share = 1 − R·(1 − E).
  The BB is out of position after the flop, so it realizes R of its equity,
  and what it forfeits goes to the SB. In DECISIONS 49's tree R is the pot's:
  the open (c = 2.5), the 3× 3-bet (7.5) or the 4× 3-bet (10).

The model's postflop line is an assumption (R), not a solved game, so its
charts are labelled "model chart" (DECISIONS 33).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from showdown.equity.cards import CLASS_NAMES
from showdown.equity.matrix import PreflopMatrix
from showdown.games.base import CHANCE, TERMINAL

FOLD, CALL, RAISE, JAM, RAISE_4X = 0, 1, 2, 3, 4
ACTION_NAMES = ("fold", "call", "raise", "all-in", "raise 4x")
CODE = "fcrj4"
OPEN_TO = 2.5
THREEBET_TO = 3 * OPEN_TO
THREEBET_4X_TO = 4 * OPEN_TO
POTS = {"open": OPEN_TO, "3x": THREEBET_TO, "4x": THREEBET_4X_TO}
"""DECISIONS 49's pots that see a flop, by the bb each player has put in."""

ACTIONS: dict[tuple[int, ...], tuple[int, ...]] = {
    (): (FOLD, RAISE, JAM),
    (RAISE,): (FOLD, CALL, RAISE, JAM),
    (RAISE, RAISE): (FOLD, CALL, JAM),
    (RAISE, RAISE, JAM): (FOLD, CALL),
    (RAISE, JAM): (FOLD, CALL),
    (JAM,): (FOLD, CALL),
}
ACTIONS_4X: dict[tuple[int, ...], tuple[int, ...]] = {
    **ACTIONS,
    (RAISE,): (FOLD, CALL, RAISE, RAISE_4X, JAM),
    (RAISE, RAISE_4X): (FOLD, CALL, JAM),
    (RAISE, RAISE_4X, JAM): (FOLD, CALL),
}
NODES: dict[str, str] = {
    "": "SB first in",
    "r": "BB vs the 2.5 bb raise",
    "rr": "SB vs the 3-bet",
    "rrj": "BB vs the SB's 4-bet jam",
    "rj": "SB vs the BB's jam",
    "j": "BB vs the SB's first-in jam",
}
"""Decision nodes by history code (f c r j 4), with the player to act implied by its length."""
NODES_4X: dict[str, str] = {
    **NODES,
    "rr": "SB vs the 3-bet to 7.5",
    "r4": "SB vs the 3-bet to 10",
    "rrj": "BB vs the SB's 4-bet jam over the 3-bet to 7.5",
    "r4j": "BB vs the SB's 4-bet jam over the 3-bet to 10",
}
FOLDS = {
    (FOLD,): -0.5,
    (RAISE, FOLD): 1.0,
    (JAM, FOLD): 1.0,
    (RAISE, RAISE, FOLD): -OPEN_TO,
    (RAISE, JAM, FOLD): -OPEN_TO,
    (RAISE, RAISE, JAM, FOLD): THREEBET_TO,
    (RAISE, RAISE_4X, FOLD): -OPEN_TO,
    (RAISE, RAISE_4X, JAM, FOLD): THREEBET_4X_TO,
}
FLOP_LINES = {(RAISE, CALL): "open", (RAISE, RAISE, CALL): "3x", (RAISE, RAISE_4X, CALL): "4x"}


def history_code(history: tuple[int, ...]) -> str:
    return "".join(CODE[a] for a in history)


@dataclass(frozen=True, eq=False)
class _Table:
    raises: bool
    actions: dict[tuple[int, ...], tuple[int, ...]]
    allin: np.ndarray
    flop: dict[tuple[int, ...], np.ndarray]
    """A called raise or 3-bet's line -> the SB's net per class pair."""
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
        return self.table.actions[self.history]

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
            u = FOLDS[h]
        elif h in t.flop:
            u = float(t.flop[h][ij])
        else:  # a called all-in
            u = float(t.allin[ij])
        return (u, -u)

    def information_state(self) -> str:
        sb, bb = divmod(self.deal, 169)
        player = len(self.history) % 2
        name = CLASS_NAMES[sb] if player == 0 else CLASS_NAMES[bb]
        return f"{('SB', 'BB')[player]}:{name}:{history_code(self.history)}"


class PreflopGame:
    """The preflop model at `stack` bb.

    With `r_oop`, DECISIONS 34's tree: the BB realizes `r_oop` of its equity in every pot.
    With `r`, DECISIONS 49's tree with the 4× 3-bet: R for each pot in `POTS`, any value
    in (0, 2), since an out-of-position 3-bettor can realize more than its equity.
    """

    name = "preflop-model"

    def __init__(
        self,
        stack: float,
        matrix: PreflopMatrix,
        *,
        r_oop: float = 0.9,
        raises: bool = True,
        r: dict[str, float] | None = None,
    ) -> None:
        if r is None:
            biggest, actions = THREEBET_TO, ACTIONS
            if not 0 < r_oop <= 1:
                raise ValueError("r_oop must be in (0, 1]")
            per_pot = {"open": r_oop, "3x": r_oop}
        else:
            biggest, actions = THREEBET_4X_TO, ACTIONS_4X
            if set(r) != set(POTS):
                raise ValueError(f"r needs one value for each pot: {', '.join(POTS)}")
            if not all(0 < v < 2 for v in r.values()):
                raise ValueError("every R must be in (0, 2)")
            per_pot = {p: float(r[p]) for p in POTS}
        if raises and stack <= biggest:
            raise ValueError(f"the 3-bet to {biggest:g} bb needs a stack above it")
        weights = matrix.pair_counts.astype(np.int64)
        total = int(weights.sum())
        outcomes = tuple(
            (169 * i + j, int(weights[i, j]) / total) for i in range(169) for j in range(169)
        )
        e = matrix.equity
        flop = {}
        for line, pot in FLOP_LINES.items():
            if pot in per_pot:
                share = 1.0 - per_pot[pot] * (1.0 - e)
                flop[line] = POTS[pot] * (2 * share - 1)
        self.stack, self.raises = float(stack), raises
        self.r_oop = None if r is not None else float(r_oop)
        self.r = None if r is None else per_pot
        self._table = _Table(
            raises=raises,
            actions=actions,
            allin=self.stack * (2 * e - 1),
            flop=flop,
            outcomes=outcomes,
        )

    def initial_state(self) -> PreflopState:
        return PreflopState(self._table)

    def action_name(self, action: int) -> str:
        return ACTION_NAMES[action]
