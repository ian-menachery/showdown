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
showdown postflop exploit --stack 50 --flop Kc7d6c --hero sb --read never-folds
showdown postflop library build --spot 3BP100 --until 07:00
showdown play
showdown analyze data/external/phh/repo/data/pluribus
showdown advise --hero AsKd --seat sb --stack 50 --board Ts9s2d --pot 5
showdown advise --hero AhJs --seat bb --stack 60 --facing bb_vs_raise --pot 3.5 --to-call 1.5
showdown preflop chart 50
showdown preflop fit-r --round 1
showdown preflop build
showdown capture
showdown live --screen
showdown sixmax BTN A5s --limpers 2 --ante 0.5 --profile loose-passive
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
        pushfold.DEPTHS, args.iterations, args.matrix, workers=args.workers, ante=args.ante
    )
    solution.save(args.out)
    print(
        f"cfr+, {args.iterations} iterations per depth, payoffs {args.matrix}, ante {args.ante:g}"
    )
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


def _postflop_build(args: argparse.Namespace) -> int:
    from showdown.postflop import bridge

    try:
        exe = bridge.build()
    except bridge.BridgeError as error:
        raise SystemExit(str(error)) from None
    print(f"built {exe}")
    print(f"sha256 {bridge.binary_sha256()}")
    return 0


def _postflop_exploit(args: argparse.Namespace) -> int:
    from showdown.postflop import bridge, exploit
    from showdown.postflop.spot import FlopSpot, SpotError

    try:
        spot = FlopSpot.make(args.pot_type, args.stack, args.flop)
    except (SpotError, ValueError) as error:
        raise SystemExit(f"bad spot: {error}") from None
    print("solving twice (without and with the read); this takes a few minutes...", flush=True)
    try:
        result = exploit.run(spot, args.hero, args.read)
    except bridge.BridgeError as error:
        raise SystemExit(str(error)) from None
    print(exploit.report_text(result))
    return 0


def _library_build(args: argparse.Namespace) -> int:
    import datetime as dt

    from showdown.postflop import bridge, library

    try:
        until = library.deadline(args.until, dt.datetime.now()) if args.until else None
    except ValueError:
        raise SystemExit(f"bad --until {args.until!r}: use HH:MM, like 07:00") from None
    print(f"building {args.spot}" + (f" until {until:%a %H:%M}" if until else ""), flush=True)
    try:
        library.build(args.spot, until=until, log=lambda line: print(line, flush=True))
    except (library.LibraryError, bridge.BridgeError) as error:
        raise SystemExit(str(error)) from None
    return 0


def _fit_ranges(args: argparse.Namespace) -> int:
    from showdown.postflop import bridge, rangefit

    try:
        data = rangefit.fit(log=lambda line: print(line, flush=True))
    except bridge.BridgeError as error:
        raise SystemExit(str(error)) from None
    rangefit.write(data)
    print(f"wrote {len(data['curves'])} curves: {data['source']}")
    return 0


def _library_status(args: argparse.Namespace) -> int:
    from showdown.postflop import library

    for spot in [args.spot] if args.spot else library.SPOTS:
        print(library.status_line(spot))
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
            open_bb=args.open,
            threebet_bb=args.threebet,
        )
    except (SpotError, ValueError) as error:
        raise SystemExit(f"bad spot: {error}") from None
    advisor = Advisor.load(ranges=args.ranges, log_path=None if args.no_log else args.log)
    try:
        s = advisor.suggest(spot)
    except SpotError as error:
        raise SystemExit(f"bad spot: {error}") from None
    _print_suggestion(s)
    return 0


def _print_suggestion(s, indent: str = "") -> None:
    print(
        f"{indent}{s.street}: {(s.action or 'no action hint').upper()}"
        + (f" {s.size_bb:g} bb" if s.size_bb else "")
    )
    if s.evs:
        print(f"{indent}  EV (bb): " + ", ".join(f"{k} {v:+.3f}" for k, v in s.evs.items()))
    if s.mix:
        print(f"{indent}  mix: " + ", ".join(f"{k} {v:.0%}" for k, v in s.mix.items()))
    for note in s.notes:
        print(f"{indent}  ! {note}")
    if s.equity is not None:
        se = f" +/- {s.se:.3f}" if s.se else ""
        print(f"{indent}  equity {s.equity:.1%}{se} vs {s.villain_range}")
    if s.threshold is not None:
        print(f"{indent}  threshold {s.threshold:.1%}")
    print(f"{indent}  {s.source}; {s.elapsed_ms:.0f} ms")


def _replay(args: argparse.Namespace) -> int:
    import hashlib

    from showdown.equity.cards import cards_str
    from showdown.hh.replay import ReplayError
    from showdown.live import hand
    from showdown.live.advisor import Advisor
    from showdown.live.spot import SpotError

    try:
        replayed = hand.load(args.file)
    except (ReplayError, OSError) as error:
        raise SystemExit(f"cannot replay {args.file}: {error}") from None
    hole = replayed.holes[args.hero]
    if hole is None:
        raise SystemExit(f"the {args.hero.upper()}'s cards are not in the hand history")
    start = replayed.starting_bb
    print(
        f"{args.file}: you are the {args.hero.upper()} with {cards_str(hole)}; stacks "
        f"SB {start['sb']:g} bb, BB {start['bb']:g} bb"
    )
    advisor = Advisor.load(log_path=None)
    mine = [d for d in replayed.decisions if d.seat == args.hero]
    for k, d in enumerate(mine, 1):
        legal = d.legal
        options = ["fold"] if legal.to_call_bb > 0 else []
        options.append(f"call {legal.to_call_bb:g}" if legal.to_call_bb > 0 else "check")
        if legal.can_raise:
            kind = "raise" if max(d.bets_bb.values()) > 0 else "bet"
            options.append(f"{kind} to {legal.raise_min_bb:g}-{legal.raise_max_bb:g}")
        villain = "BB" if d.seat == "sb" else "SB"
        print(f"\n[{k}] {d.street}, board {cards_str(d.board) or '-'}")
        print(f"    history: {'; '.join(str(m) for m in d.history) or '(none)'}")
        print(
            f"    pot {d.pot_bb:g} bb, to call {d.to_call_bb:g} bb; stacks: you "
            f"{d.stacks_bb[d.seat]:g} bb, {villain} {d.stacks_bb[villain.lower()]:g} bb"
        )
        print(f"    legal: {', '.join(options)}")
        if d.street == "preflop":
            print(f"    preflop decision (from the action): {d.preflop_decision}")
        else:
            kind, note = d.pot_type
            print(f"    pot type (from the action): {kind}" + (f"; {note}" if note else ""))
        spot = d.spot()
        try:
            s = advisor.suggest(spot)
        except SpotError as error:
            print(f"    advice: none ({error})")
        else:
            print("    advice:")
            _print_suggestion(s, "      ")
        if args.trace and d.street != "preflop":
            v = advisor.advice_range(spot)  # the solved range where a live solve answers
            weights = v.weights or (1.0,) * len(v.combos)
            digest = hashlib.sha256(repr((v.combos, weights)).encode()).hexdigest()[:12]
            print(f"    trace: history given to the advisor: {len(spot.history)} moves")
            print(
                f"    trace: range into the equity calculation: {len(v.combos)} combos, "
                f"total weight {sum(weights):.4f}, fingerprint {digest}"
            )
        print(f"    you did: {d.taken}")
    return 0


def _live(args: argparse.Namespace) -> int:
    import warnings

    from pokerkit import HandHistory

    if args.screen:
        try:
            from showdown.live.reader import read
        except ImportError:
            raise SystemExit("the screen reader (spike S1) isn't built yet") from None
        return _screen_session(read, args)

    from showdown.live.advisor import Advisor
    from showdown.live.overlay import Overlay, event_lines
    from showdown.live.table import TableState, frames_from_history
    from showdown.live.tracker import HANDS_DIR, Tracker

    path = Path(args.replay)
    if path.suffix.lower() == ".phh":
        if args.hero is None:
            raise SystemExit("a .phh replay needs --hero sb or --hero bb")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            hh = HandHistory.load(path.open("rb"))
        frames = list(frames_from_history(hh, args.hero, every_change=not args.turns_only))
    else:
        lines = path.read_text(encoding="utf-8").splitlines()
        frames = [TableState.from_json(line) for line in lines if line.strip()]
    overlay = None if args.no_window else Overlay()

    def show(event) -> None:
        head, details, state = event_lines(event)
        print(f"[{event.kind}] {head}" + (f"  ({state})" if state else ""))
        for line in details:
            print(f"    {line}")
        if overlay is not None and event.kind == "solving":
            overlay.show(event)  # until the live solve answers (DECISIONS 47)
        elif overlay is not None and event.kind in ("advice", "no suggestion", "error"):
            overlay.show(event)
            time.sleep(args.delay)

    tracker = Tracker(Advisor.load(), HANDS_DIR if args.save else None, on_solving=show)
    for frame in frames:
        for event in tracker.feed(frame):
            if event.kind != "solving":  # shown as it happened
                show(event)
    if overlay is not None:
        print("close the overlay window to finish")
        overlay.wait()
    return 0


def _screen_session(read, args: argparse.Namespace) -> int:  # pragma: no cover - a desktop
    """Read the Poker Now window Ian plays in, every 250 ms, until Ctrl+C (DECISIONS 52)."""
    from showdown.live import capture, screen
    from showdown.live.advisor import Advisor
    from showdown.live.overlay import Overlay, event_lines
    from showdown.live.tracker import HANDS_DIR, Tracker

    try:
        import mss  # noqa: F401
    except ImportError:
        raise SystemExit("needs the live extra: pip install -e .[live]") from None
    capture.dpi_aware()
    overlay = None if args.no_window else Overlay()

    def wait(seconds: float) -> None:
        if overlay is not None:
            overlay.root.update()  # keeps the overlay drawn and draggable
        time.sleep(seconds)

    def show(event) -> None:
        head, details, state = event_lines(event)
        print(f"[{event.kind}] {head}" + (f"  ({state})" if state else ""))
        for line in details:
            print(f"    {line}")
        if overlay is not None and event.kind in ("advice", "solving", "no suggestion", "error"):
            overlay.show(event)

    print("click the Poker Now window you play in; the other seat's window is never read")
    hwnd, rect = screen.wait_for_poker_now(capture.front_handle, capture.window, wait)
    if overlay is not None:
        overlay.move(*screen.overlay_xy(rect, overlay.root.winfo_screenwidth()))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    log_path = screen.SESSIONS_DIR / f"{stamp}.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    tracker = Tracker(Advisor.load(), HANDS_DIR, on_solving=show)
    poll = screen.locked_window(hwnd, capture.front_handle, capture.window, capture.grab_png)
    with log_path.open("a", encoding="utf-8") as log:
        loop = screen.ScreenLoop(read, tracker, show, log, screen.SHOTS_DIR / stamp)
        print(f"reading that window while it is in front; log {log_path}; Ctrl+C to stop")
        try:
            screen.run(loop, poll, wait)
        except KeyboardInterrupt:
            loop.close()
    print(f"stopped: {loop.hand_no} hands seen, {tracker.written} written")
    if overlay is not None:
        overlay.close()
    return 0


def _capture(args: argparse.Namespace) -> int:
    from showdown.live import capture

    folder, saved = Path(args.out), []

    def report(path: Path | None) -> None:
        if path is None:
            print("F9: the window in front isn't a Poker Now tab; nothing saved")
        else:
            saved.append(path)
            print(f"saved {path} ({len(saved)})")

    print(f"press F9 on the Poker Now window to save it to {folder}; Ctrl+C to stop")
    try:
        capture.run(folder, report)
    except KeyboardInterrupt:
        print(f"stopped: {len(saved)} saved")
    return 0


def _preflop_build(args: argparse.Namespace) -> int:
    import os

    from showdown import preflop_fit, preflop_model
    from showdown.postflop import library

    start = time.perf_counter()
    if args.tree == "v1":
        out = args.out or preflop_model.V1_MODEL
        model = preflop_model.build(iterations=args.iterations, workers=args.workers)
    else:
        out = args.out or preflop_model.DEFAULT_MODEL
        try:
            r_by_depth, r_fit = preflop_fit.product_r(preflop_fit.load())
        except (OSError, preflop_fit.FitError) as error:
            raise SystemExit(f"the product solve needs the R fit's round 2: {error}") from None
        if not library.on_ac_power():
            raise SystemExit("not on AC power: plug in before the product solve")
        library._keep_awake(True)
        try:
            model = preflop_model.build_fitted(
                r_by_depth, r_fit, iterations=args.iterations, workers=args.workers
            )
        finally:
            library._keep_awake(False)
        old = Path(out)
        if old.exists() and preflop_model.PreflopModel.load(old).version == 1:
            moved = old.with_name(Path(preflop_model.V1_MODEL).name)
            if moved.exists():
                raise SystemExit(f"{moved} exists already; {old} was not replaced")
            os.replace(old, moved)  # DECISIONS 49: the old model, renamed byte for byte
            print(f"moved the old model to {moved}")
    model.save(out)
    print(f"cfr+, {args.iterations} iterations; grid {list(preflop_model.GRID)}")
    print(f"{'stack':>6} {'R':>24} {'exploitability':>15} {'SB value':>9}")
    for s in model.checks + model.solutions:
        kind = "" if s.raises else "  (jam-only)"
        if s.r is None:
            r = f"{s.r_oop:.2f}"
        else:
            r = f"{s.shift:+.2f}: " + " ".join(f"{p} {v:.3f}" for p, v in s.r.items())
        print(f"{s.stack:>6g} {r:>24} {s.exploitability:>15.2e} {s.value_sb:>+9.4f}{kind}")
    print(f"wrote {out} in {time.perf_counter() - start:.0f} s")
    return 0


def _preflop_fit(args: argparse.Namespace) -> int:
    from showdown import preflop_fit
    from showdown.postflop import bridge

    start = time.perf_counter()
    try:
        data = preflop_fit.run_round(
            args.round, workers=args.workers, log=lambda line: print(line, flush=True)
        )
    except (preflop_fit.FitError, bridge.BridgeError) as error:
        raise SystemExit(str(error)) from None
    cells = preflop_fit.round_cells(data, args.round)
    print(f"round {args.round}: R per pot and fit depth")
    for pot, by in cells.items():
        row = []
        for d, c in by.items():
            se = f" (SE {c['se']:.3f})" if c["measured"] else f" ({c['source']})"
            row.append(f"{d} bb {c['r']:.3f}{se}")
        print(f"  {pot}: " + "; ".join(row))
    print(f"wrote {preflop_fit.FIT_PATH} in {time.perf_counter() - start:.0f} s")
    return 0


def _preflop_chart(args: argparse.Namespace) -> int:
    from showdown import preflop_model
    from showdown.equity.cards import RANKS

    model = preflop_model.PreflopModel.load(args.file)
    depth = model.depth_for(args.stack)
    if depth is None:
        raise SystemExit("20 bb or less uses push/fold: showdown pushfold chart")
    s = model.at(depth, args.r) if model.version == 1 else model.at(depth)
    if args.node not in s.actions:
        raise SystemExit(f"node must be one of {sorted(s.actions)}")
    letters = {"fold": "F", "call": "C", "raise": "R", "all-in": "J", "raise 4x": "Q"}
    r = f"R {args.r:.2f}" if model.version == 1 else model.r_label
    print(f"model chart, {r}, {depth:g} bb, node {args.node!r}: most likely action")
    if model.version == 2:
        pairs = preflop_matrix.PreflopMatrix.load(model.matrix_path).pair_counts
        reach = s.reach(args.node, pairs)
        print("R " + ", ".join(f"{p} {v:.3f}" for p, v in s.r.items()) + f"; reached {reach:.3%}")
        print("(R = raise: the open, or the 3-bet to 3x; Q = the 3-bet to 4x)")
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


def _kind(action: str) -> str:
    return "fold" if action == "fold" else ("raise" if " to " in action else "limp")


def _sixmax(args: argparse.Namespace) -> int:
    from showdown import sixmax as S

    try:
        spot = S.Spot(args.seat.upper(), args.limpers, args.ante)
        hand = S.parse_hand(args.hand)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    profiles = S.load_profiles()
    p = profiles[args.profile]
    a = S.answer(spot, p, hand, samples=args.samples, seed=args.seed)

    def pct(rate: str, value: float | None = None) -> str:
        v = getattr(p, rate) if value is None else value
        return f"{v:.0%}" + (" (assumed)" if p.source.get(rate) == "assumed" else "")

    def rng(weights) -> str:
        return f"{S.share_of_hands(weights):.1%} of hands: {S.range_text(weights)}"

    limpers = (
        f"{spot.limpers} limper{'s' * (spot.limpers != 1)} ahead" if spot.limpers else "unopened"
    )
    ante = f"ante {spot.ante:g} from everyone" if spot.ante else "no ante"
    print(
        f"{spot.seat} with {a.hand}: {limpers}, 100 bb, blinds 0.5/1, {ante} ({spot.pot:g} bb in)"
    )
    print(
        f"Opponents: {p.name}, one profile for the whole table, fitted to 2009 online "
        "6-max hands (docs/sixmax-profiles.md). Assumed, not measured on your players."
    )
    print("\nAssumed ranges")
    x_ref = spot.sizes[1]
    kinds = [k for k, _ in spot.opponents()]
    if "limper" in kinds:
        limp = p.limp_weights()
        f = min(1 - p.iso_reraise, max(0.0, p.iso_fold))
        print(f"  Each limper: limp range {rng(S.band(limp, 0, 1 + 1e-12))}")
        print(f"    facing an iso to {x_ref:g} bb: fold {pct('iso_fold', f)}")
        print(f"      call: {rng(S.band(limp, f, 1 - p.iso_reraise))}")
        print(
            f"      re-raise ({pct('iso_reraise')} of the range): {rng(S.top(limp, p.iso_reraise))}"
        )
    rates = {
        "behind": ("Each player behind", "behind_3bet", "behind_call"),
        "SB": ("SB", "sb_3bet", "sb_call"),
        "BB": ("BB", "bb_3bet", "bb_call"),
    }
    for kind in ("behind", "SB", "BB"):
        if kind not in kinds:
            continue
        who, t_rate, c_rate = rates[kind]
        t, c = getattr(p, t_rate), getattr(p, c_rate)
        print(f"  {who}, facing a raise to {x_ref:g} bb:")
        print(f"    3-bet {pct(t_rate)}: {S.range_text(S.top(S.ALL_HANDS, t))}")
        print(f"    call {pct(c_rate)}: {S.range_text(S.band(S.ALL_HANDS, 1 - t - c, 1 - t))}")
    behind = []
    if "behind" in kinds:
        behind.append(f"each player behind raises {pct('limp_raise')}, overlimps {pct('overlimp')}")
    if "SB" in kinds:
        behind.append(f"SB raises {pct('sb_limp_raise')}, completes {pct('sb_complete')}")
    if "BB" in kinds:
        behind.append(f"BB raises {pct('bb_limp_raise')}")
    if behind:
        print(f"  Facing your {a.actions[1]}: " + "; ".join(behind))
    print(
        f"  Sizes move fold rates by {p.iso_slope:+.3f} (limpers) and {p.behind_slope:+.3f} "
        "(players behind) per bb away from the middle size."
    )

    print(f"\nEV of each action, in bb against folding ({args.samples:,} deals, seed {args.seed})")
    print(f"  {'':12s} {'EV':>7s}  {'SE':>4s}")
    for name, ev, se in zip(a.actions, a.ev, a.se, strict=True):
        mark = "   best" if name == a.best else ""
        print(f"  {name:12s} {ev:+7.2f}  {se:4.2f}{mark}")
    print(
        f"\nVerdict: {a.tier.upper()}. Best: {a.best}. Runner-up: {a.runner_up} "
        f"({a.gap_se:.1f} standard errors behind)."
    )
    if a.flips:
        winners = sorted({w for _, _, w in a.flips})
        for w in winners:
            where = [f"R {r:+.1f}/fold {d:+.0%}" for r, d, x in a.flips if x == w]
            print(f"  {w} wins at " + ", ".join(where))
        if all(_kind(w) == _kind(a.best) for w in winners):
            print(f"  Every band point picks a {_kind(a.best)}: only the size is close.")
    if a.no_stackoff_best != a.best:
        print(
            f"  Folding to every re-raise instead of stacking off, the best is {a.no_stackoff_best}."
        )
    print(
        "Band: every R moved 0.1 either way, fold-to-raise rates 10 points either way. "
        "The limp EV is a floor: "
        "a raise behind it is folded. Facing a re-raise, the hero stacks off or folds."
    )
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
    pf_build.add_argument(
        "--ante", type=float, default=0.0, help="per player, in bb (DECISIONS 48)"
    )
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

    post = commands.add_parser("postflop", help="postflop solving ahead of time (DECISIONS 40)")
    post_commands = post.add_subparsers(dest="postflop_command", required=True)
    post_build = post_commands.add_parser(
        "build", help="build the AGPL solver bridge in bridges/postflop (needs Rust)"
    )
    post_build.set_defaults(handler=_postflop_build)
    post_exploit = post_commands.add_parser(
        "exploit", help="your flop strategy with and without one locked read about the villain"
    )
    post_exploit.add_argument("--pot-type", choices=["srp", "3bp"], default="srp")
    post_exploit.add_argument("--stack", type=float, required=True, help="effective stack in bb")
    post_exploit.add_argument("--flop", required=True, help="e.g. Kc7d6c")
    post_exploit.add_argument("--hero", choices=["sb", "bb"], required=True)
    post_exploit.add_argument(
        "--read",
        choices=["never-folds", "over-folds", "never-bets", "always-bets"],
        required=True,
        help="the villain's leak, locked at its first flop decision",
    )
    post_exploit.set_defaults(handler=_postflop_exploit)
    post_fit = post_commands.add_parser(
        "fit-ranges", help="fit the stopgap range model to solves (DECISIONS 46; needs the bridge)"
    )
    post_fit.set_defaults(handler=_fit_ranges)
    post_library = post_commands.add_parser("library", help="the overnight flop library")
    library_commands = post_library.add_subparsers(dest="library_command", required=True)
    spots = ["3BP100", "SRP25", "SRP50", "SRP100"]
    lib_build = library_commands.add_parser(
        "build", help="solve flops in coverage order; resumable; needs AC power"
    )
    lib_build.add_argument("--spot", choices=spots, required=True)
    lib_build.add_argument("--until", metavar="HH:MM", help="start no flop after this time")
    lib_build.set_defaults(handler=_library_build)
    lib_status = library_commands.add_parser("status", help="flops solved and coverage")
    lib_status.add_argument("--spot", choices=spots)
    lib_status.set_defaults(handler=_library_status)

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
    advise.add_argument("--open", type=float, help="the SB's open, raise-to in bb (default 2.5)")
    advise.add_argument(
        "--threebet",
        type=float,
        help="the BB's 3-bet, raise-to in bb: picks a 3-bet pot's 3x or 4x line",
    )
    advise.add_argument("--villain", help="custom villain range, e.g. 'TT+,AQs+'")
    advise.add_argument(
        "--villain-top", type=float, help="custom villain range: the top N%% of hands"
    )
    advise.add_argument("--mode", choices=["hint", "equity"], default="hint")
    advise.add_argument("--log", default="data/live/advice.jsonl")
    advise.add_argument("--no-log", action="store_true")
    advise.set_defaults(handler=_advise)

    replay = commands.add_parser(
        "replay", help="a saved heads-up PHH hand: the state and advice at each of your decisions"
    )
    replay.add_argument("file", help="a .phh file with two players")
    replay.add_argument("--hero", choices=["sb", "bb"], required=True)
    replay.add_argument(
        "--trace", action="store_true", help="also show the range passed to the equity calculation"
    )
    replay.set_defaults(handler=_replay)

    live = commands.add_parser(
        "live", help="the tracker and overlay, fed recorded frames or the Poker Now window"
    )
    source = live.add_mutually_exclusive_group(required=True)
    source.add_argument("--replay", help="frames as .jsonl, or a heads-up .phh hand to make them")
    source.add_argument(
        "--screen", action="store_true", help="read the Poker Now window you play in, live"
    )
    live.add_argument("--hero", choices=["sb", "bb"], help="your seat, for a .phh hand")
    live.add_argument(
        "--turns-only", action="store_true", help=".phh: frames only at your turns and the end"
    )
    live.add_argument("--no-window", action="store_true", help="print only; no overlay")
    live.add_argument("--delay", type=float, default=1.5, help="seconds per suggestion shown")
    live.add_argument("--save", action="store_true", help="write finished hands to data/live")
    live.set_defaults(handler=_live)

    cap = commands.add_parser(
        "capture", help="F9 saves the Poker Now window, for the screen reader (spike S1)"
    )
    cap.add_argument("--out", default=str(Path("data") / "live" / "screens"))
    cap.set_defaults(handler=_capture)

    pre = commands.add_parser(
        "preflop", help="the preflop model above 20 bb (DECISIONS 33, 34, 49)"
    )
    pre_commands = pre.add_subparsers(dest="preflop_command", required=True)
    pre_build = pre_commands.add_parser(
        "build",
        help="solve the grid (hours; needs AC power): the 4x tree at the fitted R and -/+0.05, "
        "moving the old model to data/preflop_model_v1.json",
    )
    pre_build.add_argument("--iterations", type=int, default=1000)
    pre_build.add_argument("--workers", type=int, help="processes (about 200 MB each)")
    pre_build.add_argument(
        "--tree",
        choices=["v1", "4x"],
        default="4x",
        help="v1: DECISIONS 34's tree at R 0.85/0.90/0.95, written to data/preflop_model_v1.json",
    )
    pre_build.add_argument("--out", help="default: data/preflop_model.json (4x)")
    pre_build.set_defaults(handler=_preflop_build)
    pre_fit = pre_commands.add_parser(
        "fit-r",
        help="one round of the R fit (DECISIONS 49): preflop solves, then flop solves (hours; "
        "needs AC power and the flop bridge)",
    )
    pre_fit.add_argument("--round", type=int, choices=[1, 2], required=True)
    pre_fit.add_argument("--workers", type=int, help="preflop solve processes (about 200 MB each)")
    pre_fit.set_defaults(handler=_preflop_fit)
    pre_chart = pre_commands.add_parser("chart", help="13x13 most-likely-action chart")
    pre_chart.add_argument("stack", type=float, help="effective stack in bb")
    pre_chart.add_argument(
        "--node", default="", help="'' first in, r, rr, rrj, rj, j; the 4x tree adds r4, r4j"
    )
    pre_chart.add_argument("--r", type=float, default=0.9, help="DECISIONS 34's model only")
    pre_chart.add_argument("--file", default="data/preflop_model.json")
    pre_chart.set_defaults(handler=_preflop_chart)

    six = commands.add_parser(
        "sixmax",
        help="six-max preflop spot: ranges, EV of each action, tier (DECISIONS 53)",
    )
    six.add_argument("seat", help="UTG, HJ, CO, BTN, SB or BB")
    six.add_argument("hand", help="a class like A5s, or two cards like As5s")
    six.add_argument("--limpers", type=int, default=0, help="limpers ahead, 0 to 3")
    six.add_argument("--ante", type=float, default=0.0, help="from every player, in bb")
    six.add_argument("--profile", choices=["tight", "regular", "loose-passive"], default="regular")
    six.add_argument("--samples", type=int, default=40_000)
    six.add_argument("--seed", type=int, default=0)
    six.set_defaults(handler=_sixmax)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
