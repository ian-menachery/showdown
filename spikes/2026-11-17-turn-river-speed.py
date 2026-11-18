r"""Spike S2b, 2026-11-17: can the turn and river be solved live? (DECISIONS 44)

Everything here was fixed in DECISIONS 44 (commit 703908c) before the first timed solve:
- 3BP100 and SRP50, 10 boards each, dealt with seed 20261117; the flop in the
  library's canonical suits, the turn and river relabelled to match;
- per board, one turn start and one river start: 20 turn and 20 river solves;
- the opponent's and the hero's ranges narrowed by the flop line (check-check,
  bet-call, check-bet-call, in turn by board) from the library's four stored
  flop nodes. The library is empty, so the spike solves those flops itself with
  the library's exact spec, untimed and cached;
- the river starts assume the turn checked through: the slow case;
- tree T1's turn and river, 16 threads, 2% of the street's pot, at most 1,000
  iterations, a 120 s timeout, timed from process start to the parsed result.

Needs the pinned solver checkout and both bridge binaries (`showdown postflop
build`). Run from the repo root, the flops first, then the timed solves on an
idle laptop:

    .venv\Scripts\python -I spikes\2026-11-17-turn-river-speed.py --flops-only
    .venv\Scripts\python -I spikes\2026-11-17-turn-river-speed.py

Not part of the package and not linted by the gate.

A smoke test outside the grid (AA vs KK, Td9d6h2c and Td9d6h2c3s) solved in
10 iterations; with `oop_turn_bet` "" the OOP's only turn action was a check.

The 20 flops, untimed: 3BP100 53-163 s, SRP50 61-254 s, 1.38-2.00% of pot.

Output on Ian's laptop, 2026-11-17 17:41 (16 threads; another session's `find`
used one core):

    spot    street line             n  median s   max s      iter  worst expl %  mem GB
    3BP100  river  bet-call         6      0.03    0.04   30-40           1.689   0.000
    3BP100  river  check-bet-call   2      0.03    0.05   30-30           1.353   0.000
    3BP100  river  check-check      2      0.04    0.05   40-50           1.035   0.000
    3BP100  turn   bet-call         6      0.28    0.64   40-50           1.757   0.018
    3BP100  turn   check-bet-call   2      0.24    0.28   40-40           1.410   0.014
    3BP100  turn   check-check      2      0.68    1.12   50-60           1.940   0.020
    SRP50   river  bet-call         2      0.04    0.04   40-40           1.784   0.000
    SRP50   river  check-bet-call   4      0.03    0.04   40-40           1.530   0.000
    SRP50   river  check-check      4      0.05    0.06   40-60           1.521   0.000
    SRP50   turn   bet-call         2      0.37    0.42   40-50           1.936   0.026
    SRP50   turn   check-bet-call   4      0.25    0.30   40-50           1.792   0.018
    SRP50   turn   check-check      4      0.71    0.89   60-60           1.833   0.051

    river: 20 solves, median 0.03 s (bar 3), p95 0.05 s (bars 6 and 2 x median = 0.07), max 0.06 s: PASS
    turn: 20 solves, median 0.30 s (bar 15), p95 0.90 s (bars 30 and 2 x median = 0.60), max 1.12 s: FAIL
    accuracy: worst 1.940% of pot (bar 2%), 0 over: PASS

    Gate S2b: FAIL

Five boards took the next flop line (under 5 combos left): 3BP100 KcJd3h,
Kc7c6d, AcJd7h (the 3-bettor almost never checks) and SRP50 Qc8c2d (the BB
almost never leads). The first solve's 1.12 s includes 0.58 s of cold process
start. The per-solve rows are in data/external/postflop-solver/runs/
s2b-20261117-174138.json (gitignored). GATES.md has the reading.

Spike S2c (DECISIONS 45) is `--s2c`: seed 20261118 and absolute tail bars only.

    .venv\Scripts\python -I spikes\2026-11-17-turn-river-speed.py --s2c --flops-only
    .venv\Scripts\python -I spikes\2026-11-17-turn-river-speed.py --s2c

Its flops took 27-213 s, at 1.19-1.97% of pot. Output on 2026-11-18 01:13:

    river: 20 solves, median 0.03 s (bar 3), p95 0.09 s (bars 6 and 2 x median = 0.07), max 0.69 s: PASS
    turn: 20 solves, median 0.38 s (bar 15), p95 1.17 s (bars 30 and 2 x median = 0.75), max 1.18 s: PASS
    accuracy: worst 1.979% of pot (bar 2%), 0 over: PASS

    Gate S2c: PASS

The "2 x median" figures are reported, not gated, in S2c. Rows:
data/external/postflop-solver/runs/s2c-20261118-011329.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import itertools
import json
import random
import re
import statistics
import subprocess
import sys
import time

import numpy as np

from showdown.equity.cards import CLASS_NAMES, cards_str, class_index, class_of, combo_str
from showdown.postflop import bridge, library
from showdown.postflop.flops import canonical, relabel
from showdown.postflop.spot import SETTINGS, TREE_T1, FlopSpot, model_range

SEED = 20261117
SEED_S2C = 20261118
"""Spike S2c (DECISIONS 45): new boards, and the tail bars are absolute only."""
SPOTS = (("3BP100", "3bp", 100), ("SRP50", "srp", 50))
BOARDS = 10
LINES = ("check-check", "bet-call", "check-bet-call")
MIN_COMBOS = 5.0
TIMEOUT = 120.0
FLOP_BINARY = "c45af7521f193b53c96fc85b360cd954b81670d7480d57fd5aaf1997d634206f"
STREETS = bridge.TARGET_DIR / "release" / "streets.exe"
CACHE = bridge.EXTERNAL / "cache" / "s2b"
RUNS = bridge.EXTERNAL / "runs"
BARS = {"river": (3.0, 6.0), "turn": (15.0, 30.0)}
"""Median bar, 95th-percentile bar, in seconds."""
TARGET_PCT = 2.0
STREET_TREE = {k: TREE_T1[k] for k in TREE_T1 if not k.startswith("flop")}
_SIZED = re.compile(r"^Bet\((\d+)\)$")

COMBOS = [(b, a) for a, b in itertools.combinations(range(52), 2)]
"""Every combo, high card first, in the solver's raw order (index = c1*(101-c1)/2 + c2 - 1)."""


def boards(seed: int = SEED) -> list[tuple[str, str, str, int, tuple[int, ...], tuple[int, int]]]:
    """(spot, pot type, line, stack, canonical flop, (turn, river)), 3BP100's ten first."""
    rng = random.Random(seed)
    out = []
    for name, pot_type, stack in SPOTS:
        for i in range(BOARDS):
            deck = list(range(52))
            rng.shuffle(deck)
            flop, perm = canonical(tuple(deck[:3]))
            turn, river = relabel(tuple(deck[3:5]), perm)
            out.append((name, pot_type, LINES[i % 3], stack, flop, (turn, river)))
    return out


def flop_entry(spot_name: str, pot_type: str, stack: int, flop: tuple[int, ...]) -> dict:
    """The library's file for this flop; solved here, untimed and cached, if it isn't stored."""
    name = cards_str(flop)
    if name in library.manifest(spot_name):
        return library.load(spot_name, name)
    spot = FlopSpot.make(pot_type, stack, name)
    result = bridge.solve(spot.spec(report=list(library.NODES)), cache=CACHE)
    return library.entry(spot_name, flop, result, bridge.binary_sha256())


def preflop_weights(depth: float, pot_type: str, seat: str) -> list[float]:
    """Per combo, its class's weight in the range string the flop solve used."""
    by_class = [0.0] * len(CLASS_NAMES)
    for part in model_range(depth, pot_type, seat).split(","):
        name, _, w = part.partition(":")
        by_class[class_index(name)] = float(w) if w else 1.0
    return [by_class[class_of(c)] for c in COMBOS]


def frequency(node: dict, action: str) -> tuple[list[float], int | None]:
    """Per combo, how often it takes `action` (Check, Call or the smallest Bet) at a stored node."""
    names = node["actions"]
    if action == "Bet":
        i = next(k for k, a in enumerate(names) if _SIZED.match(a))
        amount = int(_SIZED.match(names[i]).group(1))
    else:
        i, amount = names.index(action), None
    hands = node["hands"]
    return [hands[combo_str(c)][i] / 100 if combo_str(c) in hands else 0.0 for c in COMBOS], amount


def narrow(entry: dict, line: str, pre: list[list[float]], pot: int, stack: int):
    """(OOP weights, IP weights, pot, stack) after the flop line."""
    nodes = entry["nodes"]
    for key in ("", "Check", "Bet", "Check Bet"):
        if not nodes[key]["reached"]:
            raise RuntimeError(f"{entry['flop']}: node {key!r} not reached")
    if line == "check-check":
        oop = [frequency(nodes[""], "Check")[0]]
        ip = [frequency(nodes["Check"], "Check")[0]]
        bet = 0
    elif line == "bet-call":
        f, bet = frequency(nodes[""], "Bet")
        oop, ip = [f], [frequency(nodes["Bet"], "Call")[0]]
    else:
        f, bet = frequency(nodes["Check"], "Bet")
        oop = [frequency(nodes[""], "Check")[0], frequency(nodes["Check Bet"], "Call")[0]]
        ip = [f]
    w = []
    for player, factors in ((0, oop), (1, ip)):
        out = list(pre[player])
        for f in factors:
            out = [a * b for a, b in zip(out, f, strict=True)]
        w.append(out)
    return w[0], w[1], pot + 2 * bet, stack - bet


def live(weights: list[float], board: tuple[int, ...]) -> tuple[int, float]:
    """(combos with weight, total weight), leaving out combos that touch the board."""
    dead = set(board)
    kept = [w for c, w in zip(COMBOS, weights, strict=True) if w > 0 and not dead & set(c)]
    return len(kept), sum(kept)


def timed_solve(spec: dict) -> tuple[float, dict | None, str]:
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            [str(STREETS)], input=json.dumps(spec), capture_output=True, text=True, timeout=TIMEOUT
        )
    except subprocess.TimeoutExpired:
        return TIMEOUT, None, "TIMEOUT"
    if proc.returncode != 0:
        return time.perf_counter() - start, None, "FAILED: " + proc.stderr.strip()[-300:]
    result = json.loads(proc.stdout)
    return time.perf_counter() - start, result, "ok"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--flops-only", action="store_true", help="solve the flops, time nothing")
    parser.add_argument("--s2c", action="store_true", help="Spike S2c (DECISIONS 45)")
    args = parser.parse_args()

    if not STREETS.exists():
        print(f"{STREETS} is missing: run `showdown postflop build`")
        return 2
    flop_binary = hashlib.sha256(bridge.EXE.read_bytes()).hexdigest()
    if flop_binary != FLOP_BINARY:
        print(f"the flop bridge changed: {flop_binary[:12]}, not {FLOP_BINARY[:12]}. Stopping.")
        return 2
    print(f"flop bridge {flop_binary[:12]} (unchanged); streets bridge "
          f"{hashlib.sha256(STREETS.read_bytes()).hexdigest()[:12]}")

    gate = "S2c" if args.s2c else "S2b"
    grid = boards(SEED_S2C if args.s2c else SEED)
    entries = {}
    for spot_name, pot_type, _, stack, flop, _ in grid:
        start = time.perf_counter()
        entry = flop_entry(spot_name, pot_type, stack, flop)
        entries[(spot_name, flop)] = entry
        print(f"flop {spot_name} {cards_str(flop)}: {entry['exploitability_pct']:.2f}% of pot, "
              f"{entry['build_s'] + entry['solve_s']:.0f} s solve, {time.perf_counter() - start:.1f} s here",
              flush=True)
    if args.flops_only:
        return 0

    rows = []
    print(f"\ntimed solves from {dt.datetime.now():%Y-%m-%d %H:%M:%S}")
    for n, (spot_name, pot_type, line0, stack_bb, flop, (turn, river)) in enumerate(grid, 1):
        spot = FlopSpot.make(pot_type, stack_bb, cards_str(flop))
        pre = [preflop_weights(spot.depth, pot_type, seat) for seat in ("bb", "sb")]
        entry = entries[(spot_name, flop)]
        start = LINES.index(line0)
        for k in range(len(LINES)):
            line = LINES[(start + k) % len(LINES)]
            oop, ip, pot, stack = narrow(entry, line, pre, spot.pot_chips, spot.stack_chips)
            if min(live(oop, flop)[1], live(ip, flop)[1]) >= MIN_COMBOS:
                break
            print(f"  {spot_name} {cards_str(flop)}: {line} leaves under {MIN_COMBOS:g} combos")
        for street, board in (("turn", flop + (turn,)), ("river", flop + (turn, river))):
            spec = {
                "oop_range": oop,
                "ip_range": ip,
                "board": cards_str(board),
                "starting_pot": pot,
                "effective_stack": stack,
                **STREET_TREE,
                **SETTINGS,
                "report": [[]],
            }
            if street == "turn" and line == "check-bet-call":
                spec["oop_turn_bet"] = ""  # T1: no OOP turn lead after calling a flop bet
            secs, result, status = timed_solve(spec)
            row = {
                "n": n, "spot": spot_name, "street": street, "line": line,
                "line_planned": line0, "board": cards_str(board), "pot": pot, "stack": stack,
                "seconds": secs, "status": status,
                "combos_before": [live(p, board) for p in pre],
                "combos_after": [live(oop, board), live(ip, board)],
            }
            if result:
                row |= {k: result[k] for k in (
                    "iterations", "exploitability_pct", "memory_gb", "build_s", "solve_s")}
            rows.append(row)
            expl = f"{row['exploitability_pct']:.3f}%" if result else "-"
            print(f"{len(rows):>3} {spot_name:<6} {street:<5} {cards_str(board):<10} {line:<14} "
                  f"pot {pot / 10:>5.1f} stk {stack / 10:>5.1f}  {secs:>7.2f} s  "
                  f"iter {row.get('iterations', '-'):>4}  expl {expl:>7}  "
                  f"mem {row.get('memory_gb', 0):.3f} GB  combos OOP {row['combos_after'][0][0]} "
                  f"IP {row['combos_after'][1][0]}  {status}", flush=True)

    RUNS.mkdir(parents=True, exist_ok=True)
    out = RUNS / f"{gate.lower()}-{dt.datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\nrows written to {out}")

    print(f"\n{'spot':<7} {'street':<6} {'line':<15} {'n':>2} {'median s':>9} {'max s':>7} "
          f"{'iter':>9} {'worst expl %':>13} {'mem GB':>7}")
    for (spot_name, street, line), group in itertools.groupby(
        sorted(rows, key=lambda r: (r["spot"], r["street"], r["line"])),
        key=lambda r: (r["spot"], r["street"], r["line"]),
    ):
        g = list(group)
        secs = [r["seconds"] for r in g]
        iters = [r.get("iterations", 0) for r in g]
        worst = max(r.get("exploitability_pct", float("inf")) for r in g)
        print(f"{spot_name:<7} {street:<6} {line:<15} {len(g):>2} {statistics.median(secs):>9.2f} "
              f"{max(secs):>7.2f} {min(iters):>4}-{max(iters):<4} {worst:>13.3f} "
              f"{max(r.get('memory_gb', 0) for r in g):>7.3f}")

    passed = True
    print()
    for street, (median_bar, p95_bar) in BARS.items():
        secs = [r["seconds"] for r in rows if r["street"] == street]
        median, p95 = statistics.median(secs), float(np.percentile(secs, 95))
        ok = median <= median_bar and p95 <= p95_bar and (args.s2c or p95 <= 2 * median)
        passed &= ok
        print(f"{street}: {len(secs)} solves, median {median:.2f} s (bar {median_bar:g}), "
              f"p95 {p95:.2f} s (bars {p95_bar:g} and 2 x median = {2 * median:.2f}), "
              f"max {max(secs):.2f} s: {'PASS' if ok else 'FAIL'}")
    worst = max(r.get("exploitability_pct", float("inf")) for r in rows)
    bad = [r for r in rows if r.get("exploitability_pct", float("inf")) > TARGET_PCT]
    passed &= not bad
    print(f"accuracy: worst {worst:.3f}% of pot (bar {TARGET_PCT:g}%), {len(bad)} over: "
          f"{'PASS' if not bad else 'FAIL'}")
    print(f"\nGate {gate}: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
