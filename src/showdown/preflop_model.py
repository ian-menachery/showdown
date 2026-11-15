"""Solve, store and look up the heads-up preflop model above 20 bb (DECISIONS 33, 34).

The model is solved by our generic CFR+ (`cfr_plus`, 1,000 iterations, average
policy) at every grid depth and at three values of R_oop. The product answer
uses R_oop = 0.90. The 0.85 and 0.95 solves only flag classes whose most likely
action depends on R. Its charts are labelled "model chart": the postflop line
is an assumption, not a solved game (DECISIONS 33).
"""

from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from showdown.cfr import Tree, cfr_plus, compile_game, exploitability, policy_value
from showdown.equity.cards import CLASS_NAMES
from showdown.equity.matrix import PreflopMatrix
from showdown.games.preflop import ACTION_NAMES, PreflopGame

GRID: tuple[float, ...] = (25, 30, 40, 50, 60, 70, 80, 90, 100)
R_VALUES: tuple[float, ...] = (0.85, 0.90, 0.95)
R_PRODUCT = 0.90
ITERATIONS = 1000
PUSHFOLD_MAX_BB = 20
DEFAULT_MATRIX = "data/preflop_169_exact.npz"
DEFAULT_MODEL = "data/preflop_model.json"
LINE_ACTIONS = {"f": "fold", "c": "call", "r": "raise", "j": "all-in"}


@dataclass
class DepthSolution:
    stack: float
    r_oop: float
    raises: bool
    exploitability: float
    value_sb: float
    strategy: dict[str, dict[str, list[float]]]
    """node code -> class name -> probabilities, in `actions[node]` order."""
    actions: dict[str, list[str]]

    def probs(self, node: str, cls: int) -> dict[str, float]:
        row = self.strategy[node][CLASS_NAMES[cls]]
        return dict(zip(self.actions[node], row, strict=True))

    def line_factors(self, line: str) -> tuple[np.ndarray, np.ndarray]:
        """(SB, BB): per class, the product of that player's own action frequencies along `line`.

        `line` is a history code such as "rc" (an open, called). The BB's factor
        for "rc" is its range in a single-raised pot (DECISIONS 35).
        """
        factors = [np.ones(len(CLASS_NAMES)), np.ones(len(CLASS_NAMES))]
        for k, code in enumerate(line):
            node = line[:k]
            index = self.actions[node].index(LINE_ACTIONS[code])
            column = np.array([self.strategy[node][name][index] for name in CLASS_NAMES])
            factors[k % 2] = factors[k % 2] * column
        return factors[0], factors[1]

    def reach(self, line: str, pair_counts: np.ndarray) -> float:
        """The share of deals, weighted by class-pair combo counts, that follow `line`."""
        sb, bb = self.line_factors(line)
        w = pair_counts.astype(float)
        return float(sb @ w @ bb / w.sum())


def read_strategy(tree: Tree, policy) -> tuple[dict, dict]:
    """(strategy, actions) from a policy on the compiled preflop tree."""
    strategy: dict[str, dict[str, list[float]]] = {}
    actions: dict[str, list[str]] = {}
    for key, acts, probs in zip(tree.infoset_key, tree.infoset_actions, policy, strict=True):
        _, name, node = key.split(":")
        actions[node] = [ACTION_NAMES[a] for a in acts]
        strategy.setdefault(node, {})[name] = [float(p) for p in probs]
    return strategy, actions


def solve_depth(
    stack: float,
    r_oop: float,
    iterations: int = ITERATIONS,
    matrix_path: str | Path = DEFAULT_MATRIX,
    raises: bool = True,
) -> DepthSolution:
    game = PreflopGame(stack, PreflopMatrix.load(matrix_path), r_oop=r_oop, raises=raises)
    tree = compile_game(game)
    solver = cfr_plus(tree)
    solver.iterate(iterations)
    average = solver.average_policy()
    strategy, actions = read_strategy(tree, average)
    return DepthSolution(
        stack=float(stack),
        r_oop=float(r_oop),
        raises=raises,
        exploitability=exploitability(tree, average),
        value_sb=policy_value(tree, average),
        strategy=strategy,
        actions=actions,
    )


def _job(args: tuple) -> DepthSolution:
    return solve_depth(*args)


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass
class PreflopModel:
    iterations: int
    matrix_path: str
    matrix_sha256: str
    solutions: list[DepthSolution] = field(default_factory=list)
    checks: list[DepthSolution] = field(default_factory=list)
    """Gate P's 20 bb solves: the jam-only continuity game and the full game at R 0.90."""

    def at(self, stack: float, r_oop: float = R_PRODUCT) -> DepthSolution:
        for s in self.solutions:
            if np.isclose(s.stack, stack) and np.isclose(s.r_oop, r_oop):
                return s
        raise KeyError(f"no solution at {stack} bb, R {r_oop}")

    @staticmethod
    def depth_for(effective_bb: float) -> float | None:
        """The grid depth used for a stack (DECISIONS 34); None means push/fold answers."""
        if effective_bb <= PUSHFOLD_MAX_BB:
            return None
        if effective_bb >= GRID[-1]:
            return GRID[-1]
        # The nearest grid depth, with ties going to the smaller stack.
        return min(GRID, key=lambda g: (abs(g - effective_bb), g))

    def depends_on_r(self, stack: float, node: str, cls: int) -> bool:
        """True when the most likely action differs between the R 0.85 and 0.95 solves."""
        low, high = self.at(stack, 0.85).probs(node, cls), self.at(stack, 0.95).probs(node, cls)
        return max(low, key=low.get) != max(high, key=high.get)

    def save(self, path: str | Path) -> None:
        def encode(s: DepthSolution) -> dict:
            return {
                "stack": s.stack,
                "r_oop": s.r_oop,
                "raises": s.raises,
                "exploitability": s.exploitability,
                "value_sb": s.value_sb,
                "actions": s.actions,
                "strategy": s.strategy,
            }

        payload = {
            "algorithm": "cfr+",
            "iterations": self.iterations,
            "matrix": self.matrix_path,
            "matrix_sha256": self.matrix_sha256,
            "solutions": [encode(s) for s in self.solutions],
            "checks": [encode(s) for s in self.checks],
        }
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8", newline="\n")

    @classmethod
    def load(cls, path: str | Path = DEFAULT_MODEL) -> PreflopModel:
        data = json.loads(Path(path).read_text(encoding="utf-8"))

        def decode(d: dict) -> DepthSolution:
            return DepthSolution(
                stack=float(d["stack"]),
                r_oop=float(d["r_oop"]),
                raises=bool(d["raises"]),
                exploitability=float(d["exploitability"]),
                value_sb=float(d["value_sb"]),
                strategy=d["strategy"],
                actions=d["actions"],
            )

        return cls(
            data["iterations"],
            data["matrix"],
            data["matrix_sha256"],
            [decode(d) for d in data["solutions"]],
            [decode(d) for d in data["checks"]],
        )


def build(
    *,
    grid: tuple[float, ...] = GRID,
    r_values: tuple[float, ...] = R_VALUES,
    iterations: int = ITERATIONS,
    matrix_path: str | Path = DEFAULT_MATRIX,
    workers: int | None = None,
) -> PreflopModel:
    """Every grid solve, plus Gate P's two 20 bb check solves, in parallel processes."""
    jobs = [(s, r, iterations, str(matrix_path), True) for r in r_values for s in grid]
    checks = [
        (20.0, R_PRODUCT, iterations, str(matrix_path), False),  # jam-only: continuity
        (20.0, R_PRODUCT, iterations, str(matrix_path), True),  # full game: sanity
    ]
    all_jobs = checks + jobs
    workers = workers or min(len(all_jobs), os.cpu_count() or 1)
    if workers == 1:
        results = [_job(j) for j in all_jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_job, all_jobs))
    return PreflopModel(
        iterations, str(matrix_path), _sha256(matrix_path), results[2:], results[:2]
    )
