"""The `showdown` command line.

showdown solve kuhn --algo cfr+ --iterations 1000
showdown solve leduc --iterations 200 --out data/strategies/leduc.json
showdown equity AsKs QQ --board Ts9s2d
showdown equity "TT+,AK" "22-99" --samples 200000
showdown matrix build
showdown matrix show AKs QQ
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from showdown.cfr import (
    CFRSolver,
    cfr,
    cfr_plus,
    compile_game,
    exploitability,
    policy_to_dict,
    policy_value,
)
from showdown.equity import matrix as preflop_matrix
from showdown.equity.cards import cards_str, class_index, parse_cards
from showdown.equity.exact import range_vs_range
from showdown.equity.montecarlo import monte_carlo
from showdown.equity.ranges import parse_range
from showdown.games import GAMES, load_game

_ALGORITHMS = {"cfr": cfr, "cfr+": cfr_plus}
_MAX_PRINTED_INFOSETS = 60


def _report_points(iterations: int, every: int | None) -> list[int]:
    if every:
        points = list(range(every, iterations + 1, every))
    else:
        points = [10**k for k in range(0, 9) if 10**k < iterations]
    if not points or points[-1] != iterations:
        points.append(iterations)
    return points


def _solve(args: argparse.Namespace) -> int:
    if args.iterations < 1:
        raise SystemExit("--iterations must be at least 1")
    tree = compile_game(load_game(args.game))
    solver: CFRSolver = _ALGORITHMS[args.algo](tree)
    print(
        f"{args.game}: {tree.num_nodes} nodes, {tree.num_infosets} infosets, "
        f"{args.algo}, {args.iterations} iterations"
    )
    print(f"{'iteration':>10}  {'exploitability':>15}  {'value p0':>10}  {'seconds':>8}")
    start = time.perf_counter()
    done = 0
    for point in _report_points(args.iterations, args.every):
        solver.iterate(point - done)
        done = point
        average = solver.average_policy()
        elapsed = time.perf_counter() - start
        print(
            f"{point:>10}  {exploitability(tree, average):>15.8f}  "
            f"{policy_value(tree, average):>10.6f}  {elapsed:>8.2f}"
        )

    average = solver.average_policy()
    table = policy_to_dict(tree, average)
    if args.show_policy or tree.num_infosets <= _MAX_PRINTED_INFOSETS:
        print()
        width = max(len(k) for k in table)
        for key in sorted(table):
            probs = "  ".join(f"{a} {p:.3f}" for a, p in table[key].items())
            print(f"  {key:<{width}}  {probs}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "game": args.game,
            "algorithm": args.algo,
            "iterations": args.iterations,
            "exploitability": exploitability(tree, average),
            "value_player0": policy_value(tree, average),
            "policy": table,
        }
        out.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nwrote {out}")
    return 0


DEFAULT_MATRIX = "data/preflop_169.npz"


def _equity(args: argparse.Namespace) -> int:
    hero, villain = parse_range(args.hero), parse_range(args.villain)
    board = parse_cards(args.board) if args.board else ()
    where = f" on {cards_str(board)}" if board else " preflop"
    print(f"{args.hero} ({len(hero)} combos) vs {args.villain} ({len(villain)} combos){where}")
    method = args.method
    if method == "auto":
        single = len(hero) == 1 and len(villain) == 1
        method = "exact" if single or len(board) >= 3 else "mc"
    if method == "exact":
        try:
            result = range_vs_range(hero, villain, board)
        except ValueError as error:
            if args.method == "exact":
                raise SystemExit(str(error)) from None
            print(f"  ({error}; falling back to Monte Carlo)")
        else:
            print(
                f"  exact: equity {result.equity:.5f}  (win {result.win:.5f}, "
                f"tie {result.tie:.5f}) over {result.outcomes:,} outcomes"
            )
            return 0
    estimate = monte_carlo(hero, villain, board, samples=args.samples, seed=args.seed)
    print(
        f"  monte carlo: equity {estimate.equity:.5f} +/- {estimate.se:.5f} (1 SE), "
        f"{estimate.samples:,} samples, seed {args.seed}"
    )
    return 0


def _matrix_build(args: argparse.Namespace) -> int:
    start = time.perf_counter()
    result = preflop_matrix.build(
        boards_per_batch=args.boards_per_batch,
        batches=args.batches,
        seed=args.seed,
        workers=args.workers,
    )
    result.save(args.out)
    off_diagonal = result.se[~np.eye(169, dtype=bool)]
    print(
        f"wrote {args.out}: {result.boards:,} boards in {result.batches} batches, "
        f"seed {args.seed}, {time.perf_counter() - start:.0f} s; "
        f"max SE {off_diagonal.max():.5f}"
    )
    return 0


def _matrix_show(args: argparse.Namespace) -> int:
    loaded = preflop_matrix.PreflopMatrix.load(args.file)
    equity, se = loaded.cell(args.row, args.col)
    pairs = int(loaded.pair_counts[class_index(args.row), class_index(args.col)])
    print(f"{args.row} vs {args.col}: equity {equity:.5f} +/- {se:.5f} (1 SE), {pairs} combo pairs")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="showdown", description="Heads-up poker lab.")
    commands = parser.add_subparsers(dest="command", required=True)

    solve = commands.add_parser("solve", help="run CFR on a small game")
    solve.add_argument("game", choices=sorted(GAMES))
    solve.add_argument("--algo", choices=sorted(_ALGORITHMS), default="cfr+")
    solve.add_argument("--iterations", type=int, default=1000)
    solve.add_argument(
        "--every", type=int, help="report every N iterations (default: powers of 10)"
    )
    solve.add_argument("--out", help="write the average policy and its numbers as JSON")
    solve.add_argument("--show-policy", action="store_true", help="print the policy even if large")
    solve.set_defaults(handler=_solve)

    equity = commands.add_parser("equity", help="heads-up equity of a hand or range")
    equity.add_argument("hero", help="hand or range, e.g. AsKs or 'TT+,AK'")
    equity.add_argument("villain")
    equity.add_argument("--board", help="board cards, e.g. Ts9s2d")
    equity.add_argument("--method", choices=["auto", "exact", "mc"], default="auto")
    equity.add_argument("--samples", type=int, default=200_000)
    equity.add_argument("--seed", type=int, default=0)
    equity.set_defaults(handler=_equity)

    matrix = commands.add_parser("matrix", help="the 169x169 preflop equity matrix")
    matrix_commands = matrix.add_subparsers(dest="matrix_command", required=True)
    build = matrix_commands.add_parser("build", help="estimate the matrix (minutes, all cores)")
    build.add_argument("--boards-per-batch", type=int, default=2300)
    build.add_argument("--batches", type=int, default=64)
    build.add_argument("--seed", type=int, default=20261114)
    build.add_argument("--workers", type=int, help="processes (default: all cores)")
    build.add_argument("--out", default=DEFAULT_MATRIX)
    build.set_defaults(handler=_matrix_build)
    show = matrix_commands.add_parser("show", help="one cell, e.g. AKs QQ")
    show.add_argument("row")
    show.add_argument("col")
    show.add_argument("--file", default=DEFAULT_MATRIX)
    show.set_defaults(handler=_matrix_show)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
