"""One heads-up push/fold hand on pokerkit's NLHE state machine (DECISIONS 24).

In pokerkit's heads-up state, player 0 is the big blind and player 1 is the
small blind (button), who acts first preflop. Chips are integers scaled ×2:
blinds (1, 2), stacks 2S, so a payoff in chips divided by 2 is in bb. Every
card comes from our own deal; pokerkit's dealing and burning automations are
off, so its global shuffle never runs.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from pokerkit import Automation, NoLimitTexasHoldem

from showdown.equity.cards import card_str, class_of, make_combo

BB_SEAT, SB_SEAT = 0, 1
CHIPS_PER_BB = 2
AUTOMATIONS = (
    Automation.ANTE_POSTING,
    Automation.BET_COLLECTION,
    Automation.BLIND_OR_STRADDLE_POSTING,
    Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
    Automation.HAND_KILLING,
    Automation.CHIPS_PUSHING,
    Automation.CHIPS_PULLING,
)


def deal_cards(rng: random.Random) -> list[int]:
    """Nine distinct card ids: SB's two, BB's two, then the five board cards."""
    return rng.sample(range(52), 9)


@dataclass
class HandResult:
    stack: int
    sb_cards: tuple[int, int]
    bb_cards: tuple[int, int]
    board: tuple[int, ...]
    """Empty when someone folded."""
    sb_jammed: bool
    bb_called: bool | None
    """None when the BB had no decision (the SB folded, or the BB was all-in from its blind)."""
    sb_net: float
    """The SB's result in bb; the BB's is the negation."""


class PushFoldHand:
    """Drive one hand: the SB jams or folds, then the BB calls or folds."""

    def __init__(self, stack: int, cards: Sequence[int]) -> None:
        if stack < 1 or len(cards) != 9 or len(set(cards)) != 9:
            raise ValueError("need a stack of at least 1 bb and nine distinct cards")
        self.stack = int(stack)
        self.cards = list(cards)
        chips = CHIPS_PER_BB * self.stack
        self.state = NoLimitTexasHoldem.create_state(
            AUTOMATIONS, True, 0, (1, 2), 2, (chips, chips), 2
        )
        self.state.deal_hole(self._text(self.bb_cards), BB_SEAT)
        self.state.deal_hole(self._text(self.sb_cards), SB_SEAT)
        self.sb_jammed: bool | None = None
        self.bb_called: bool | None = None

    @staticmethod
    def _text(cards: Sequence[int]) -> str:
        return "".join(card_str(c) for c in cards)

    @property
    def sb_cards(self) -> tuple[int, int]:
        return (self.cards[0], self.cards[1])

    @property
    def bb_cards(self) -> tuple[int, int]:
        return (self.cards[2], self.cards[3])

    @property
    def sb_class(self) -> int:
        return class_of(make_combo(*self.sb_cards))

    @property
    def bb_class(self) -> int:
        return class_of(make_combo(*self.bb_cards))

    @property
    def to_act(self) -> str | None:
        """ "sb", "bb" or None when the hand needs no more decisions."""
        actor = self.state.actor_index
        if actor is None:
            return None
        return "sb" if actor == SB_SEAT else "bb"

    def sb_act(self, jam: bool) -> None:
        if self.to_act != "sb":
            raise ValueError("it is not the small blind's turn")
        self.sb_jammed = jam
        if not jam:
            self.state.fold()
        elif self.state.can_complete_bet_or_raise_to():
            self.state.complete_bet_or_raise_to(
                self.state.max_completion_betting_or_raising_to_amount
            )
        else:  # at 1 bb the BB is all-in from its blind, so the jam is a call
            self.state.check_or_call()

    def bb_act(self, call: bool) -> None:
        if self.to_act != "bb":
            raise ValueError("it is not the big blind's turn")
        self.bb_called = call
        if call:
            self.state.check_or_call()
        else:
            self.state.fold()

    def finish(self) -> HandResult:
        """Deal any remaining board cards and return the result."""
        if self.to_act is not None:
            raise ValueError("the hand still needs a decision")
        board = self.cards[4:]
        dealt = 0
        while self.state.status:
            if self.state.can_burn_card():
                self.state.burn_card("??")
            elif self.state.can_deal_board():
                count = 3 if dealt == 0 else 1
                self.state.deal_board(self._text(board[dealt : dealt + count]))
                dealt += count
            else:  # pragma: no cover - pokerkit always resolves an all-in hand
                raise RuntimeError("pokerkit stopped before the hand finished")
        payoffs = self.state.payoffs
        return HandResult(
            stack=self.stack,
            sb_cards=self.sb_cards,
            bb_cards=self.bb_cards,
            board=tuple(board[:dealt]),
            sb_jammed=bool(self.sb_jammed),
            bb_called=self.bb_called,
            sb_net=payoffs[SB_SEAT] / CHIPS_PER_BB,
        )
