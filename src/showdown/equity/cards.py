"""Cards, two-card combos and the 169 preflop hand classes.

A card is an int 0..51: 4 * rank + suit, with ranks 2..A as 0..12 and suits in
the order c, d, h, s. A combo is a pair of cards stored high card first.

The 169 classes sit on the usual 13×13 grid, with rows and columns running from
A down to 2. Class index = 13 * row + col. The diagonal holds the pairs. Above
the diagonal (row < col) are suited hands, so row A, column K is AKs. Below it
are offsuit hands, so row K, column A is AKo.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

RANKS = "23456789TJQKA"
SUITS = "cdhs"

Combo = tuple[int, int]


def card(rank: int, suit: int) -> int:
    return 4 * rank + suit


def rank_of(c: int) -> int:
    return c // 4


def suit_of(c: int) -> int:
    return c % 4


def parse_card(text: str) -> int:
    if len(text) != 2 or text[0].upper() not in RANKS or text[1].lower() not in SUITS:
        raise ValueError(f"bad card {text!r}; expected rank then suit, like 'As' or 'Td'")
    return card(RANKS.index(text[0].upper()), SUITS.index(text[1].lower()))


def card_str(c: int) -> str:
    return RANKS[rank_of(c)] + SUITS[suit_of(c)]


def parse_cards(text: str) -> tuple[int, ...]:
    """'AsKd 7c' or 'AsKd7c' -> card ids. Rejects duplicates."""
    compact = re.sub(r"[\s,]", "", text)
    if len(compact) % 2:
        raise ValueError(f"bad card list {text!r}")
    cards = tuple(parse_card(compact[i : i + 2]) for i in range(0, len(compact), 2))
    if len(set(cards)) != len(cards):
        raise ValueError(f"duplicate card in {text!r}")
    return cards


def make_combo(a: int, b: int) -> Combo:
    if a == b:
        raise ValueError("a combo needs two different cards")
    return (a, b) if a > b else (b, a)


def combo_str(combo: Combo) -> str:
    return card_str(combo[0]) + card_str(combo[1])


def cards_str(cards: Iterable[int]) -> str:
    return "".join(card_str(c) for c in cards)


# --- hand classes -----------------------------------------------------------


def _grid_rank(index: int) -> int:
    """Grid row/column 0 is the ace (rank 12)."""
    return 12 - index


def class_name(index: int) -> str:
    row, col = divmod(index, 13)
    high, low = RANKS[_grid_rank(min(row, col))], RANKS[_grid_rank(max(row, col))]
    if row == col:
        return high + low
    return high + low + ("s" if row < col else "o")


CLASS_NAMES: tuple[str, ...] = tuple(class_name(i) for i in range(169))
_CLASS_INDEX = {name: i for i, name in enumerate(CLASS_NAMES)}


def class_index(name: str) -> int:
    key = name[0].upper() + name[1].upper() + name[2:].lower()
    try:
        return _CLASS_INDEX[key]
    except KeyError:
        raise ValueError(f"unknown hand class {name!r}; expected like 'AA', 'AKs', 'T9o'") from None


def class_of(combo: Combo) -> int:
    high, low = rank_of(combo[0]), rank_of(combo[1])
    if high == low:
        row = col = 12 - high
    elif suit_of(combo[0]) == suit_of(combo[1]):
        row, col = 12 - high, 12 - low
    else:
        row, col = 12 - low, 12 - high
    return 13 * row + col


ALL_COMBOS: tuple[Combo, ...] = tuple(
    sorted(
        (make_combo(a, b) for a in range(52) for b in range(a)),
        key=lambda c: (class_of(c), -c[0], -c[1]),
    )
)
"""All 1,326 combos, grouped by class index (the matrix builder relies on this)."""

CLASS_COMBOS: tuple[tuple[Combo, ...], ...] = tuple(
    tuple(c for c in ALL_COMBOS if class_of(c) == i) for i in range(169)
)
