"""Kuhn poker.

Three cards (J, Q, K), one dealt to each player, ante 1. Player 0 passes or bets
1. After a pass, player 1 passes (showdown for 1) or bets 1, and player 0 then
folds or calls. After a bet, player 1 folds or calls (showdown for 2).

The encoding matches OpenSpiel's `kuhn_poker` so the two trees can be walked in
lockstep in tests: cards are 0, 1 and 2, dealt to player 0 and then player 1,
and actions are 0 = pass and 1 = bet.
"""

from __future__ import annotations

from dataclasses import dataclass

from showdown.games.base import CHANCE, TERMINAL

CARD_NAMES = "JQK"
PASS, BET = 0, 1
_LETTER = "pb"
_TERMINAL_HISTORIES = frozenset({"pp", "bp", "bb", "pbp", "pbb"})


@dataclass(frozen=True)
class KuhnState:
    cards: tuple[int, ...] = ()
    history: str = ""

    def current_player(self) -> int:
        if len(self.cards) < 2:
            return CHANCE
        if self.history in _TERMINAL_HISTORIES:
            return TERMINAL
        return len(self.history) % 2

    def legal_actions(self) -> tuple[int, ...]:
        return (PASS, BET)

    def chance_outcomes(self) -> list[tuple[int, float]]:
        remaining = [c for c in range(3) if c not in self.cards]
        return [(c, 1.0 / len(remaining)) for c in remaining]

    def child(self, action: int) -> KuhnState:
        if len(self.cards) < 2:
            return KuhnState(self.cards + (action,), self.history)
        return KuhnState(self.cards, self.history + _LETTER[action])

    def returns(self) -> tuple[float, float]:
        h = self.history
        if h == "bp":  # player 1 folds to a bet
            return (1.0, -1.0)
        if h == "pbp":  # player 0 folds to a bet
            return (-1.0, 1.0)
        stake = 2.0 if "b" in h else 1.0
        u0 = stake if self.cards[0] > self.cards[1] else -stake
        return (u0, -u0)

    def information_state(self) -> str:
        player = len(self.history) % 2
        return f"{CARD_NAMES[self.cards[player]]}:{self.history}"


class KuhnPoker:
    name = "kuhn"

    def initial_state(self) -> KuhnState:
        return KuhnState()

    def action_name(self, action: int) -> str:
        return ("pass", "bet")[action]
