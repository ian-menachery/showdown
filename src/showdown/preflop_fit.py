"""R fitted to our own flop solves, for the preflop re-solve (DECISIONS 49, SCOPE A10).

R is the share of its flop equity the BB, out of position, turns into EV once the flop is
played. On one flop, R = EV_BB / (pot × E_BB):
- EV_BB is the flop bridge's root EV for the BB (`root_ev[0]`, in chips, counting the pot
  it wins);
- E_BB is the BB's range equity at the root, from a report at the root path `[]`.

A cell is a pot (the open, the 3× 3-bet, the 4× 3-bet) at a fit depth (25, 50, 100 bb). Its
R is the mean over 20 flops drawn with seed 20261119, solved with the flop bridge (tree T1,
2% target, at most 1,000 iterations; DECISIONS 40) on each seat's model weights along the
pot's line. There are two rounds: round 1 solves the new tree at R 0.90 for every pot,
round 2 at round 1's R. `showdown preflop fit-r --round N` runs one round and writes
`data/preflop_r_fit.json`; bridge outputs and the rounds' preflop solves are cached under
`data/external/`. The bridge runs as a separate process (DECISIONS 29).
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from showdown import preflop_model as pm
from showdown.equity.cards import cards_str
from showdown.equity.matrix import PreflopMatrix
from showdown.games.preflop import POTS
from showdown.postflop import bridge, library
from showdown.postflop.spot import CHIPS_PER_BB, SETTINGS, TREE_T1, range_text

FIT_DEPTHS: tuple[int, ...] = (25, 50, 100)
R_START = 0.90
SEED = 20261119
FLOPS = 20
REACH_MIN = 0.001
"""DECISIONS 35's rule: a pot the round's model reaches in under 0.1% of deals is not measured."""
FIT_PATH = pm.ROOT / "data" / "preflop_r_fit.json"
CACHE = bridge.EXTERNAL / "cache" / "r-fit"
SOLVES = pm.ROOT / "data" / "external" / "preflop-fit"
"""The rounds' preflop solves, cached by their inputs."""
ROOT_REPORT = [[]]


class FitError(RuntimeError):
    """The fit cannot start or continue."""


def fit_flops() -> list[str]:
    """20 flops, uniform without replacement over all 22,100, seed 20261119; high card first."""
    flops = random.Random(SEED).sample(list(itertools.combinations(range(52), 3)), FLOPS)
    return [cards_str(sorted(f, reverse=True)) for f in flops]


def flop_spec(solution: pm.DepthSolution, pot: str, flop: str) -> dict:
    """The flop bridge's spot for one cell and flop: pot 2c, stack d − c, the line's ranges."""
    c = POTS[pot]
    sb, bb = solution.line_factors(pm.POT_LINES[pot])
    return {
        "oop_range": range_text(bb),
        "ip_range": range_text(sb),
        "flop": flop,
        "starting_pot": round(2 * c * CHIPS_PER_BB),
        "effective_stack": round((solution.stack - c) * CHIPS_PER_BB),
        **TREE_T1,
        **SETTINGS,
        "locks": [],
        "report": ROOT_REPORT,
    }


def measure_r(result: dict, pot_chips: int) -> dict:
    """R on one flop, from the bridge's root EV and its report at the root."""
    roots = [r for r in result.get("reports", []) if r.get("path") == []]
    root = roots[0] if len(roots) == 1 else {}
    if not root.get("reached") or root.get("player") != 0 or "equity" not in root:
        raise FitError(
            "the flop bridge did not report the BB's root equity: stop and ask Ian (DECISIONS 49)"
        )
    w = np.asarray(root["weights"], dtype=float)
    e = np.asarray(root["equity"], dtype=float)
    e_bb = float(w @ e / w.sum())
    ev = float(result["root_ev"][0])
    return {"ev_bb": ev, "e_bb": e_bb, "r": ev / (pot_chips * e_bb)}


def summarize(values: list[float]) -> tuple[float, float]:
    """A cell's R and its standard error: the mean, and sd / √n with the sample sd."""
    x = np.asarray(values, dtype=float)
    return float(x.mean()), float(x.std(ddof=1) / np.sqrt(len(x)))


def fill(cells: dict[str, dict[int, dict]]) -> None:
    """Unmeasured cells take the same pot's R from the nearest measured fit depth, or 0.90."""
    for pot, by_depth in cells.items():
        measured = [d for d in FIT_DEPTHS if by_depth[d]["measured"]]
        for d in FIT_DEPTHS:
            cell = by_depth[d]
            if cell["measured"]:
                continue
            if measured:
                source = min(measured, key=lambda m: (abs(m - d), m))
                cell["r"] = by_depth[source]["r"]
                cell["source"] = f"fallback: the {pot} pot's R at {source} bb"
            else:
                cell["r"] = R_START
                cell["source"] = f"fallback: {R_START:.2f}, no depth measured the {pot} pot"


def grid_r(cells: dict[str, dict[int, dict]], depth: float) -> dict[str, float]:
    """R per pot at a grid depth: a straight line in depth between the fit depths."""
    return {
        pot: float(np.interp(depth, FIT_DEPTHS, [cells[pot][d]["r"] for d in FIT_DEPTHS]))
        for pot in POTS
    }


# --- the file ----------------------------------------------------------------------------


def _cells_out(cells: dict[str, dict[int, dict]]) -> dict:
    return {pot: {str(d): cell for d, cell in by.items()} for pot, by in cells.items()}


def _cells_in(stored: dict) -> dict[str, dict[int, dict]]:
    return {pot: {int(d): cell for d, cell in by.items()} for pot, by in stored.items()}


def load(path: Path = FIT_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def round_cells(data: dict, n: int) -> dict[str, dict[int, dict]]:
    """Round `n`'s cells (1 or 2), every one with its R, measured or a fallback."""
    rounds = data.get("rounds", [])
    if len(rounds) < n:
        raise FitError(f"round {n} of the R fit has not run: showdown preflop fit-r --round {n}")
    return _cells_in(rounds[n - 1]["cells"])


def product_r(data: dict) -> tuple[dict[float, dict[str, float]], dict]:
    """The product solve's R per grid depth from round 2, and the cells stored with the model."""
    cells = round_cells(data, 2)
    stored = {
        pot: {
            str(d): {k: c[k] for k in ("r", "measured", "se", "source") if k in c}
            for d, c in by.items()
        }
        for pot, by in cells.items()
    }
    return {float(g): grid_r(cells, g) for g in pm.GRID}, stored


# --- a round -----------------------------------------------------------------------------


def _solve_cached(
    jobs: dict[int, dict[str, float]], matrix_path: str, workers: int | None, log
) -> dict[int, pm.DepthSolution]:
    """The round's preflop solves at its fit depths, reused when the same inputs ran before."""
    sha = hashlib.sha256((pm.ROOT / matrix_path).read_bytes()).hexdigest()
    paths, out = {}, {}
    for d, r in jobs.items():
        key = json.dumps({"stack": d, "r": r, "iterations": pm.ITERATIONS, "matrix": sha})
        paths[d] = SOLVES / (hashlib.sha256(key.encode()).hexdigest() + ".json")
        if paths[d].exists():
            out[d] = pm.decode_solution(json.loads(paths[d].read_text(encoding="utf-8")))
    todo = [d for d in jobs if d not in out]
    if todo:
        log(f"preflop solves at {todo} bb, {pm.ITERATIONS} iterations each...")
        start = time.perf_counter()
        args = [(d, None, pm.ITERATIONS, matrix_path, True, jobs[d], 0.0) for d in todo]
        for d, s in zip(todo, pm._run(args, workers), strict=True):
            SOLVES.mkdir(parents=True, exist_ok=True)
            paths[d].write_text(json.dumps(pm.encode_solution(s)), encoding="utf-8")
            out[d] = s
        log(f"preflop solves done in {time.perf_counter() - start:.0f} s")
    return out


def run_round(
    n: int,
    *,
    path: Path = FIT_PATH,
    matrix_path: str = pm.DEFAULT_MATRIX,
    workers: int | None = None,
    on_ac: Callable[[], bool] = library.on_ac_power,
    log: Callable[[str], None] = print,
) -> dict:
    """Run round `n` (1 or 2) and write the fit file; returns its contents."""
    if n not in (1, 2):
        raise FitError("the fit has two rounds: 1 and 2")
    data = load(path) if Path(path).exists() else {}
    if n == 1:
        start_r = {d: dict.fromkeys(POTS, R_START) for d in FIT_DEPTHS}
    else:
        before = round_cells(data, 1)
        start_r = {d: {p: before[p][d]["r"] for p in POTS} for d in FIT_DEPTHS}
    if not on_ac():
        raise FitError("not on AC power: plug in before a fit run")
    flops = fit_flops()
    binary = bridge.binary_sha256()
    library._keep_awake(True)
    try:
        solutions = _solve_cached(start_r, matrix_path, workers, log)
        pairs = PreflopMatrix.load(pm.ROOT / matrix_path).pair_counts
        cells: dict[str, dict[int, dict]] = {p: {} for p in POTS}
        for d in FIT_DEPTHS:
            for pot in POTS:
                reach = solutions[d].reach(pm.POT_LINES[pot], pairs)
                cell = {"reach": reach, "measured": reach >= REACH_MIN}
                if cell["measured"]:
                    cell["flops"] = []
                    for flop in flops:
                        if not on_ac():
                            raise FitError("stopping: the laptop went on battery; rerun to resume")
                        spec = flop_spec(solutions[d], pot, flop)
                        result = bridge.solve(spec, cache=CACHE)
                        row = {"flop": flop, **measure_r(result, spec["starting_pot"])}
                        row |= {k: result[k] for k in ("exploitability_pct", "iterations")}
                        row["seconds"] = result["build_s"] + result["solve_s"]
                        cell["flops"].append(row)
                        log(f"round {n} {pot} {d} bb {flop}: R {row['r']:.4f}")
                    cell["r"], cell["se"] = summarize([x["r"] for x in cell["flops"]])
                    cell["source"] = "measured"
                    log(f"round {n} {pot} {d} bb: R {cell['r']:.4f} (SE {cell['se']:.4f})")
                else:
                    log(f"round {n} {pot} {d} bb: reached in {reach:.4%} of deals, not measured")
                cells[pot][d] = cell
        fill(cells)
    finally:
        library._keep_awake(False)
    record = {
        "round": n,
        "preflop_r": {str(d): r for d, r in start_r.items()},
        "preflop": {
            str(d): {"exploitability": s.exploitability, "value_sb": s.value_sb}
            for d, s in solutions.items()
        },
        "cells": _cells_out(cells),
    }
    data = {
        "decisions": 49,
        "seed": SEED,
        "flops": flops,
        "binary": binary,
        "tree": TREE_T1,
        "settings": SETTINGS,
        "iterations": pm.ITERATIONS,
        "rounds": [*data.get("rounds", [])[: n - 1], record],
    }
    Path(path).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")
    return data
