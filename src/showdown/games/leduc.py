"""Leduc hold'em.

Six cards: J, Q and K in two suits. Each player antes 1 and gets one private
card. Round 1 is a betting round, then one public card is dealt, then round 2.
Bets are fixed: a raise is 2 in round 1 and 4 in round 2, with at most two
raises per round. Player 0 acts first in both rounds. At showdown, a private
card that pairs the public card wins; otherwise the higher rank wins; equal
ranks split.

The encoding matches OpenSpiel's `leduc_poker` (default parameters) so the two
trees can be walked in lockstep in tests:

- cards are 0 to 5, with rank = card // 2;
- private cards are dealt to player 0, then player 1;
- actions are 0 = fold, 1 = call (or check), 2 = raise (or bet);
- fold is legal only when facing a bet.

Information-set keys keep the suit of every card, as OpenSpiel's do. That gives
936 infosets. Suit isomorphism would merge them, but the partition would no
longer match OpenSpiel's (DECISIONS 6).
"""

from __future__ import annotations

from dataclasses import dataclass

from showdown.games.base import CHANCE, TERMINAL

FOLD, CALL, RAISE = 0, 1, 2
ANTE = 1
RAISE_SIZE = (2, 4)
MAX_RAISES = 2
DECK = tuple(range(6))
_LETTER = "fcr"


def card_name(card: int) -> str:
    return "JQK"[card // 2] + "sh"[card % 2]


@dataclass(frozen=True)
class LeducState:
    private: tuple[int, ...] = ()
    public: int | None = None
    round: int = 0
    history: tuple[str, str] = ("", "")
    contrib: tuple[int, int] = (ANTE, ANTE)
    raises: int = 0
    to_act: int = 0
    folded: int | None = None
    showdown: bool = False

    def current_player(self) -> int:
        if self.folded is not None or self.showdown:
            return TERMINAL
        if len(self.private) < 2:
            return CHANCE
        if self.round == 1 and self.public is None:
            return CHANCE
        return self.to_act

    def legal_actions(self) -> tuple[int, ...]:
        facing_bet = self.contrib[self.to_act] < self.contrib[1 - self.to_act]
        actions = (FOLD, CALL) if facing_bet else (CALL,)
        return actions + (RAISE,) if self.raises < MAX_RAISES else actions

    def chance_outcomes(self) -> list[tuple[int, float]]:
        dealt = set(self.private)
        remaining = [c for c in DECK if c not in dealt]
        return [(c, 1.0 / len(remaining)) for c in remaining]

    def child(self, action: int) -> LeducState:
        if len(self.private) < 2:
            return _replace(self, private=self.private + (action,))
        if self.round == 1 and self.public is None:
            return _replace(self, public=action)

        player, other = self.to_act, 1 - self.to_act
        history = list(self.history)
        history[self.round] += _LETTER[action]
        history_t = (history[0], history[1])
        if action == FOLD:
            return _replace(self, history=history_t, folded=player)

        contrib = list(self.contrib)
        if action == RAISE:
            contrib[player] = contrib[other] + RAISE_SIZE[self.round]
            return _replace(
                self,
                history=history_t,
                contrib=(contrib[0], contrib[1]),
                raises=self.raises + 1,
                to_act=other,
            )

        contrib[player] = contrib[other]
        contrib_t = (contrib[0], contrib[1])
        if len(history[self.round]) < 2:  # an opening check; the round goes on
            return _replace(self, history=history_t, contrib=contrib_t, to_act=other)
        if self.round == 1:
            return _replace(self, history=history_t, contrib=contrib_t, showdown=True)
        return _replace(self, history=history_t, contrib=contrib_t, round=1, raises=0, to_act=0)

    def returns(self) -> tuple[float, float]:
        if self.folded is not None:
            lost = float(self.contrib[self.folded])
            return (-lost, lost) if self.folded == 0 else (lost, -lost)
        winner = _winner(self.private[0], self.private[1], self.public)
        if winner is None:
            return (0.0, 0.0)
        stake = float(self.contrib[0])
        return (stake, -stake) if winner == 0 else (-stake, stake)

    def information_state(self) -> str:
        own = card_name(self.private[self.to_act])
        if self.public is None:
            return f"{own}:{self.history[0]}"
        return f"{own}{card_name(self.public)}:{self.history[0]}/{self.history[1]}"


def _winner(card0: int, card1: int, public: int | None) -> int | None:
    rank0, rank1, board = card0 // 2, card1 // 2, public // 2
    pair0, pair1 = rank0 == board, rank1 == board
    if pair0 != pair1:
        return 0 if pair0 else 1
    if rank0 == rank1:
        return None
    return 0 if rank0 > rank1 else 1


def _replace(state: LeducState, **changes) -> LeducState:
    fields = {
        "private": state.private,
        "public": state.public,
        "round": state.round,
        "history": state.history,
        "contrib": state.contrib,
        "raises": state.raises,
        "to_act": state.to_act,
        "folded": state.folded,
        "showdown": state.showdown,
    }
    fields.update(changes)
    return LeducState(**fields)


class LeducPoker:
    name = "leduc"

    def initial_state(self) -> LeducState:
        return LeducState()

    def action_name(self, action: int) -> str:
        return ("fold", "call", "raise")[action]
