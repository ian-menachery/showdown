r"""Spike S4, 2026-11-15: can b-inary's postflop-solver solve heads-up flops in seconds? (DECISIONS 38)

Everything here was fixed in DECISIONS 38 before the first solve:
- S2's 5 spots, 20 flops, flop-by-flop order and top-% ranges, loaded from
  S2's own spike module, so the grid is identical by construction;
- tree T1 in postflop-solver's terms: bets 33% / 66% / 75% plus all-in, raises
  60% plus all-in, no turn donk bets, river donk 75%, the library's default
  all-in thresholds;
- all 16 threads, a target of 2% of the starting pot (`compute_exploitability`,
  NashConv / 2), at most 300 iterations, 32-bit storage unless a tree needs
  more than 10 GB;
- a 120 s timeout per solve, timed from process start to result;
- S2's bars and S2's stop-early rule.

Needs Rust (DECISIONS 38's pinned toolchain) and the pinned solver checkout in
`data/external/postflop-solver/solver`. The bridge below is our own code,
written to `data/external/postflop-solver/bridge` (gitignored) and built
there. The binary links AGPL code and is never committed. Run from the repo
root:

    .venv\Scripts\python -I spikes\2026-11-15-postflop-solver-speed.py

Not part of the package and not linted by the gate.

Two build fixes came first, both before any solve:
1. The optional `bincode` feature now resolves to an incompatible
   bincode 2.0.x, so the bridge depends on the solver with only `rayon`.
2. Rust 1.100 denies `dangerous_implicit_autorefs`, which the 2023 code trips
   at three lines of action_tree.rs. Ian chose to allow that one lint.

A smoke test outside the grid (AA vs KK on Td9d6h) solved to 0.14% of the pot
in 20 iterations.

Output on Ian's laptop, 2026-11-15 (16 threads). Other projects' jobs were
also running on the laptop, using about one core:

      1 SRP25   Kc7d6c    27.71 s  iter 60  expl 1.736%  nodes 429  mem 2.39 GB  read ok
      2 SRP50   Kc7d6c    67.58 s  iter 80  expl 1.690%  nodes 568  mem 3.55 GB  read ok
      3 SRP100  Kc7d6c   120.00 s  TIMEOUT
      4 3BP50   Kc7d6c     6.69 s  iter 40  expl 1.789%  nodes 244  mem 0.45 GB  read ok
      5 3BP100  Kc7d6c    12.56 s  iter 50  expl 1.593%  nodes 363  mem 0.69 GB  read ok
      6 SRP25   AcKd4h    72.07 s  iter 60  expl 1.679%  nodes 429  mem 3.84 GB  read ok
      7 SRP50   AcKd4h   120.00 s  TIMEOUT
      8 SRP100  AcKd4h   120.00 s  TIMEOUT
      9 3BP50   AcKd4h    10.27 s  iter 40  expl 1.472%  nodes 244  mem 0.66 GB  read ok
     10 3BP100  AcKd4h    17.59 s  iter 50  expl 1.831%  nodes 363  mem 1.01 GB  read ok

    10 solves (stopped early: 6 solves over 20 s: the 95th percentile cannot pass)
    all: median 47.64 s (bar 10), p95 120.00 s (bar 20), worst exploitability inf% (bar 2%)
    Gate S4: FAIL

    Model ranges, first 5 flops (not gated): SRP25 38-85 s, SRP50 100-120 s or
    timeout, SRP100 timeout, 3BP100 23-55 s, 3BP50 skipped (the model never
    3-bets small at 50 bb).

    Node lock, SRP50 on Kc7d6c (not gated):
        unlocked                       SB bets after a check 53.1%, weakest third 53.8%
        BB never folds to the 33% bet  SB bets after a check 67.2%, weakest third 37.1%

Reading:
- postflop-solver is 4 to 10 times faster than TexasSolver on the same
  spots. 3-bet pots took 7 to 18 s, against 50 to 76 s, and SRP25 on the first
  flop finished in 28 s where TexasSolver timed out. That is still not live
  speed for single-raised pots, which have wide ranges and deep stacks:
  25 bb took 28 to 72 s, 50 bb 68 s to over 120 s, and 100 bb over 120 s.
- The FAIL does not depend on the other jobs. Single-raised pots are 60% of
  the grid and would need to run 3 to 6 times faster, while the other jobs
  used about one core of 16.
- Node locking works, and points the right way. Against a BB who never folds,
  the SB bets more often overall (value) and less often with its weakest
  third (bluffs).
"""

import csv
import functools
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from showdown import preflop_model as pm
from showdown.equity.cards import CLASS_NAMES
from showdown.equity.matrix import PreflopMatrix

ROOT = Path("data/external/postflop-solver")
SOLVER_DIR = ROOT / "solver"
COMMIT = "9d1509fe5077d019825f833eed04b16d342dfda1"
BRIDGE = ROOT / "bridge"
EXE = BRIDGE / "target" / "release" / "showdown-pfs-bridge.exe"
CARGO_BIN = Path.home() / ".cargo" / "bin"
RUNS = ROOT / "runs"
TOOLCHAIN = "1.100.0-x86_64-pc-windows-gnu"


def _load_s2():
    path = Path("spikes/2026-11-15-texassolver-speed.py")
    spec = importlib.util.spec_from_file_location("spike_s2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S2 = _load_s2()
FLOPS, SPOTS = S2.FLOPS, S2.SPOTS
TIMEOUT, TIME_MEDIAN, TIME_P95, ACCURACY = S2.TIMEOUT, S2.TIME_MEDIAN, S2.TIME_P95, S2.ACCURACY
TREE = {
    "flop_bet": "33%, a",
    "flop_raise": "60%, a",
    "turn_bet": "66%, a",
    "turn_raise": "60%, a",
    "river_bet": "75%, a",
    "river_raise": "60%, a",
    "river_donk": "75%",
}
SETTINGS = {"target_pct": ACCURACY, "max_iterations": 300, "compress_over_gb": 10.0}
MODEL_DEPTH = {"SRP25": 25, "SRP50": 50, "SRP100": 100, "3BP50": 50, "3BP100": 100}

CARGO_TOML = """[package]
name = "showdown-pfs-bridge"
version = "0.1.0"
edition = "2021"
publish = false
license = "AGPL-3.0-or-later"

[dependencies]
# Without default features: the optional `bincode` feature (saving trees) pins
# bincode 2.0.0-rc.3, which now resolves to an incompatible 2.0.x. Only
# `rayon` (multithreading) is needed.
postflop-solver = { path = "../solver", default-features = false, features = ["rayon"] }
serde_json = "1"
"""

MAIN_RS = r"""// showdown's bridge to postflop-solver (DECISIONS 38). Reads one spot as JSON on stdin and
// writes one result as JSON on stdout. Links AGPL-3.0 code: never committed or distributed.
use postflop_solver::*;
use serde_json::{json, Value};
use std::io::Read;
use std::time::Instant;

fn count_nodes(tree: &mut ActionTree) -> usize {
    let mut n = 1;
    if tree.is_terminal_node() {
        return n;
    }
    let actions: Vec<Action> = tree.available_actions().to_vec();
    for action in actions {
        tree.play(action).unwrap();
        n += count_nodes(tree);
        tree.undo().unwrap();
    }
    n
}

fn action_name(action: &Action) -> String {
    format!("{action:?}")
}

// Average frequency of each action at the current node, weighted by the actor's reach.
fn frequencies(game: &PostFlopGame) -> (Vec<String>, Vec<f64>, Vec<f32>, Vec<f32>) {
    let player = game.current_player();
    let actions = game.available_actions();
    let strategy = game.strategy();
    let weights = game.normalized_weights(player).to_vec();
    let n = weights.len();
    let total: f64 = weights.iter().map(|&w| w as f64).sum();
    let freq = (0..actions.len())
        .map(|a| (0..n).map(|h| (weights[h] * strategy[a * n + h]) as f64).sum::<f64>() / total)
        .collect();
    (actions.iter().map(action_name).collect(), freq, strategy, weights)
}

fn main() {
    let start = Instant::now();
    let mut input = String::new();
    std::io::stdin().read_to_string(&mut input).unwrap();
    let spec: Value = serde_json::from_str(&input).unwrap();
    let text = |key: &str| spec[key].as_str().unwrap().to_string();
    let sizes = |bet: &str, raise: &str| {
        BetSizeOptions::try_from((text(bet).as_str(), text(raise).as_str())).unwrap()
    };
    let card_config = CardConfig {
        range: [text("oop_range").parse().unwrap(), text("ip_range").parse().unwrap()],
        flop: flop_from_str(&text("flop")).unwrap(),
        turn: NOT_DEALT,
        river: NOT_DEALT,
    };
    let starting_pot = spec["starting_pot"].as_i64().unwrap() as i32;
    let (flop, turn, river) = (
        sizes("flop_bet", "flop_raise"),
        sizes("turn_bet", "turn_raise"),
        sizes("river_bet", "river_raise"),
    );
    let tree_config = TreeConfig {
        initial_state: BoardState::Flop,
        starting_pot,
        effective_stack: spec["effective_stack"].as_i64().unwrap() as i32,
        rake_rate: 0.0,
        rake_cap: 0.0,
        flop_bet_sizes: [flop.clone(), flop],
        turn_bet_sizes: [turn.clone(), turn],
        river_bet_sizes: [river.clone(), river],
        turn_donk_sizes: Some(DonkSizeOptions { donk: vec![] }),
        river_donk_sizes: Some(DonkSizeOptions::try_from(text("river_donk").as_str()).unwrap()),
        add_allin_threshold: 1.5,
        force_allin_threshold: 0.15,
        merging_threshold: 0.1,
    };
    let mut counter = ActionTree::new(tree_config.clone()).unwrap();
    let nodes = count_nodes(&mut counter);
    let action_tree = ActionTree::new(tree_config).unwrap();
    let mut game = PostFlopGame::with_config(card_config, action_tree).unwrap();
    let (memory, _) = game.memory_usage();
    let memory_gb = memory as f64 / 1e9;
    let compressed = memory_gb > spec["compress_over_gb"].as_f64().unwrap();
    game.allocate_memory(compressed);

    // Optional node lock: the BB (OOP) never folds to the IP's first flop bet after a check.
    let locked = spec["lock_bb_never_folds"].as_bool().unwrap_or(false);
    if locked {
        game.play(0); // OOP checks
        let bet = game
            .available_actions()
            .iter()
            .position(|a| matches!(a, Action::Bet(_)))
            .unwrap();
        game.play(bet); // IP bets its smallest size (33%)
        let actions = game.available_actions();
        let n = game.num_private_hands(game.current_player());
        let call = actions.iter().position(|a| matches!(a, Action::Call)).unwrap();
        let mut lock = vec![0.0f32; actions.len() * n];
        for h in 0..n {
            lock[call * n + h] = 1.0;
        }
        game.lock_current_strategy(&lock);
        game.back_to_root();
    }
    let build_s = start.elapsed().as_secs_f64();

    // postflop_solver::solve's loop, kept here to report the iteration count.
    let target = starting_pot as f32 * spec["target_pct"].as_f64().unwrap() as f32 / 100.0;
    let max_iterations = spec["max_iterations"].as_u64().unwrap() as u32;
    let mut exploitability = compute_exploitability(&game);
    let mut iterations = 0;
    for t in 0..max_iterations {
        if exploitability <= target {
            break;
        }
        solve_step(&game, t);
        iterations = t + 1;
        if (t + 1) % 10 == 0 || t + 1 == max_iterations {
            exploitability = compute_exploitability(&game);
        }
    }
    finalize(&mut game);
    let solve_s = start.elapsed().as_secs_f64() - build_s;

    // The flop root (OOP), and the IP's reply after a check.
    game.back_to_root();
    game.cache_normalized_weights();
    let (root_actions, root_freq, root_strategy, root_weights) = frequencies(&game);
    let n = root_weights.len();
    let readable = (0..n).all(|h| {
        let s: f32 = (0..root_actions.len()).map(|a| root_strategy[a * n + h]).sum();
        (s - 1.0).abs() < 1e-3
    });
    game.play(0);
    game.cache_normalized_weights();
    let (ip_actions, ip_freq, ip_strategy, ip_weights) = frequencies(&game);
    let equity = game.equity(1);
    let n = ip_weights.len();
    let mut order: Vec<usize> = (0..n).collect();
    order.sort_by(|&a, &b| equity[a].partial_cmp(&equity[b]).unwrap());
    let total: f32 = ip_weights.iter().sum();
    let (mut taken, mut weak_weight, mut weak_bet) = (0.0f32, 0.0f64, 0.0f64);
    let bets: Vec<usize> = (0..ip_actions.len()).filter(|&a| ip_actions[a] != "Check").collect();
    for &h in &order {
        if taken >= total / 3.0 {
            break;
        }
        taken += ip_weights[h];
        weak_weight += ip_weights[h] as f64;
        weak_bet += bets.iter().map(|&a| (ip_weights[h] * ip_strategy[a * n + h]) as f64).sum::<f64>();
    }

    let result = json!({
        "nodes": nodes,
        "memory_gb": memory_gb,
        "compressed": compressed,
        "locked": locked,
        "build_s": build_s,
        "solve_s": solve_s,
        "iterations": iterations,
        "exploitability": exploitability,
        "exploitability_pct": 100.0 * exploitability as f64 / starting_pot as f64,
        "readable": readable,
        "root_actions": root_actions,
        "root_freq": root_freq,
        "ip_after_check_actions": ip_actions,
        "ip_after_check_freq": ip_freq,
        "ip_weakest_third_bet_freq": weak_bet / weak_weight,
    });
    println!("{result}");
}
"""


def build() -> None:
    head = subprocess.run(
        ["git", "-C", str(SOLVER_DIR), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    if head != COMMIT:
        sys.exit(f"postflop-solver checkout is {head}, not DECISIONS 38's {COMMIT}")
    (BRIDGE / "src").mkdir(parents=True, exist_ok=True)
    (BRIDGE / "Cargo.toml").write_text(CARGO_TOML, encoding="utf-8")
    (BRIDGE / "src" / "main.rs").write_text(MAIN_RS, encoding="utf-8")
    # Rust 1.100 denies `dangerous_implicit_autorefs` by default; the 2023 solver trips it at
    # three lines of action_tree.rs. Ian chose to allow that one lint (2026-11-15).
    env = {
        **os.environ,
        "PATH": f"{CARGO_BIN}{os.pathsep}{os.environ['PATH']}",
        "RUSTFLAGS": "-A dangerous_implicit_autorefs",
    }
    subprocess.run(
        [str(CARGO_BIN / "cargo.exe"), f"+{TOOLCHAIN}", "build", "--release", "--quiet"],
        cwd=BRIDGE,
        env=env,
        check=True,
    )


@functools.cache
def _model() -> tuple[pm.PreflopModel, PreflopMatrix]:
    return pm.PreflopModel.load(), PreflopMatrix.load("data/preflop_169_exact.npz")


def model_range(stack: int, line: str, seat: str) -> str | None:
    """The preflop model's weighted range for one seat's line (DECISIONS 35), or None if unreached."""
    model, matrix = _model()
    solution = model.at(stack)
    if solution.reach(line, matrix.pair_counts) < 0.001:
        return None
    sb, bb = solution.line_factors(line)
    weights = sb if seat == "sb" else bb
    parts = [f"{CLASS_NAMES[k]}:{w:.4f}" for k, w in enumerate(weights) if w >= 0.0005]
    return ",".join(p[:-7] if p.endswith(":1.0000") else p for p in parts)


def solve(spot: str, flop: str, ip: str, oop: str, *, lock: bool = False) -> dict:
    pot, stack, _, _ = SPOTS[spot]
    spec = {
        "oop_range": oop,
        "ip_range": ip,
        "flop": flop,
        "starting_pot": pot,
        "effective_stack": stack,
        "lock_bb_never_folds": lock,
        **TREE,
        **SETTINGS,
    }
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            [str(EXE)], input=json.dumps(spec), capture_output=True, text=True, timeout=TIMEOUT
        )
        wall = time.perf_counter() - start
        result = json.loads(proc.stdout) if proc.returncode == 0 else {}
        timed_out = False
        error = None if proc.returncode == 0 else proc.stderr.strip()[-300:]
    except subprocess.TimeoutExpired:
        wall, result, timed_out, error = TIMEOUT, {}, True, None
    return {
        "spot": spot,
        "flop": flop,
        "seconds": round(TIMEOUT if timed_out else wall, 2),
        "timed_out": timed_out,
        "iterations": result.get("iterations"),
        "exploitability_pct": result.get("exploitability_pct"),
        "readable": result.get("readable", False),
        "nodes": result.get("nodes"),
        "memory_gb": result.get("memory_gb"),
        "compressed": result.get("compressed"),
        "build_s": result.get("build_s"),
        "ip_bet_after_check": sum(
            f for a, f in zip(result.get("ip_after_check_actions", []),
                              result.get("ip_after_check_freq", []), strict=True)
            if a != "Check"
        ) if result else None,
        "ip_weakest_third_bet": result.get("ip_weakest_third_bet_freq"),
        "error": error,
    }


def line(n: int, row: dict) -> str:
    expl = row["exploitability_pct"]
    return (
        f"{n:>3} {row['spot']:<7} {row['flop']}  {row['seconds']:>7.2f} s  "
        f"iter {row['iterations']}  expl {'-' if expl is None else f'{expl:.3f}'}%  "
        f"nodes {row['nodes']}  mem {row['memory_gb'] or 0:.2f} GB"
        f"{' (16-bit)' if row['compressed'] else ''}  read {'ok' if row['readable'] else 'NO'}"
        f"{'  TIMEOUT' if row['timed_out'] else ''}{'  ERROR ' + row['error'] if row['error'] else ''}"
    )


def main() -> int:
    build()
    RUNS.mkdir(parents=True, exist_ok=True)
    matrix = PreflopMatrix.load("data/preflop_169_exact.npz")
    ranges = {s: (S2.top_range(v[2], matrix), S2.top_range(v[3], matrix)) for s, v in SPOTS.items()}

    # --- Gate S4: S2's grid, ranges and bars --------------------------------------------------
    rows: list[dict] = []
    stopped = None
    for k, flop in enumerate(FLOPS):
        for spot in SPOTS:
            ip, oop = ranges[spot]
            rows.append(solve(spot, flop, ip, oop))
            print(line(len(rows), rows[-1]), flush=True)
        if k >= 1 and (stopped := S2.fail_certain(rows)):
            break
    with open(RUNS / "s4_results.csv", "w", newline="") as f:
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
    print("Gate S4:", "PASS" if passed else "FAIL")

    # --- Reported, not gated -------------------------------------------------------------------
    print("\nModel ranges (DECISIONS 35), first 5 flops; not gated:")
    lines = {"SRP": "rc", "3BP": "rrc"}
    n = 0
    for flop in FLOPS[:5]:
        for spot in SPOTS:
            depth, kind = MODEL_DEPTH[spot], spot[:3]
            ip = model_range(depth, lines[kind], "sb")
            oop = model_range(depth, lines[kind], "bb")
            if ip is None or oop is None:
                print(f"    {spot:<7} {flop}  skipped: the model almost never reaches this pot "
                      f"at {depth} bb")
                continue
            n += 1
            print(line(n, solve(spot, flop, ip, oop)), flush=True)

    print("\nNode lock, SRP50 on the first flop; not gated:")
    ip, oop = ranges["SRP50"]
    free = solve("SRP50", FLOPS[0], ip, oop)
    locked = solve("SRP50", FLOPS[0], ip, oop, lock=True)
    for label, row in (("unlocked", free), ("BB never folds to the 33% bet", locked)):
        print(f"    {label:<30} SB bets after a check {row['ip_bet_after_check']:.1%}, "
              f"weakest third {row['ip_weakest_third_bet']:.1%}  ({row['seconds']:.2f} s, "
              f"expl {row['exploitability_pct']:.3f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
