"""Hand evaluation, delegated to eval7 (DECISIONS 5).

Only `eval7.evaluate` is used. eval7's own equity and Monte Carlo helpers are
wrong (spike, 2026-11-14) and must not be called from anywhere in showdown.
Higher values are better hands; equal values tie.
"""

from __future__ import annotations

from collections.abc import Iterable

import eval7

from showdown.equity.cards import card_str

EVAL7_CARDS: tuple = tuple(eval7.Card(card_str(c)) for c in range(52))
"""eval7 card objects indexed by our card id, for hot loops."""

evaluate_eval7 = eval7.evaluate


def evaluate(cards: Iterable[int]) -> int:
    """Strength of the best 5-card hand in 5 to 7 cards. Higher is better."""
    return eval7.evaluate([EVAL7_CARDS[c] for c in cards])
