"""Heads-up push/fold hold'em (DECISIONS 8 and 22).

Blinds are 0.5 and 1 bb, with no ante. S is the effective stack before the
blinds are posted. Chance deals a class pair (SB class i, BB class j) with
probability proportional to its number of non-conflicting combo pairs. The SB
folds, losing 0.5, or goes all-in. Facing the jam, the BB folds, losing its
1 bb blind, or calls. On a call, the SB nets S·(2E − 1), where E is the exact
all-in equity of class i against class j.

Each player's information set is their own hand class: "SB:AKs" or "BB:72o".
Action 0 is fold and action 1 is all-in (a jam for the SB, a call for the BB).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from showdown.equity.cards import CLASS_NAMES
from showdown.equity.matrix import PreflopMatrix
from showdown.games.base import CHANCE, TERMINAL

FOLD, ALL_IN = 0, 1
SB_FOLD = -0.5
"""SB's payoff when it folds."""
BB_FOLD = 1.0
"""SB's payoff when the BB folds to the jam."""


@dataclass(frozen=True, eq=False)
class _Table:
    """Per-game constants shared by every state."""

    stack: float
    showdown: np.ndarray
    """[i, j]: SB's net payoff on a call, S·(2E − 1)."""
    outcomes: tuple[tuple[int, float], ...]


@dataclass(frozen=True)
class PushFoldState:
    table: _Table
    deal: int = -1
    """169 · SB class + BB class, or -1 before the deal."""
    history: tuple[int, ...] = ()

    def current_player(self) -> int:
        if self.deal < 0:
            return CHANCE
        if self.history in ((FOLD,), (ALL_IN, FOLD), (ALL_IN, ALL_IN)):
            return TERMINAL
        return len(self.history)

    def legal_actions(self) -> tuple[int, ...]:
        return (FOLD, ALL_IN)

    def chance_outcomes(self) -> tuple[tuple[int, float], ...]:
        return self.table.outcomes

    def child(self, action: int) -> PushFoldState:
        if self.deal < 0:
            return PushFoldState(self.table, action)
        return PushFoldState(self.table, self.deal, self.history + (action,))

    def returns(self) -> tuple[float, float]:
        if self.history == (FOLD,):
            u = SB_FOLD
        elif self.history == (ALL_IN, FOLD):
            u = BB_FOLD
        else:
            u = float(self.table.showdown[divmod(self.deal, 169)])
        return (u, -u)

    def information_state(self) -> str:
        sb, bb = divmod(self.deal, 169)
        return f"SB:{CLASS_NAMES[sb]}" if not self.history else f"BB:{CLASS_NAMES[bb]}"


class PushFoldGame:
    """Push/fold at effective stack `stack` bb, with payoffs from `matrix`."""

    name = "pushfold"

    def __init__(self, stack: float, matrix: PreflopMatrix) -> None:
        if stack < 1:
            raise ValueError("the effective stack must be at least the 1 bb big blind")
        weights = matrix.pair_counts.astype(np.int64)
        total = int(weights.sum())
        outcomes = tuple(
            (169 * i + j, int(weights[i, j]) / total) for i in range(169) for j in range(169)
        )
        self.stack = float(stack)
        self.matrix = matrix
        self._table = _Table(self.stack, self.stack * (2 * matrix.equity - 1), outcomes)

    def initial_state(self) -> PushFoldState:
        return PushFoldState(self._table)

    def action_name(self, action: int) -> str:
        return ("fold", "all-in")[action]
