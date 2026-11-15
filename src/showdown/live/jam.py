"""Call or fold against an all-in, as the best response to a villain range (DECISIONS 36).

The hero's equity is exact for a range of whole hand classes:

    E = sum_j w_j * n_j * M[i, j] / sum_j w_j * n_j

where i is the hero's class, w_j the villain class's weight, n_j the combos
of class j that share no card with the hero's hand, and M the exact 169 x 169
matrix. Every combo of class i is a suit relabelling of the hero's hand and
every class j is closed under relabelling, so the hero's average equity
against class j is the class average M[i, j].
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from showdown.equity.cards import CLASS_COMBOS, CLASS_NAMES, Combo, class_of
from showdown.equity.matrix import PreflopMatrix

CLOSE = 0.02
"""A call within 2 points of the price is flagged "close"."""
JAM_DECISIONS = ("bb_vs_jam", "sb_vs_jam", "bb_vs_4bet_jam")
DEFAULT_TOP = {"bb_vs_jam": 20.0, "bb_vs_4bet_jam": 8.0}
"""The labelled default villain range, top % of combos, where nothing else answers."""
JAM_KIND = {
    "bb_vs_jam": "first-in jam",
    "sb_vs_jam": "jam over the open",
    "bb_vs_4bet_jam": "4-bet jam",
}
_CLASS_SIZES = np.array([len(c) for c in CLASS_COMBOS])


class RangeError(ValueError):
    """A villain range the helper cannot use."""


def class_weights(combos: Sequence[Combo]) -> np.ndarray:
    """1 for each class the range covers entirely, 0 otherwise; an error for a partial class."""
    counts = np.zeros(len(CLASS_COMBOS))
    for combo in set(combos):
        counts[class_of(combo)] += 1
    partial = [CLASS_NAMES[k] for k in np.flatnonzero((counts > 0) & (counts < _CLASS_SIZES))]
    if partial:
        raise RangeError(
            "preflop ranges must be whole hand classes (e.g. AKs, not AhKh); "
            "partly covered: " + ", ".join(partial)
        )
    return (counts == _CLASS_SIZES).astype(float)


def live_counts(hero: Combo) -> np.ndarray:
    """Per class, the combos that share no card with the hero's hand."""
    held = set(hero)
    return np.array([sum(1 for v in combos if not held & set(v)) for combos in CLASS_COMBOS])


def jam_equity(hero: Combo, weights: np.ndarray, matrix: PreflopMatrix) -> float:
    """The hero's exact all-in equity against villain classes weighted by `weights`."""
    w = np.asarray(weights, dtype=float) * live_counts(hero)
    total = w.sum()
    if total <= 0:
        raise RangeError("no villain hand in this range is possible with the hero's cards")
    return float((w * matrix.equity[class_of(hero)]).sum() / total)


@dataclass(frozen=True)
class JamAnswer:
    equity: float
    price: float
    """to call / (pot + to call): the equity a call needs."""
    action: str
    """call or fold."""
    ev_call: float
    """The EV of calling relative to folding, in bb."""
    close: bool


def answer(equity: float, pot: float, to_call: float) -> JamAnswer:
    """The best response's call or fold. A to-call of 0 (a 1 bb push/fold jam) prices at 0."""
    if to_call < 0 or pot + to_call <= 0:
        raise ValueError("need a to-call of at least 0 and a positive pot")
    price = to_call / (pot + to_call)
    return JamAnswer(
        equity=equity,
        price=price,
        action="call" if equity >= price else "fold",
        ev_call=equity * (pot + to_call) - to_call,
        close=abs(equity - price) < CLOSE,
    )
