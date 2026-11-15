"""Seeded Monte Carlo equity with a standard error.

Each sample draws one valid combo pair uniformly (so pairs count equally, as in
`exact.range_vs_range`), then a uniform runout from the cards left. Given
villain weights (DECISIONS 35), a pair is drawn with its villain combo's weight. A sample
scores 1 for a win, 0.5 for a tie and 0 for a loss. The standard error is the
sample standard deviation over sqrt(n).

Gate C checks calibration: over 200 seeded runs, the share of estimates within
±2 SE of the exact answer must fall between 0.90 and 0.99. That is the test
eval7's own Monte Carlo fails.
"""

from __future__ import annotations

import math
import random
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import accumulate

from showdown.equity.cards import Combo
from showdown.equity.evaluator import EVAL7_CARDS, evaluate_eval7


@dataclass(frozen=True)
class Estimate:
    equity: float
    se: float
    samples: int


def monte_carlo(
    hero: Sequence[Combo],
    villain: Sequence[Combo],
    board: Sequence[int] = (),
    *,
    samples: int = 100_000,
    seed: int = 0,
    villain_weights: Sequence[float] | None = None,
) -> Estimate:
    if samples < 2:
        raise ValueError("need at least 2 samples for a standard error")
    board = tuple(board)
    if len(set(board)) != len(board) or len(board) > 5:
        raise ValueError("bad board")
    on_board = set(board)
    if villain_weights is None:
        weighted = [(v, 1.0) for v in villain]
    else:
        if len(villain_weights) != len(villain):
            raise ValueError("need one weight per villain combo")
        if any(w < 0 for w in villain_weights):
            raise ValueError("weights must be at least 0")
        weighted = [(v, float(w)) for v, w in zip(villain, villain_weights, strict=True) if w > 0]
    pairs, pair_weights = [], []
    for h in hero:
        for v, w in weighted:
            if not (set(h) & set(v)) and not (on_board & set(h)) and not (on_board & set(v)):
                pairs.append((h, v))
                pair_weights.append(w)
    if not pairs:
        raise ValueError("no combo pair is possible on this board")
    cumulative = list(accumulate(pair_weights)) if villain_weights is not None else None

    rng = random.Random(seed)
    E = EVAL7_CARDS
    ev = evaluate_eval7
    deck = [c for c in range(52) if c not in on_board]
    need = 5 - len(board)
    b = [E[c] for c in board]
    total = total_sq = 0.0
    for _ in range(samples):
        if cumulative is None:
            h, v = pairs[rng.randrange(len(pairs))]
        else:
            k = bisect_right(cumulative, rng.random() * cumulative[-1])
            h, v = pairs[min(k, len(pairs) - 1)]
        dead = {h[0], h[1], v[0], v[1]}
        run = [c for c in rng.sample(deck, need + 4) if c not in dead][:need]
        full = b + [E[c] for c in run]
        a = ev([E[h[0]], E[h[1]], *full])
        k = ev([E[v[0]], E[v[1]], *full])
        score = 1.0 if a > k else (0.5 if a == k else 0.0)
        total += score
        total_sq += score * score
    mean = total / samples
    variance = max(0.0, (total_sq - samples * mean * mean) / (samples - 1))
    return Estimate(mean, math.sqrt(variance / samples), samples)
