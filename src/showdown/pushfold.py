"""Push/fold solutions at 1 to 20 bb, their charts, and Gate D's comparison (DECISIONS 22).

The solve is our generic CFR+ on the compiled push/fold tree: `cfr_plus`,
1,000 iterations at every depth, average policy, with payoffs from the exact
matrix (DECISIONS 21). Each depth is solved on its own, so the result does not
depend on how many worker processes ran.

A strategy is a pair of length-169 vectors in class-index order: `push[i]`,
the SB's all-in probability with class i, and `call[j]`, the BB's call
probability with class j.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from showdown.cfr import Policy, Tree, cfr_plus, compile_game, exploitability, policy_value
from showdown.equity.cards import CLASS_COMBOS, CLASS_NAMES, RANKS
from showdown.equity.matrix import PreflopMatrix
from showdown.games.pushfold import ALL_IN, PushFoldGame, fold_payoffs

DEPTHS: tuple[int, ...] = tuple(range(1, 21))
ITERATIONS = 1000
PURE = 0.99
"""A probability at or above this plays, at or below 1 - PURE folds (DECISIONS 22)."""
DEFAULT_MATRIX = "data/preflop_169_exact.npz"
DEFAULT_SOLUTION = "data/pushfold.json"
COMBOS_PER_CLASS = np.array([len(c) for c in CLASS_COMBOS])


@dataclass
class DepthResult:
    stack: float
    push: np.ndarray
    call: np.ndarray
    exploitability: float
    """bb per hand, by `showdown.cfr.exploitability` on the compiled tree."""
    value_sb: float
    """The SB's expected result in bb per hand under the solved strategies."""

    def push_share(self) -> float:
        """Share of the 1,326 starting hands the SB jams."""
        return float(COMBOS_PER_CLASS @ self.push / 1326)

    def call_share(self) -> float:
        return float(COMBOS_PER_CLASS @ self.call / 1326)


def strategy_vectors(tree: Tree, policy: Policy) -> tuple[np.ndarray, np.ndarray]:
    """(push, call) from a policy on the compiled push/fold tree."""
    push, call = np.full(169, np.nan), np.full(169, np.nan)
    index = {name: k for k, name in enumerate(CLASS_NAMES)}
    for key, actions, probs in zip(tree.infoset_key, tree.infoset_actions, policy, strict=True):
        seat, name = key.split(":")
        target = push if seat == "SB" else call
        target[index[name]] = probs[actions.index(ALL_IN)]
    if np.isnan(push).any() or np.isnan(call).any():
        raise ValueError("policy does not cover all 338 push/fold infosets")
    return push, call


def policy_from_vectors(tree: Tree, push: np.ndarray, call: np.ndarray) -> Policy:
    """Inverse of `strategy_vectors`."""
    index = {name: k for k, name in enumerate(CLASS_NAMES)}
    policy: Policy = []
    for key, actions in zip(tree.infoset_key, tree.infoset_actions, strict=True):
        seat, name = key.split(":")
        p = float((push if seat == "SB" else call)[index[name]])
        policy.append([p if a == ALL_IN else 1.0 - p for a in actions])
    return policy


def solve_depth(
    stack: float,
    iterations: int = ITERATIONS,
    matrix_path: str | Path = DEFAULT_MATRIX,
    ante: float = 0.0,
) -> DepthResult:
    tree = compile_game(PushFoldGame(stack, PreflopMatrix.load(matrix_path), ante))
    solver = cfr_plus(tree)
    solver.iterate(iterations)
    average = solver.average_policy()
    push, call = strategy_vectors(tree, average)
    return DepthResult(
        stack=float(stack),
        push=push,
        call=call,
        exploitability=exploitability(tree, average),
        value_sb=policy_value(tree, average),
    )


def _solve_job(args: tuple[float, int, str, float]) -> DepthResult:
    return solve_depth(*args)


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass
class PushFoldSolution:
    iterations: int
    matrix_path: str
    matrix_sha256: str
    depths: list[DepthResult] = field(default_factory=list)
    ante: float = 0.0
    """Per player, in bb (DECISIONS 48)."""

    def at(self, stack: float) -> DepthResult:
        for result in self.depths:
            if np.isclose(result.stack, stack):
                return result
        raise KeyError(f"no solution at {stack} bb; solved: {[d.stack for d in self.depths]}")

    def save(self, path: str | Path) -> None:
        payload = {
            "algorithm": "cfr+",
            "iterations": self.iterations,
            "matrix": self.matrix_path,
            "matrix_sha256": self.matrix_sha256,
            **({"ante": self.ante} if self.ante else {}),
            "depths": [
                {
                    "stack": d.stack,
                    "exploitability": d.exploitability,
                    "value_sb": d.value_sb,
                    "push": dict(zip(CLASS_NAMES, d.push.tolist(), strict=True)),
                    "call": dict(zip(CLASS_NAMES, d.call.tolist(), strict=True)),
                }
                for d in self.depths
            ],
        }
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8", newline="\n")

    @classmethod
    def load(cls, path: str | Path) -> PushFoldSolution:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        depths = [
            DepthResult(
                stack=float(d["stack"]),
                push=np.array([d["push"][n] for n in CLASS_NAMES]),
                call=np.array([d["call"][n] for n in CLASS_NAMES]),
                exploitability=float(d["exploitability"]),
                value_sb=float(d["value_sb"]),
            )
            for d in data["depths"]
        ]
        ante = float(data.get("ante", 0.0))
        return cls(data["iterations"], data["matrix"], data["matrix_sha256"], depths, ante)


def solve_all(
    depths: Sequence[float] = DEPTHS,
    iterations: int = ITERATIONS,
    matrix_path: str | Path = DEFAULT_MATRIX,
    workers: int | None = None,
    ante: float = 0.0,
) -> PushFoldSolution:
    jobs = [(float(s), iterations, str(matrix_path), float(ante)) for s in depths]
    workers = workers or min(len(jobs), os.cpu_count() or 1)
    if workers == 1:
        results = [_solve_job(job) for job in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_solve_job, jobs))
    return PushFoldSolution(iterations, str(matrix_path), _sha256(matrix_path), results, ante)


# --- closed forms, independent of the tree ---------------------------------------


def _terms(stack: float, matrix: PreflopMatrix) -> tuple[np.ndarray, np.ndarray]:
    weights = matrix.pair_counts.astype(float)
    return weights / weights.sum(), stack * (2 * matrix.equity - 1)


def sb_value(
    push: np.ndarray, call: np.ndarray, stack: float, matrix: PreflopMatrix, ante: float = 0.0
) -> float:
    """The SB's expected bb per hand, summed directly over class pairs."""
    w, showdown = _terms(stack, matrix)
    sb_fold, bb_fold = fold_payoffs(stack, ante)
    jam = (1 - call)[None, :] * bb_fold + call[None, :] * showdown
    per_pair = (1 - push)[:, None] * sb_fold + push[:, None] * jam
    return float((w * per_pair).sum())


def closed_form_exploitability(
    push: np.ndarray, call: np.ndarray, stack: float, matrix: PreflopMatrix, ante: float = 0.0
) -> float:
    """NashConv / 2 (DECISIONS 7), from best responses computed class by class."""
    w, showdown = _terms(stack, matrix)
    sb_fold, bb_fold = fold_payoffs(stack, ante)
    # SB best response to `call`: per class, the better of folding and jamming.
    jam = ((1 - call)[None, :] * bb_fold + call[None, :] * showdown) * w
    fold = sb_fold * w
    sb_best = np.maximum(fold.sum(axis=1), jam.sum(axis=1)).sum()
    # BB best response to `push`: per class, the better of folding and calling (BB's payoff).
    folded = (1 - push)[:, None] * (-sb_fold) * w
    vs_jam_fold = push[:, None] * (-bb_fold) * w
    vs_jam_call = push[:, None] * (-showdown) * w
    bb_best = (
        folded.sum(axis=0) + np.maximum(vs_jam_fold.sum(axis=0), vs_jam_call.sum(axis=0))
    ).sum()
    # NashConv = (sb_best - value) + (bb_best - (-value)); the values cancel.
    return float((sb_best + bb_best) / 2)


def sb_action_values(
    call: np.ndarray, stack: float, matrix: PreflopMatrix, ante: float = 0.0
) -> tuple[np.ndarray, np.ndarray]:
    """Per SB class, the SB's EV in bb of folding and of jamming against `call` (DECISIONS 24)."""
    w, showdown = _terms(stack, matrix)
    sb_fold, bb_fold = fold_payoffs(stack, ante)
    jam = (w * ((1 - call)[None, :] * bb_fold + call[None, :] * showdown)).sum(axis=1)
    return np.full(169, sb_fold), jam / w.sum(axis=1)


def bb_action_values(
    push: np.ndarray, stack: float, matrix: PreflopMatrix, ante: float = 0.0
) -> tuple[np.ndarray, np.ndarray]:
    """Per BB class facing a jam, the BB's EV in bb of folding and of calling against `push`.

    A class that no SB jam can meet (impossible with any real strategy, since
    every jam range is weighted by card removal) gets NaN.
    """
    w, showdown = _terms(stack, matrix)
    weight = w * push[:, None]
    total = weight.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        call = (weight * -showdown).sum(axis=0) / total
    return np.full(169, -fold_payoffs(stack, ante)[1]), call


# --- Gate D comparison ----------------------------------------------------------------


def classify(probs: np.ndarray) -> np.ndarray:
    """1 where a class plays (p >= 0.99), 0 where it folds (p <= 0.01), -1 where it mixes."""
    probs = np.asarray(probs, dtype=float)
    out = np.full(probs.shape, -1)
    out[probs >= PURE] = 1
    out[probs <= 1 - PURE] = 0
    return out


@dataclass
class Comparison:
    agree: int
    compared: int
    excluded: int
    disagree: list[str]
    """Class names where both sides are pure and differ."""

    @property
    def share(self) -> float:
        return self.agree / self.compared if self.compared else float("nan")

    @property
    def passed(self) -> bool:
        return self.compared > 0 and self.share >= 0.95


def compare(ours: np.ndarray, reference: np.ndarray) -> Comparison:
    """Gate D's rule (DECISIONS 22) for one seat at one depth."""
    a, b = classify(ours), classify(reference)
    both = (a >= 0) & (b >= 0)
    differ = both & (a != b)
    return Comparison(
        agree=int((both & (a == b)).sum()),
        compared=int(both.sum()),
        excluded=int((~both).sum()),
        disagree=[CLASS_NAMES[k] for k in np.flatnonzero(differ)],
    )


# --- charts ----------------------------------------------------------------------------


def chart(probs: np.ndarray) -> str:
    """13×13 grid of whole percentages: suited above the diagonal, offsuit below.

    "100" means always and "." means never; anything else is a mixed class.
    """
    labels = RANKS[::-1]
    lines = ["     " + "".join(f"{r:>4}" for r in labels)]
    for row in range(13):
        cells = []
        for col in range(13):
            p = float(probs[13 * row + col])
            pct = round(100 * p)
            cells.append(f"{'.' if pct == 0 else pct:>4}")
        lines.append(f"  {labels[row]}  " + "".join(cells))
    return "\n".join(lines)
