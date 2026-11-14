"""Exact heads-up equity by exhaustive enumeration of the remaining board.

Equity = P(win) + P(tie) / 2. For ranges, every combo pair that does not share
a card (with each other or the board) counts equally, and each pair's equity is
taken over all of its own runouts.

Speed: about 5 s for one preflop hand-vs-hand (1,712,304 boards). For class vs
class, combo pairs that are identical up to a relabelling of suits share one
enumeration. That cuts AA vs KK from 36 enumerations to 3.
"""

from __future__ import annotations

import itertools
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from math import comb

import numpy as np

from showdown.equity.cards import CLASS_COMBOS, Combo
from showdown.equity.evaluator import EVAL7_CARDS, evaluate_eval7

MAX_EXACT_EVALUATIONS = 60_000_000
"""Runaway guard for range-vs-range enumeration, about a minute of work."""

_SUIT_PERMUTATIONS = tuple(itertools.permutations(range(4)))


@dataclass(frozen=True)
class Equity:
    win: float
    tie: float
    outcomes: int
    """Number of (combo pair, runout) outcomes enumerated."""

    @property
    def equity(self) -> float:
        return self.win + self.tie / 2

    @property
    def lose(self) -> float:
        return 1.0 - self.win - self.tie


def _check_disjoint(*groups: Sequence[int]) -> None:
    cards = [c for g in groups for c in g]
    if len(set(cards)) != len(cards):
        raise ValueError("hands and board share a card")
    if len(groups[-1]) > 5:
        raise ValueError("a board has at most 5 cards")


def hand_vs_hand(hero: Combo, villain: Combo, board: Sequence[int] = ()) -> Equity:
    _check_disjoint(hero, villain, board)
    return _hand_vs_hand(tuple(hero), tuple(villain), tuple(sorted(board)))


@lru_cache(maxsize=4096)
def _hand_vs_hand(hero: Combo, villain: Combo, board: tuple[int, ...]) -> Equity:
    dead = set(hero) | set(villain) | set(board)
    deck = [EVAL7_CARDS[c] for c in range(52) if c not in dead]
    h = [EVAL7_CARDS[c] for c in hero]
    v = [EVAL7_CARDS[c] for c in villain]
    b = [EVAL7_CARDS[c] for c in board]
    ev = evaluate_eval7
    win = tie = n = 0
    for run in itertools.combinations(deck, 5 - len(board)):
        full = b + list(run)
        a, k = ev(h + full), ev(v + full)
        n += 1
        if a > k:
            win += 1
        elif a == k:
            tie += 1
    return Equity(win / n, tie / n, n)


def range_vs_range(
    hero: Sequence[Combo], villain: Sequence[Combo], board: Sequence[int] = ()
) -> Equity:
    """Exact equity of `hero` against `villain`, equal weight per valid combo pair."""
    board = tuple(board)
    _check_disjoint(board)
    on_board = set(board)
    hero = [h for h in hero if not on_board.intersection(h)]
    villain = [v for v in villain if not on_board.intersection(v)]
    pairs_valid = np.array([[not set(h) & set(v) for v in villain] for h in hero], dtype=bool)
    if not hero or not villain or not pairs_valid.any():
        raise ValueError("no combo pair is possible on this board")
    if len(hero) == 1 and len(villain) == 1:
        return hand_vs_hand(hero[0], villain[0], board)

    deck = [c for c in range(52) if c not in on_board]
    need = 5 - len(board)
    runouts = comb(len(deck), need)
    work = runouts * (len(hero) + len(villain))
    if work > MAX_EXACT_EVALUATIONS:
        raise ValueError(
            f"exact enumeration needs about {work:,} evaluations "
            f"(guard {MAX_EXACT_EVALUATIONS:,}); use Monte Carlo"
        )

    E = EVAL7_CARDS
    b = [E[c] for c in board]
    wins = np.zeros(pairs_valid.shape)
    ties = np.zeros(pairs_valid.shape)
    counts = np.zeros(pairs_valid.shape)
    for run in itertools.combinations(deck, need):
        run_set = set(run)
        full = b + [E[c] for c in run]
        hv = np.array([not run_set.intersection(h) for h in hero])
        vv = np.array([not run_set.intersection(v) for v in villain])
        hr = np.array(
            [
                evaluate_eval7([E[h[0]], E[h[1]], *full]) if ok else -1
                for h, ok in zip(hero, hv, strict=True)
            ]
        )
        vr = np.array(
            [
                evaluate_eval7([E[v[0]], E[v[1]], *full]) if ok else -1
                for v, ok in zip(villain, vv, strict=True)
            ]
        )
        live = pairs_valid & hv[:, None] & vv[None, :]
        wins += (hr[:, None] > vr[None, :]) & live
        ties += (hr[:, None] == vr[None, :]) & live
        counts += live
    per_pair = counts[pairs_valid]
    win = float(np.mean(wins[pairs_valid] / per_pair))
    tie = float(np.mean(ties[pairs_valid] / per_pair))
    return Equity(win, tie, int(per_pair.sum()))


def canonical_pair(hero: Combo, villain: Combo) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """The smallest relabelling of suits. Preflop equity is invariant under it."""
    best = None
    for perm in _SUIT_PERMUTATIONS:
        h = tuple(sorted((4 * (c // 4) + perm[c % 4] for c in hero), reverse=True))
        v = tuple(sorted((4 * (c // 4) + perm[c % 4] for c in villain), reverse=True))
        if best is None or (h, v) < best:
            best = (h, v)
    return best


def class_vs_class(row_class: int, col_class: int) -> Equity:
    """Exact preflop equity of one hand class against another (card removal included)."""
    groups: Counter = Counter()
    for h in CLASS_COMBOS[row_class]:
        for v in CLASS_COMBOS[col_class]:
            if not set(h) & set(v):
                groups[canonical_pair(h, v)] += 1
    if not groups:
        raise ValueError("these classes cannot be dealt together")
    total = sum(groups.values())
    win = tie = 0.0
    outcomes = 0
    for (h, v), count in sorted(groups.items()):
        eq = hand_vs_hand(h, v)
        win += count * eq.win
        tie += count * eq.tie
        outcomes += count * eq.outcomes
    return Equity(win / total, tie / total, outcomes)
