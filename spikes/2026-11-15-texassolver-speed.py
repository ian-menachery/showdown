r"""Spike S2, 2026-11-15: can TexasSolver solve heads-up flops in seconds? (DECISIONS 30)

Everything here was fixed in DECISIONS 30 before the first solve:
- 5 spots on 20 seeded flops;
- tree T1, with one size per street;
- 16 threads, an accuracy target of 2% of the pot, at most 300 iterations,
  print interval 10;
- a 120 s timeout per solve;
- a flop-by-flop order, and a stop-early rule that only ends a run whose FAIL
  is certain.

Needs the pinned `data/external/texassolver/` (DECISIONS 30). Run it from the
repo root:

    .venv\Scripts\python -I spikes\2026-11-15-texassolver-speed.py

Not part of the package and not linted by the gate.

Output on Ian's laptop, 2026-11-15 (16 threads):

      1 SRP25   Kc7d6c   120.00 s  iter 51  expl 3.0735955%  dump NO  TIMEOUT
      2 SRP50   Kc7d6c   120.00 s  iter 21  expl 21.009573%  dump NO  TIMEOUT
      3 SRP100  Kc7d6c   120.00 s  iter 11  expl 300.77576%  dump NO  TIMEOUT
      4 3BP50   Kc7d6c    65.16 s  iter 41  expl 1.3278016%  dump ok
      5 3BP100  Kc7d6c    67.06 s  iter 51  expl 1.7053703%  dump ok
      6 SRP25   AcKd4h   120.00 s  iter 11  expl 26.902412%  dump NO  TIMEOUT
      7 SRP50   AcKd4h   120.00 s  iter 11  expl 38.399548%  dump NO  TIMEOUT
      8 SRP100  AcKd4h   120.00 s  iter 0  expl 356.28516%  dump NO  TIMEOUT
      9 3BP50   AcKd4h    49.59 s  iter 41  expl 1.3701781%  dump ok
     10 3BP100  AcKd4h    76.22 s  iter 51  expl 1.8054684%  dump ok

    10 solves (stopped early: 10 solves over 20 s: the 95th percentile cannot pass)
    all: median 120.00 s (bar 10), p95 120.00 s (bar 20),
         worst exploitability 356.285% (bar 2%)
    Gate S2: FAIL

Reading:
- Single-raised pots, with wide ranges and deep stacks, never converge within
  120 s.
- 3-bet pots converge to under 2% of the pot, but take 50 to 76 s.
- The second flop ran while another session's CFR spike shared the CPU: 11
  iterations against 51 on the first. The first flop alone is already 6 to 12
  times over the 10 s bar, so contention cannot change the verdict.
"""

import csv
import hashlib
import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from showdown.equity.cards import CLASS_COMBOS, CLASS_NAMES
from showdown.equity.matrix import PreflopMatrix

ROOT = Path("data/external/texassolver")
ZIP_SHA256 = "0a9122fa0cd9384e6c1cbe0492e8a3b8ac7809890c649e1a53f77a59d6d50a7c"
SOLVER = ROOT / "TexasSolver-v0.2.0-Windows" / "console_solver.exe"
RESOURCES = ROOT / "TexasSolver-v0.2.0-Windows" / "resources"
RUNS = ROOT / "runs" / "s2"

FLOPS = (
    "Kc7d6c AcKd4h JdJc6h 9c6d3d 8c4d4c 9c4d3h Tc2h2d 6c4c2d Tc8d7d Ac6d2h "
    "QcJhJd Ac4d2h 9c7c2c 9c6d4c 7d7c3h 7c5c2c Qc6c2c Tc7c5d KdKc6c 8c7d2d"
).split()
# name: (pot, effective stack, IP top %, OOP top %); chips are half big blinds.
SPOTS = {
    "SRP25": (8, 46, 75, 55),
    "SRP50": (10, 95, 75, 55),
    "SRP100": (10, 195, 75, 55),
    "3BP50": (28, 86, 30, 15),
    "3BP100": (36, 182, 30, 15),
}
TREE = """set_bet_sizes oop,flop,bet,33
set_bet_sizes oop,flop,raise,60
set_bet_sizes oop,flop,allin
set_bet_sizes ip,flop,bet,33
set_bet_sizes ip,flop,raise,60
set_bet_sizes ip,flop,allin
set_bet_sizes oop,turn,bet,66
set_bet_sizes oop,turn,raise,60
set_bet_sizes oop,turn,allin
set_bet_sizes ip,turn,bet,66
set_bet_sizes ip,turn,raise,60
set_bet_sizes ip,turn,allin
set_bet_sizes oop,river,bet,75
set_bet_sizes oop,river,donk,75
set_bet_sizes oop,river,raise,60
set_bet_sizes oop,river,allin
set_bet_sizes ip,river,bet,75
set_bet_sizes ip,river,raise,60
set_bet_sizes ip,river,allin
set_allin_threshold 0.67
build_tree
set_thread_num 16
set_accuracy 2
set_max_iteration 300
set_print_interval 10
set_use_isomorphism 1
start_solve
set_dump_rounds 1
"""
TIMEOUT = 120.0
TIME_MEDIAN, TIME_P95, ACCURACY = 10.0, 20.0, 2.0


def top_range(percent: float, matrix: PreflopMatrix) -> str:
    """The top `percent` of combos by equity against a random hand, in TexasSolver's format."""
    w = matrix.pair_counts.astype(float)
    vs_random = (w * matrix.equity).sum(axis=1) / w.sum(axis=1)
    target = 1326 * percent / 100
    parts, taken = [], 0.0
    for cls in np.argsort(-vs_random, kind="stable"):
        n = len(CLASS_COMBOS[cls])
        if taken + n <= target + 1e-9:
            parts.append(CLASS_NAMES[cls])
            taken += n
        else:
            weight = (target - taken) / n
            if weight > 1e-6:
                parts.append(f"{CLASS_NAMES[cls]}:{weight:.4f}")
            break
    return ",".join(parts)


def board(flop: str) -> str:
    return ",".join(flop[i : i + 2] for i in (0, 2, 4))


def solve(spot: str, flop: str, ranges: dict[str, tuple[str, str]]) -> dict:
    pot, stack, _, _ = SPOTS[spot]
    ip, oop = ranges[spot]
    out = RUNS / f"{spot}_{flop}.json"
    text = (
        f"set_pot {pot}\nset_effective_stack {stack}\nset_board {board(flop)}\n"
        f"set_range_ip {ip}\nset_range_oop {oop}\n{TREE}dump_result {out.as_posix()}\n"
    )
    input_file = RUNS / f"{spot}_{flop}.txt"
    input_file.write_text(text, encoding="ascii")
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            [str(SOLVER), "--input_file", str(input_file), "--resource_dir", str(RESOURCES),
             "--mode", "holdem"],
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        log = proc.stdout + proc.stderr
        timed_out = False
    except subprocess.TimeoutExpired as error:
        log = (error.stdout or b"").decode(errors="replace") if isinstance(error.stdout, bytes) else (error.stdout or "")
        timed_out = True
    wall = time.perf_counter() - start
    exploit = re.findall(r"Total exploitability ([0-9.]+) precent", log)
    iters = re.findall(r"Iter: (\d+)", log)
    dump_ok = False
    if not timed_out and out.exists():
        root = json.loads(out.read_text())
        probs = root["strategy"]["strategy"]
        dump_ok = bool(probs) and all(abs(sum(p) - 1) < 1e-3 for p in probs.values())
    return {
        "spot": spot,
        "flop": flop,
        "seconds": round(TIMEOUT if timed_out else wall, 2),
        "timed_out": timed_out,
        "iterations": int(iters[-1]) if iters else None,
        "exploitability_pct": float(exploit[-1]) if exploit else None,
        "dump_ok": dump_ok,
    }


def fail_certain(rows: list[dict]) -> str | None:
    over10 = sum(r["seconds"] > TIME_MEDIAN for r in rows)
    over20 = sum(r["seconds"] > TIME_P95 for r in rows)
    bad = [r for r in rows if r["timed_out"] or r["exploitability_pct"] is None
           or r["exploitability_pct"] > ACCURACY]
    if over10 > 50:
        return f"{over10} solves over {TIME_MEDIAN:g} s: the median cannot pass"
    if over20 > 5:
        return f"{over20} solves over {TIME_P95:g} s: the 95th percentile cannot pass"
    if bad:
        return f"{bad[0]['spot']} {bad[0]['flop']} ended above {ACCURACY:g}% of the pot"
    return None


def main() -> int:
    digest = hashlib.sha256((ROOT / "TexasSolver-v0.2.0-Windows.zip").read_bytes()).hexdigest()
    if digest != ZIP_SHA256:
        sys.exit("TexasSolver zip SHA-256 does not match DECISIONS 30")
    RUNS.mkdir(parents=True, exist_ok=True)
    matrix = PreflopMatrix.load("data/preflop_169_exact.npz")
    ranges = {s: (top_range(v[2], matrix), top_range(v[3], matrix)) for s, v in SPOTS.items()}
    rows: list[dict] = []
    stopped = None
    for k, flop in enumerate(FLOPS):
        for spot in SPOTS:
            row = solve(spot, flop, ranges)
            rows.append(row)
            print(f"{len(rows):>3} {spot:<7} {flop}  {row['seconds']:>7.2f} s  "
                  f"iter {row['iterations']}  expl {row['exploitability_pct']}%  "
                  f"dump {'ok' if row['dump_ok'] else 'NO'}{'  TIMEOUT' if row['timed_out'] else ''}",
                  flush=True)
        if k >= 1 and (stopped := fail_certain(rows)):
            break
    with open(ROOT / "runs" / "s2_results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{len(rows)} solves{' (stopped early: ' + stopped + ')' if stopped else ''}")
    print(f"{'spot':<7} {'n':>3} {'median s':>9} {'p95 s':>7} {'max s':>7} {'worst expl %':>13}")
    for spot in SPOTS:
        sub = [r for r in rows if r["spot"] == spot]
        secs = sorted(r["seconds"] for r in sub)
        expl = [r["exploitability_pct"] for r in sub if r["exploitability_pct"] is not None]
        p95 = float(np.percentile(secs, 95)) if secs else float("nan")
        print(f"{spot:<7} {len(sub):>3} {statistics.median(secs):>9.2f} {p95:>7.2f} "
              f"{max(secs):>7.2f} {max(expl) if expl else float('nan'):>13.3f}")
    secs = [r["seconds"] for r in rows]
    median, p95 = statistics.median(secs), float(np.percentile(secs, 95))
    worst = max((r["exploitability_pct"] or float("inf")) for r in rows)
    passed = (not stopped and len(rows) == 100 and median <= TIME_MEDIAN
              and p95 <= TIME_P95 and worst <= ACCURACY)
    print(f"\nall: median {median:.2f} s (bar {TIME_MEDIAN:g}), p95 {p95:.2f} s (bar {TIME_P95:g}), "
          f"worst exploitability {worst:.3f}% (bar {ACCURACY:g}%)")
    print("Gate S2:", "PASS" if passed else "FAIL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
