"""The `showdown` command line.

showdown solve kuhn --algo cfr+ --iterations 1000
showdown solve leduc --iterations 200 --out data/strategies/leduc.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from showdown.cfr import (
    CFRSolver,
    cfr,
    cfr_plus,
    compile_game,
    exploitability,
    policy_to_dict,
    policy_value,
)
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
