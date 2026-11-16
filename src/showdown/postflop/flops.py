"""Flops up to suit symmetry: 1,755 suit-distinct flops out of 22,100 (DECISIONS 40)."""

from __future__ import annotations

import functools
import itertools

from showdown.equity.cards import card, rank_of, suit_of

SUIT_PERMUTATIONS = tuple(itertools.permutations(range(4)))


def relabel(cards: tuple[int, ...], perm: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(card(rank_of(c), perm[suit_of(c)]) for c in cards)


def canonical(flop: tuple[int, ...]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """(the canonical flop, the suit permutation that maps `flop` onto it).

    The canonical flop is the smallest sorted card tuple over all 24 relabellings.
    """
    best = None
    for perm in SUIT_PERMUTATIONS:
        image = tuple(sorted(relabel(flop, perm), reverse=True))
        if best is None or image < best[0]:
            best = (image, perm)
    return best


@functools.cache
def suit_distinct_flops() -> tuple[tuple[int, ...], ...]:
    """Every canonical flop, sorted."""
    return tuple(sorted({canonical(f)[0] for f in itertools.combinations(range(52), 3)}))


@functools.cache
def flop_weights() -> dict[tuple[int, ...], int]:
    """How many of the 22,100 flops each canonical flop stands for."""
    weights: dict[tuple[int, ...], int] = {}
    for f in itertools.combinations(range(52), 3):
        key = canonical(f)[0]
        weights[key] = weights.get(key, 0) + 1
    return weights
