"""Expected pot shares for all-in hands with any number of players and side pots (DECISIONS 26).

Given the hole cards of every player still in the hand, the board so far, and
the pots (each an amount and the seats eligible to win it), `pot_shares`
returns each seat's expected winnings over uniform runouts of the remaining
board. A pot is split equally among the best eligible hands.

The method:
- runouts are enumerated exactly when at most two board cards are still to
  come (at most 1,081 runouts);
- a heads-up hand with all five board cards to come is also exact, through
  `exact.hand_vs_hand`, with suit-isomorphic pairs sharing one enumeration;
- anything else (three or more players with five cards to come) is seeded
  Monte Carlo with a standard error per seat.

Cards that are not in a live hand or on the board stay in the deck, including
folded players' cards (DECISIONS 26). Only eval7's `evaluate` is used
(DECISIONS 5).
"""

from __future__ import annotations

import itertools
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from showdown.equity.evaluator import EVAL7_CARDS, evaluate_eval7
from showdown.equity.exact import canonical_pair, hand_vs_hand

Pot = tuple[float, tuple[int, ...]]
"""(amount, eligible seats)."""


@dataclass(frozen=True)
class Shares:
    expected: dict[int, float]
    """Seat -> expected winnings from all pots."""
    se: dict[int, float]
    """Seat -> standard error of `expected` (0 when exact)."""
    method: str
    """"exact" or "monte-carlo"."""
    runouts: int


def _rank_all(hands: Mapping[int, Sequence[int]], board: Sequence[int]) -> dict[int, int]:
    board_cards = [EVAL7_CARDS[c] for c in board]
    return {
        seat: evaluate_eval7([EVAL7_CARDS[c] for c in cards] + board_cards)
        for seat, cards in hands.items()
    }


def _winnings(ranks: Mapping[int, int], pots: Sequence[Pot]) -> dict[int, float]:
    out = dict.fromkeys(ranks, 0.0)
    for amount, eligible in pots:
        contenders = [s for s in eligible if s in ranks]
        if not contenders:
            continue
        best = max(ranks[s] for s in contenders)
        winners = [s for s in contenders if ranks[s] == best]
        for s in winners:
            out[s] += amount / len(winners)
    return out


def _check(hands: Mapping[int, Sequence[int]], board: Sequence[int], pots: Sequence[Pot]) -> None:
    cards = [c for h in hands.values() for c in h] + list(board)
    if len(set(cards)) != len(cards):
        raise ValueError("hands and board share a card")
    if len(board) > 5 or any(len(h) != 2 for h in hands.values()):
        raise ValueError("hold'em hands have two cards and the board at most five")
    for _, eligible in pots:
        if not any(s in hands for s in eligible):
            raise ValueError("a pot has no live eligible player")


def pot_shares(
    hands: Mapping[int, Sequence[int]],
    board: Sequence[int],
    pots: Sequence[Pot],
    *,
    samples: int = 20_000,
    seed: int = 0,
) -> Shares:
    """Expected winnings per seat; see the module docstring for the method."""
    _check(hands, board, pots)
    dead = {c for h in hands.values() for c in h} | set(board)
    deck = [c for c in range(52) if c not in dead]
    to_come = 5 - len(board)

    if to_come <= 2:
        totals = dict.fromkeys(hands, 0.0)
        count = 0
        for extra in itertools.combinations(deck, to_come):
            won = _winnings(_rank_all(hands, [*board, *extra]), pots)
            for s, v in won.items():
                totals[s] += v
            count += 1
        expected = {s: v / count for s, v in totals.items()}
        return Shares(expected, dict.fromkeys(hands, 0.0), "exact", count)

    if len(hands) == 2:
        (a, ha), (b, hb) = sorted(hands.items())
        first, second = tuple(sorted(ha, reverse=True)), tuple(sorted(hb, reverse=True))
        hero, villain = canonical_pair(first, second)
        eq = hand_vs_hand(tuple(hero), tuple(villain), tuple(board)).equity
        expected = dict.fromkeys(hands, 0.0)
        for amount, eligible in pots:
            live = [s for s in eligible if s in hands]
            if len(live) == 1:
                expected[live[0]] += amount
            else:
                expected[a] += amount * eq
                expected[b] += amount * (1 - eq)
        runouts = math.comb(len(deck), to_come)
        return Shares(expected, dict.fromkeys(hands, 0.0), "exact", runouts)

    rng = random.Random(seed)
    sums = dict.fromkeys(hands, 0.0)
    squares = dict.fromkeys(hands, 0.0)
    for _ in range(samples):
        extra = rng.sample(deck, to_come)
        won = _winnings(_rank_all(hands, [*board, *extra]), pots)
        for s, v in won.items():
            sums[s] += v
            squares[s] += v * v
    expected = {s: sums[s] / samples for s in hands}
    se = {
        s: math.sqrt(max(squares[s] / samples - expected[s] ** 2, 0.0) / (samples - 1))
        for s in hands
    }
    return Shares(expected, se, "monte-carlo", samples)
