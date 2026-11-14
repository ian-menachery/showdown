"""The 169×169 preflop all-in equity matrix (DECISIONS 18).

Cell [i, j] is the equity of class i against class j: the average, over every
combo pair (one combo from each class) that shares no card, of that pair's
equity over a uniform random board. These are the payoffs of the push/fold
game.

How it is built (board-major Monte Carlo):

1. Draw a random 5-card board.
2. Rank, with eval7, each of the 1,081 combos that miss the board.
3. Compare every pair of them with numpy. That scores about 580,000
   non-conflicting combo pairs from one board.
4. Add the scores into 169×169 blocks with `np.add.reduceat`. `ALL_COMBOS` is
   sorted by class, which makes the blocks contiguous.

A board drawn uniformly from 52 cards, conditioned on missing a pair's 4 cards,
is uniform over that pair's 48-card remainder. Every combo pair has the same
chance of being live on a board, so the ratio of summed scores to summed live
counts estimates the equal-weight average.

Batches are seeded independently (`SeedSequence(seed, spawn_key=(b,))`), so the
result does not depend on how many worker processes ran them. The standard error
is computed by batch means. `pair_counts`, the card-removal weights, is exact
and not sampled.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from showdown.equity.cards import ALL_COMBOS, CLASS_NAMES, class_index, class_of
from showdown.equity.evaluator import EVAL7_CARDS, evaluate_eval7

_STATIC: dict[str, np.ndarray] = {}


def _static() -> dict[str, np.ndarray]:
    if not _STATIC:
        high = np.array([c[0] for c in ALL_COMBOS])
        low = np.array([c[1] for c in ALL_COMBOS])
        member = np.zeros((len(ALL_COMBOS), 52), dtype=bool)
        member[np.arange(len(ALL_COMBOS)), high] = True
        member[np.arange(len(ALL_COMBOS)), low] = True
        overlap = member.astype(np.int32) @ member.T.astype(np.int32)
        classes = np.array([class_of(c) for c in ALL_COMBOS])
        starts = np.flatnonzero(np.r_[True, classes[1:] != classes[:-1]])
        if len(starts) != 169:
            raise AssertionError("ALL_COMBOS must be grouped by class")
        _STATIC.update(high=high, low=low, disjoint=overlap == 0, starts=starts)
    return _STATIC


def _block_sum(matrix: np.ndarray, starts: np.ndarray) -> np.ndarray:
    return np.add.reduceat(np.add.reduceat(matrix, starts, axis=0), starts, axis=1)


def exact_pair_counts() -> np.ndarray:
    """Number of non-conflicting combo pairs for each class pair (card removal)."""
    s = _static()
    return _block_sum(s["disjoint"].astype(np.int64), s["starts"])


def _run_batch(args: tuple[int, int, int]) -> tuple[np.ndarray, np.ndarray]:
    seed, batch, boards = args
    s = _static()
    high, low, disjoint, starts = s["high"], s["low"], s["disjoint"], s["starts"]
    rng = np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(batch,)))
    E = EVAL7_CARDS
    ev = evaluate_eval7
    scores = np.zeros((169, 169))
    counts = np.zeros((169, 169))
    for _ in range(boards):
        board = rng.choice(52, size=5, replace=False)
        on_board = np.zeros(52, dtype=bool)
        on_board[board] = True
        live = ~(on_board[high] | on_board[low])
        board_cards = [E[c] for c in board]
        ranks = np.full(len(ALL_COMBOS), -1, dtype=np.int64)
        for k in np.flatnonzero(live):
            ranks[k] = ev([E[high[k]], E[low[k]], *board_cards])
        valid = disjoint & live[:, None] & live[None, :]
        wins = (ranks[:, None] > ranks[None, :]) & valid
        ties = (ranks[:, None] == ranks[None, :]) & valid
        score = wins.astype(np.float32) + np.float32(0.5) * ties
        scores += _block_sum(score, starts)
        counts += _block_sum(valid.astype(np.float32), starts)
    return scores, counts


@dataclass
class PreflopMatrix:
    equity: np.ndarray
    """[i, j]: equity of class i against class j."""
    se: np.ndarray
    """Batch-means standard error of each cell (0 on the diagonal, which is exactly 0.5)."""
    pair_counts: np.ndarray
    """Exact number of non-conflicting combo pairs per class pair."""
    boards: int
    batches: int
    seed: int

    def cell(self, row: str, col: str) -> tuple[float, float]:
        i, j = class_index(row), class_index(col)
        return float(self.equity[i, j]), float(self.se[i, j])

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            equity=self.equity,
            se=self.se,
            pair_counts=self.pair_counts,
            boards=self.boards,
            batches=self.batches,
            seed=self.seed,
            class_names=np.array(CLASS_NAMES),
        )

    @classmethod
    def load(cls, path: str | Path) -> PreflopMatrix:
        with np.load(path) as data:
            if tuple(data["class_names"]) != CLASS_NAMES:
                raise ValueError(f"{path}: class order does not match this version")
            return cls(
                equity=data["equity"],
                se=data["se"],
                pair_counts=data["pair_counts"],
                boards=int(data["boards"]),
                batches=int(data["batches"]),
                seed=int(data["seed"]),
            )


def build(
    *, boards_per_batch: int, batches: int, seed: int, workers: int | None = None
) -> PreflopMatrix:
    if batches < 2 or boards_per_batch < 1:
        raise ValueError("need at least 2 batches of at least 1 board")
    jobs = [(seed, b, boards_per_batch) for b in range(batches)]
    workers = workers or os.cpu_count() or 1
    if workers == 1:
        results = [_run_batch(job) for job in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_run_batch, jobs))
    scores = np.stack([r[0] for r in results])
    counts = np.stack([r[1] for r in results])
    # A class pair with no live sample (only in tiny builds) comes out NaN, not 0.
    with np.errstate(invalid="ignore", divide="ignore"):
        equity = scores.sum(axis=0) / counts.sum(axis=0)
        per_batch = scores / counts
    se = per_batch.std(axis=0, ddof=1) / np.sqrt(batches)
    return PreflopMatrix(
        equity=equity,
        se=se,
        pair_counts=exact_pair_counts(),
        boards=boards_per_batch * batches,
        batches=batches,
        seed=seed,
    )
