"""The `showdown` command line.

showdown solve kuhn --algo cfr+ --iterations 1000
showdown solve leduc --iterations 200 --out data/strategies/leduc.json
showdown equity AsKs QQ --board Ts9s2d
showdown equity "TT+,AK" "22-99" --samples 200000
showdown matrix build --exact
showdown matrix show AKs QQ
showdown pushfold build
showdown pushfold chart 10
showdown pushfold exploit 10 --villain-calls 15
showdown play
showdown analyze data/external/phh/repo/data/pluribus
showdown advise --hero AsKd --seat sb --stack 50 --board Ts9s2d --pot 5
showdown advise --hero AhJs --seat bb --stack 60 --facing bb_vs_raise --pot 3.5 --to-call 1.5
showdown preflop chart 50
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import webbrowser
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from showdown import pushfold
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
from showdown.live.spot import PREFLOP_SPOTS

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
        text = json.dumps(payload, indent=1, sort_keys=True) + "\n"
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"\nwrote {out}")
    return 0


DEFAULT_MATRIX = "data/preflop_169.npz"
DEFAULT_EXACT_MATRIX = "data/preflop_169_exact.npz"


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
    if args.exact:
        out = args.out or DEFAULT_EXACT_MATRIX
        result = preflop_matrix.build_exact(workers=args.workers)
        result.save(out)
        print(
            f"wrote {out}: exact, all {result.boards:,} boards, {time.perf_counter() - start:.0f} s"
        )
        return 0
    args.out = args.out or DEFAULT_MATRIX
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
    error = "exact" if loaded.method == "exact" else f"+/- {se:.5f} (1 SE)"
    print(f"{args.row} vs {args.col}: equity {equity:.5f} {error}, {pairs} combo pairs")
    return 0


def _pushfold_build(args: argparse.Namespace) -> int:
    if args.iterations < 1:
        raise SystemExit("--iterations must be at least 1")
    start = time.perf_counter()
    solution = pushfold.solve_all(
        pushfold.DEPTHS, args.iterations, args.matrix, workers=args.workers
    )
    solution.save(args.out)
    print(f"cfr+, {args.iterations} iterations per depth, payoffs {args.matrix}")
    print(f"{'stack':>6}  {'exploitability':>14}  {'SB value':>9}  {'SB jams':>8}  {'BB calls':>8}")
    for d in solution.depths:
        print(
            f"{d.stack:>6g}  {d.exploitability:>14.2e}  {d.value_sb:>+9.5f}  "
            f"{d.push_share():>8.1%}  {d.call_share():>8.1%}"
        )
    print(f"wrote {args.out} in {time.perf_counter() - start:.0f} s")
    return 0


def _pushfold_chart(args: argparse.Namespace) -> int:
    result = pushfold.PushFoldSolution.load(args.file).at(args.stack)
    print(
        f"{result.stack:g} bb effective: SB value {result.value_sb:+.5f} bb, "
        f"exploitability {result.exploitability:.2e} bb"
    )
    print()
    print(f"SB jams {result.push_share():.1%} of hands; cells are % of the time, suited above")
    print(pushfold.chart(result.push))
    print()
    print(f"BB calls a jam with {result.call_share():.1%} of hands")
    print(pushfold.chart(result.call))
    return 0


def _pushfold_exploit(args: argparse.Namespace) -> int:
    from showdown.exploit import exploit, report

    solution = pushfold.PushFoldSolution.load(args.file)
    matrix = preflop_matrix.PreflopMatrix.load(solution.matrix_path)
    try:
        e = exploit(
            solution,
            matrix,
            args.stack,
            villain_calls=args.villain_calls,
            villain_jams=args.villain_jams,
        )
    except ValueError as error:
        raise SystemExit(f"bad read: {error}") from None
    print(report(e))
    return 0


def _play(args: argparse.Namespace) -> int:
    from showdown.bot.policy import LeducStrategy, PushFoldStrategy
    from showdown.bot.server import App, PlayServer

    app = App(PushFoldStrategy.load(args.pushfold), LeducStrategy.load(args.leduc))
    server = PlayServer(app, args.port)
    print(f"showdown play: {server.url}  (127.0.0.1 only; Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(server.url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    finally:
        server.server_close()
    return 0


def _fmt(value: float, digits: int = 1) -> str:
    return "-" if value != value else f"{value:.{digits}f}"  # NaN when there is no denominator


def _analyze(args: argparse.Namespace) -> int:
    from collections import Counter

    from showdown.bot.policy import PushFoldStrategy
    from showdown.hh.grade import grade_hand
    from showdown.hh.parse import load
    from showdown.hh.stats import analyze

    start = time.perf_counter()
    parsed = load(args.paths, args.format)
    if not parsed.found:
        print("no hand histories found")
        return 1
    share = parsed.parsed / parsed.found
    print(f"hands found {parsed.found:,}, parsed {parsed.parsed:,} ({share:.2%})")
    if parsed.odd_chip:
        print(f"  {parsed.odd_chip} parsed with an odd-chip split (DECISIONS 25)")
    for source, reason in parsed.failures[: args.show_failures]:
        print(f"  FAILED {source}: {reason}")
    if len(parsed.failures) > args.show_failures:
        print(f"  ... and {len(parsed.failures) - args.show_failures} more failures")
    if not parsed.records:
        return 1

    report, _ = analyze(parsed.records, samples=args.samples, seed=args.seed)
    rows = sorted(report.players.values(), key=lambda s: (-s.hands, s.name))
    if args.player:
        rows = [s for s in rows if s.name in args.player]
    print()
    print(
        f"{'player':<16}{'hands':>7}{'VPIP':>7}{'PFR':>7}{'3bet':>7}{'WTSD':>7}"
        f"{'W$SD':>7}{'bb/100':>9}{'EV bb/100':>11}"
    )
    for s in rows:
        se = f" +/-{s.ev_bb_per_100_se:.2f}" if s.ev_se_bb_sq > 0 else ""
        print(
            f"{s.name[:15]:<16}{s.hands:>7,}{_fmt(s.vpip_pct):>7}{_fmt(s.pfr_pct):>7}"
            f"{_fmt(s.three_bet_pct):>7}{_fmt(s.wtsd_pct):>7}{_fmt(s.wsd_pct):>7}"
            f"{_fmt(s.bb_per_100, 2):>9}{_fmt(s.ev_bb_per_100, 2):>11}{se}"
        )
    print()
    print(
        f"all-in EV: {report.allin_hands} all-in hands; adjusted {report.allin_exact} exactly"
        f" and {report.allin_monte_carlo} by Monte Carlo ({args.samples:,} runouts, seed"
        f" {args.seed}); {report.allin_multiway} multiway;"
        f" {report.allin_unknown_cards} not adjusted (unknown cards)"
    )

    strategy = PushFoldStrategy.load(args.pushfold)
    reasons: Counter[str] = Counter()
    graded: dict[str, list] = {}
    for record in parsed.records:
        result = grade_hand(record, strategy)
        if result.reason:
            reasons[result.reason] += 1
        for d in result.decisions:
            graded.setdefault(d.player, []).append(d)
    print()
    gradable = parsed.parsed - sum(reasons.values())
    print(f"push/fold grading (DECISIONS 27): {gradable} gradable hands")
    for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  not gradable, {reason}: {count}")
    for player, decisions in sorted(graded.items()):
        if args.player and player not in args.player:
            continue
        lost = sum(d.loss for d in decisions)
        mistakes = sum(d.mistake for d in decisions)
        print(f"  {player}: {len(decisions)} decisions, {mistakes} mistakes, {lost:.3f} bb lost")
    print()
    print(f"{time.perf_counter() - start:.0f} s")
    return 0


def _advise(args: argparse.Namespace) -> int:
    from showdown.live.advisor import Advisor
    from showdown.live.spot import Spot, SpotError

    try:
        spot = Spot.parse(
            args.hero,
            args.board or "",
            seat=args.seat,
            effective_bb=args.stack,
            pot_bb=args.pot,
            to_call_bb=args.to_call,
            pot_type=args.pot_type,
            preflop=args.facing,
            villain_range=args.villain,
            villain_top=args.villain_top,
            mode=args.mode,
        )
    except (SpotError, ValueError) as error:
        raise SystemExit(f"bad spot: {error}") from None
    advisor = Advisor.load(ranges=args.ranges, log_path=None if args.no_log else args.log)
    try:
        s = advisor.suggest(spot)
    except SpotError as error:
        raise SystemExit(f"bad spot: {error}") from None
    print(
        f"{s.street}: {(s.action or 'no action hint').upper()}"
        + (f" {s.size_bb:g} bb" if s.size_bb else "")
    )
    if s.evs:
        print("  EV (bb): " + ", ".join(f"{k} {v:+.3f}" for k, v in s.evs.items()))
    if s.mix:
        print("  mix: " + ", ".join(f"{k} {v:.0%}" for k, v in s.mix.items()))
    for note in s.notes:
        print(f"  ! {note}")
    if s.equity is not None:
        se = f" +/- {s.se:.3f}" if s.se else ""
        print(f"  equity {s.equity:.1%}{se} vs {s.villain_range}")
    if s.threshold is not None:
        print(f"  threshold {s.threshold:.1%}")
    print(f"  {s.source}; {s.elapsed_ms:.0f} ms")
    return 0


def _preflop_build(args: argparse.Namespace) -> int:
    from showdown import preflop_model

    start = time.perf_counter()
    model = preflop_model.build(iterations=args.iterations, workers=args.workers)
    model.save(args.out)
    print(f"cfr+, {args.iterations} iterations; grid {list(preflop_model.GRID)}")
    print(f"{'stack':>6} {'R':>5} {'exploitability':>15} {'SB value':>9}")
    for s in model.checks + model.solutions:
        kind = "" if s.raises else "  (jam-only)"
        print(f"{s.stack:>6g} {s.r_oop:>5.2f} {s.exploitability:>15.2e} {s.value_sb:>+9.4f}{kind}")
    print(f"wrote {args.out} in {time.perf_counter() - start:.0f} s")
    return 0


def _preflop_chart(args: argparse.Namespace) -> int:
    from showdown import preflop_model
    from showdown.equity.cards import RANKS

    model = preflop_model.PreflopModel.load(args.file)
    depth = model.depth_for(args.stack)
    if depth is None:
        raise SystemExit("20 bb or less uses push/fold: showdown pushfold chart")
    s = model.at(depth, args.r)
    if args.node not in s.actions:
        raise SystemExit(f"node must be one of {sorted(s.actions)}")
    letters = {"fold": "F", "call": "C", "raise": "R", "all-in": "J"}
    print(f"model chart, R {args.r:.2f}, {depth:g} bb, node {args.node!r}: most likely action")
    print("(suited above the diagonal; lower case = mixed below 90%; * = depends on R)")
    labels = RANKS[::-1]
    print("     " + "".join(f"{r:>4}" for r in labels))
    for row in range(13):
        cells = []
        for col in range(13):
            cls = 13 * row + col
            probs = s.probs(args.node, cls)
            best = max(probs, key=probs.get)
            mark = letters[best] if probs[best] >= 0.9 else letters[best].lower()
            if model.depends_on_r(depth, args.node, cls):
                mark += "*"
            cells.append(f"{mark:>4}")
        print(f"  {labels[row]}  " + "".join(cells))
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
    build = matrix_commands.add_parser(
        "build", help="build the matrix: Monte Carlo, or exact with --exact (minutes, all cores)"
    )
    build.add_argument("--exact", action="store_true", help="enumerate every board (DECISIONS 21)")
    build.add_argument("--boards-per-batch", type=int, default=2300)
    build.add_argument("--batches", type=int, default=64)
    build.add_argument("--seed", type=int, default=20261114)
    build.add_argument("--workers", type=int, help="processes (default: all cores)")
    build.add_argument("--out", help=f"default {DEFAULT_MATRIX}, or {DEFAULT_EXACT_MATRIX}")
    build.set_defaults(handler=_matrix_build)
    show = matrix_commands.add_parser("show", help="one cell, e.g. AKs QQ")
    show.add_argument("row")
    show.add_argument("col")
    show.add_argument("--file", default=DEFAULT_EXACT_MATRIX)
    show.set_defaults(handler=_matrix_show)

    pf = commands.add_parser("pushfold", help="heads-up push/fold solutions at 1 to 20 bb")
    pf_commands = pf.add_subparsers(dest="pushfold_command", required=True)
    pf_build = pf_commands.add_parser("build", help="solve 1 to 20 bb with CFR+ (DECISIONS 22)")
    pf_build.add_argument("--iterations", type=int, default=pushfold.ITERATIONS)
    pf_build.add_argument("--workers", type=int, help="processes (default: one per depth)")
    pf_build.add_argument("--matrix", default=pushfold.DEFAULT_MATRIX)
    pf_build.add_argument("--out", default=pushfold.DEFAULT_SOLUTION)
    pf_build.set_defaults(handler=_pushfold_build)
    pf_chart = pf_commands.add_parser("chart", help="13x13 SB and BB charts at one depth")
    pf_chart.add_argument("stack", type=float, help="effective stack in bb, before blinds")
    pf_chart.add_argument("--file", default=pushfold.DEFAULT_SOLUTION)
    pf_chart.set_defaults(handler=_pushfold_chart)
    pf_exploit = pf_commands.add_parser(
        "exploit", help="best response to a read, its gain and its risk (DECISIONS 37)"
    )
    pf_exploit.add_argument("stack", type=float, help="effective stack in bb, before blinds")
    read = pf_exploit.add_mutually_exclusive_group(required=True)
    read.add_argument(
        "--villain-calls", type=float, metavar="N", help="you are the SB; the BB calls the top N%%"
    )
    read.add_argument(
        "--villain-jams", type=float, metavar="N", help="you are the BB; the SB jams the top N%%"
    )
    pf_exploit.add_argument("--file", default=pushfold.DEFAULT_SOLUTION)
    pf_exploit.set_defaults(handler=_pushfold_exploit)

    play = commands.add_parser("play", help="local browser page: push/fold trainer and Leduc")
    play.add_argument("--port", type=int, default=0, help="default: any free port")
    play.add_argument("--no-browser", action="store_true", help="print the URL only")
    play.add_argument("--pushfold", default=pushfold.DEFAULT_SOLUTION)
    play.add_argument("--leduc", default="data/leduc_cfr_plus.json")
    play.set_defaults(handler=_play)

    analyze_cmd = commands.add_parser(
        "analyze", help="stats, all-in EV and push/fold grading for hand histories"
    )
    analyze_cmd.add_argument("paths", nargs="+", help="PHH or PokerStars files, or directories")
    analyze_cmd.add_argument("--format", choices=["auto", "phh", "pokerstars"], default="auto")
    analyze_cmd.add_argument("--player", action="append", help="only these players (repeatable)")
    analyze_cmd.add_argument("--samples", type=int, default=20_000, help="Monte Carlo runouts")
    analyze_cmd.add_argument("--seed", type=int, default=0)
    analyze_cmd.add_argument("--show-failures", type=int, default=20)
    analyze_cmd.add_argument("--pushfold", default=pushfold.DEFAULT_SOLUTION)
    analyze_cmd.set_defaults(handler=_analyze)

    advise = commands.add_parser(
        "advise", help="one live suggestion: push/fold or model chart preflop, equity postflop"
    )
    advise.add_argument("--hero", required=True, help="your two cards, e.g. AsKd")
    advise.add_argument("--seat", choices=["sb", "bb"], required=True)
    advise.add_argument("--stack", type=float, required=True, help="effective stack in bb")
    advise.add_argument("--board", help="e.g. Ts9s2d")
    advise.add_argument("--pot", type=float, default=1.5, help="pot in bb, incl. a bet faced")
    advise.add_argument("--to-call", type=float, default=0.0, help="bb to call; 0 = can check")
    advise.add_argument("--pot-type", choices=["srp", "3bp"], default="srp")
    advise.add_argument(
        "--facing",
        choices=PREFLOP_SPOTS,
        default="sb_first",
        help="preflop decision; a raise faced is read from --pot and --to-call",
    )
    advise.add_argument(
        "--ranges",
        choices=["model", "fixed"],
        default="model",
        help="default postflop villain range: the preflop model's, or fixed top-%%",
    )
    advise.add_argument("--villain", help="custom villain range, e.g. 'TT+,AQs+'")
    advise.add_argument(
        "--villain-top", type=float, help="custom villain range: the top N%% of hands"
    )
    advise.add_argument("--mode", choices=["hint", "equity"], default="hint")
    advise.add_argument("--log", default="data/live/advice.jsonl")
    advise.add_argument("--no-log", action="store_true")
    advise.set_defaults(handler=_advise)

    pre = commands.add_parser("preflop", help="the preflop model above 20 bb (DECISIONS 33, 34)")
    pre_commands = pre.add_subparsers(dest="preflop_command", required=True)
    pre_build = pre_commands.add_parser("build", help="solve the grid at R 0.85/0.90/0.95 (hours)")
    pre_build.add_argument("--iterations", type=int, default=1000)
    pre_build.add_argument("--workers", type=int, help="processes (about 200 MB each)")
    pre_build.add_argument("--out", default="data/preflop_model.json")
    pre_build.set_defaults(handler=_preflop_build)
    pre_chart = pre_commands.add_parser("chart", help="13x13 most-likely-action chart")
    pre_chart.add_argument("stack", type=float, help="effective stack in bb")
    pre_chart.add_argument("--node", default="", help="'' first in, r, rr, rrj, rj, j")
    pre_chart.add_argument("--r", type=float, default=0.9)
    pre_chart.add_argument("--file", default="data/preflop_model.json")
    pre_chart.set_defaults(handler=_preflop_chart)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
