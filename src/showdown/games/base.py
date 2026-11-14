"""The game interface that every solver in showdown works against.

A game is a tree of states. Each state is a chance node, a decision node for
player 0 or 1, or a terminal. The solvers never look inside a state: they call
these methods once, through `showdown.cfr.tree.compile_game`, and work on the
compiled arrays from then on.

Only two-player zero-sum games are supported (SCOPE: three or more players are
out of scope). `compile_game` checks the zero-sum property at every terminal.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

CHANCE = -1
TERMINAL = -2


class State(Protocol):
    """One node of a game tree. Implementations are immutable."""

    def current_player(self) -> int:
        """0 or 1 at a decision node, otherwise `CHANCE` or `TERMINAL`."""
        ...

    def legal_actions(self) -> Sequence[int]:
        """Actions at a decision node, in ascending order."""
        ...

    def chance_outcomes(self) -> Sequence[tuple[int, float]]:
        """(outcome, probability) pairs at a chance node; probabilities sum to 1."""
        ...

    def child(self, action: int) -> State:
        """The state after `action` (a decision or a chance outcome)."""
        ...

    def returns(self) -> tuple[float, float]:
        """Terminal payoffs to players 0 and 1."""
        ...

    def information_state(self) -> str:
        """Key of the acting player's information set at a decision node.

        Two decision nodes of the same player share a key exactly when that
        player cannot tell them apart.
        """
        ...


class Game(Protocol):
    """A two-player zero-sum extensive-form game."""

    name: str

    def initial_state(self) -> State: ...

    def action_name(self, action: int) -> str: ...
