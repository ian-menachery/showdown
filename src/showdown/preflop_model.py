"""Solve, store and look up the heads-up preflop model above 20 bb (DECISIONS 33, 34, 49).

The model is solved by our generic CFR+ (`cfr_plus`, 1,000 iterations, average
policy) at every grid depth and at three R settings. Its charts are labelled
"model chart": the postflop line is an assumption, not a solved game (DECISIONS 33).

- Version 1 (DECISIONS 34): one 3-bet size, R_oop 0.85, 0.90 and 0.95; the
  product answer uses 0.90.
- Version 2 (DECISIONS 49): 3-bets to 7.5 and 10, R per pot fitted to our own flop
  solves (`showdown.preflop_fit`); the product answer uses the fitted R, and the
  solves with every pot's R moved down and up 0.05 set "depends on R".
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

ROOT = Path(__file__).resolve().parents[2]
GRID: tuple[float, ...] = (25, 30, 40, 50, 60, 70, 80, 90, 100)
R_VALUES: tuple[float, ...] = (0.85, 0.90, 0.95)
R_PRODUCT = 0.90
SHIFT = 0.05
"""Version 2: "depends on R" compares the solves with every pot's R moved by −/+ this."""
SHIFTS: tuple[float, ...] = (-SHIFT, 0.0, SHIFT)
ITERATIONS = 1000
PUSHFOLD_MAX_BB = 20
DEFAULT_MATRIX = "data/preflop_169_exact.npz"
DEFAULT_MODEL = "data/preflop_model.json"
V1_MODEL = "data/preflop_model_v1.json"
LINE_ACTIONS = {"f": "fold", "c": "call", "r": "raise", "j": "all-in", "4": "raise 4x"}
POT_LINES = {"open": "rc", "3x": "rrc", "4x": "r4c"}
"""Version 2's pots that see a flop, by their preflop line."""


def v1_model_path() -> Path:
    """DECISIONS 34's model, which the older gates' tests are pinned to (DECISIONS 49).

    The re-solve moves it to `data/preflop_model_v1.json`; until then it is
    `data/preflop_model.json`.
    """
    moved = ROOT / V1_MODEL
    return moved if moved.exists() else ROOT / DEFAULT_MODEL


@dataclass
class DepthSolution:
    stack: float
    r_oop: float | None
    """Version 1's R; None in version 2."""
    raises: bool
    exploitability: float
    value_sb: float
    strategy: dict[str, dict[str, list[float]]]
    """node code -> class name -> probabilities, in `actions[node]` order."""
    actions: dict[str, list[str]]
    r: dict[str, float] | None = None
    """Version 2: the R solved with, per pot ("open", "3x", "4x")."""
    shift: float | None = None
    """Version 2: −0.05, 0 (the fitted R) or +0.05."""

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

    def more_often_3bet(self, pair_counts: np.ndarray) -> str:
        """Version 2: "3x" or "4x", the 3-bet the BB makes in more deals; ties go to 3x."""
        return "4x" if self.reach("r4", pair_counts) > self.reach("rr", pair_counts) else "3x"


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
    r_oop: float | None,
    iterations: int = ITERATIONS,
    matrix_path: str | Path = DEFAULT_MATRIX,
    raises: bool = True,
    r: dict[str, float] | None = None,
    shift: float | None = None,
) -> DepthSolution:
    """One solve: DECISIONS 34's tree at `r_oop`, or with `r` DECISIONS 49's at R per pot."""
    matrix = PreflopMatrix.load(matrix_path)
    if r is None:
        game = PreflopGame(stack, matrix, r_oop=r_oop, raises=raises)
    else:
        game = PreflopGame(stack, matrix, r=r)
    tree = compile_game(game)
    solver = cfr_plus(tree)
    solver.iterate(iterations)
    average = solver.average_policy()
    strategy, actions = read_strategy(tree, average)
    return DepthSolution(
        stack=float(stack),
        r_oop=None if r is not None else float(r_oop),
        raises=raises,
        exploitability=exploitability(tree, average),
        value_sb=policy_value(tree, average),
        strategy=strategy,
        actions=actions,
        r=None if r is None else dict(game.r),
        shift=shift,
    )


def _job(args: tuple) -> DepthSolution:
    return solve_depth(*args)


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _run(jobs: list[tuple], workers: int | None) -> list[DepthSolution]:
    workers = workers or min(len(jobs), os.cpu_count() or 1)
    if workers == 1:
        return [_job(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_job, jobs))


def encode_solution(s: DepthSolution) -> dict:
    out = {
        "stack": s.stack,
        "r_oop": s.r_oop,
        "raises": s.raises,
        "exploitability": s.exploitability,
        "value_sb": s.value_sb,
        "actions": s.actions,
        "strategy": s.strategy,
    }
    if s.r is not None:
        out |= {"r": s.r, "shift": s.shift}
    return out


def decode_solution(d: dict) -> DepthSolution:
    return DepthSolution(
        stack=float(d["stack"]),
        r_oop=None if d["r_oop"] is None else float(d["r_oop"]),
        raises=bool(d["raises"]),
        exploitability=float(d["exploitability"]),
        value_sb=float(d["value_sb"]),
        strategy=d["strategy"],
        actions=d["actions"],
        r=d.get("r"),
        shift=d.get("shift"),
    )


@dataclass
class PreflopModel:
    iterations: int
    matrix_path: str
    matrix_sha256: str
    solutions: list[DepthSolution] = field(default_factory=list)
    checks: list[DepthSolution] = field(default_factory=list)
    """Gate P's 20 bb solves: the jam-only continuity game and the full game at R 0.90."""
    version: int = 1
    r_fit: dict | None = None
    """Version 2: each fit cell's R, measured or a fallback, by pot and fit depth."""

    def at(self, stack: float, r_oop: float = R_PRODUCT, *, shift: float = 0.0) -> DepthSolution:
        """Version 1: the solve at `r_oop`. Version 2: the solve at the fitted R plus `shift`."""
        for s in self.solutions:
            if not np.isclose(s.stack, stack):
                continue
            if self.version == 1 and np.isclose(s.r_oop, r_oop):
                return s
            if self.version == 2 and np.isclose(s.shift, shift):
                return s
        setting = f"R {r_oop}" if self.version == 1 else f"shift {shift:+g}"
        raise KeyError(f"no solution at {stack} bb, {setting}")

    @property
    def r_label(self) -> str:
        """How the product answer's R is shown: "R 0.90", or "fitted R" (DECISIONS 49)."""
        return f"R {R_PRODUCT:.2f}" if self.version == 1 else "fitted R"

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
        """True when the most likely action differs between the low-R and high-R solves:
        R 0.85 and 0.95 (version 1), or the fitted R −0.05 and +0.05 (version 2)."""
        if self.version == 1:
            low, high = self.at(stack, 0.85), self.at(stack, 0.95)
        else:
            low, high = self.at(stack, shift=-SHIFT), self.at(stack, shift=SHIFT)
        low, high = low.probs(node, cls), high.probs(node, cls)
        return max(low, key=low.get) != max(high, key=high.get)

    def save(self, path: str | Path) -> None:
        payload = {"version": 2} if self.version == 2 else {}
        payload |= {
            "algorithm": "cfr+",
            "iterations": self.iterations,
            "matrix": self.matrix_path,
            "matrix_sha256": self.matrix_sha256,
        }
        if self.version == 2:
            payload |= {"shift": SHIFT, "r_fit": self.r_fit}
        payload |= {
            "solutions": [encode_solution(s) for s in self.solutions],
            "checks": [encode_solution(s) for s in self.checks],
        }
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8", newline="\n")

    @classmethod
    def load(cls, path: str | Path = DEFAULT_MODEL) -> PreflopModel:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            data["iterations"],
            data["matrix"],
            data["matrix_sha256"],
            [decode_solution(d) for d in data["solutions"]],
            [decode_solution(d) for d in data["checks"]],
            data.get("version", 1),
            data.get("r_fit"),
        )


def build(
    *,
    grid: tuple[float, ...] = GRID,
    r_values: tuple[float, ...] = R_VALUES,
    iterations: int = ITERATIONS,
    matrix_path: str | Path = DEFAULT_MATRIX,
    workers: int | None = None,
) -> PreflopModel:
    """DECISIONS 34: every grid solve, plus Gate P's two 20 bb check solves."""
    jobs = [(s, r, iterations, str(matrix_path), True) for r in r_values for s in grid]
    checks = [
        (20.0, R_PRODUCT, iterations, str(matrix_path), False),  # jam-only: continuity
        (20.0, R_PRODUCT, iterations, str(matrix_path), True),  # full game: sanity
    ]
    results = _run(checks + jobs, workers)
    return PreflopModel(
        iterations, str(matrix_path), _sha256(matrix_path), results[2:], results[:2]
    )


def shifted(r: dict[str, float], shift: float) -> dict[str, float]:
    """Every pot's R moved together (DECISIONS 49)."""
    return {pot: round(v + shift, 12) for pot, v in r.items()}


def build_fitted(
    r_by_depth: dict[float, dict[str, float]],
    r_fit: dict,
    *,
    iterations: int = ITERATIONS,
    matrix_path: str | Path = DEFAULT_MATRIX,
    workers: int | None = None,
) -> PreflopModel:
    """DECISIONS 49: three solves per grid depth (the fitted R, and −/+ 0.05), 27 in all."""
    jobs = [
        (d, None, iterations, str(matrix_path), True, shifted(r, s), s)
        for s in SHIFTS
        for d, r in sorted(r_by_depth.items())
    ]
    results = _run(jobs, workers)
    return PreflopModel(iterations, str(matrix_path), _sha256(matrix_path), results, [], 2, r_fit)
