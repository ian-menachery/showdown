"""Range strings to combos.

Comma-separated tokens, whitespace ignored:

    AA  AKs  AKo  AK         one class (AK means suited and offsuit)
    TT+  A2s+  KTo+  AT+     a pair and every higher pair, or a fixed high card
                             with the kicker running up to one below it
    22-55  A2s-A5s  KTo-KQo  inclusive spans with the same shape
    AsKs                     one exact combo
    random                   all 1,326 combos

Returns the combos sorted and de-duplicated. Weights are not supported.
"""

from __future__ import annotations

import re

from showdown.equity.cards import (
    ALL_COMBOS,
    RANKS,
    Combo,
    make_combo,
    parse_card,
    rank_of,
    suit_of,
)

_CLASS = re.compile(r"^([2-9TJQKA])([2-9TJQKA])([so]?)$")


def _class_combos(high: int, low: int, kind: str) -> list[Combo]:
    if high == low:
        if kind:
            raise ValueError(f"a pair cannot be suited or offsuit: {RANKS[high] * 2 + kind}")
        return [c for c in ALL_COMBOS if rank_of(c[0]) == rank_of(c[1]) == high]
    if high < low:
        high, low = low, high
    out = []
    for c in ALL_COMBOS:
        if (rank_of(c[0]), rank_of(c[1])) != (high, low):
            continue
        suited = suit_of(c[0]) == suit_of(c[1])
        if kind == "" or (kind == "s") == suited:
            out.append(c)
    return out


def _parse_class(text: str) -> tuple[int, int, str]:
    m = _CLASS.match(text)
    if not m:
        raise ValueError(f"bad range token {text!r}")
    a, b, kind = RANKS.index(m.group(1)), RANKS.index(m.group(2)), m.group(3)
    return max(a, b), min(a, b), kind


def _token(token: str) -> list[Combo]:
    if token.lower() in ("random", "any"):
        return list(ALL_COMBOS)
    if len(token) == 4 and token[1].islower() and token[3].islower():
        return [make_combo(parse_card(token[:2]), parse_card(token[2:]))]
    # Ranks never use the letters S or O, so this only touches shape suffixes.
    upper = token.upper().replace("S", "s").replace("O", "o")

    if upper.endswith("+"):
        high, low, kind = _parse_class(upper[:-1])
        if high == low:
            return [c for r in range(high, 13) for c in _class_combos(r, r, "")]
        return [c for k in range(low, high) for c in _class_combos(high, k, kind)]

    if "-" in upper:
        left, right = upper.split("-", 1)
        h1, l1, k1 = _parse_class(left)
        h2, l2, k2 = _parse_class(right)
        if k1 != k2:
            raise ValueError(f"span ends differ in shape: {token!r}")
        if h1 == l1 and h2 == l2:
            lo, hi = sorted((h1, h2))
            return [c for r in range(lo, hi + 1) for c in _class_combos(r, r, "")]
        if h1 != h2 or h1 == l1 or h2 == l2:
            raise ValueError(f"span must keep the same high card: {token!r}")
        lo, hi = sorted((l1, l2))
        return [c for k in range(lo, hi + 1) for c in _class_combos(h1, k, k1)]

    high, low, kind = _parse_class(upper)
    return _class_combos(high, low, kind)


def parse_range(text: str) -> tuple[Combo, ...]:
    tokens = [t for t in re.sub(r"\s", "", text).split(",") if t]
    if not tokens:
        raise ValueError("empty range")
    combos: set[Combo] = set()
    for token in tokens:
        combos.update(_token(token))
    return tuple(sorted(combos, reverse=True))
