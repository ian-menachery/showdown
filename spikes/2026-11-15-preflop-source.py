r"""Spike S3, 2026-11-15: a heads-up preflop source above 20 bb (decision D3).

A measurement, not product code (SCOPE rules out "any abstraction beyond
push/fold"; DECISIONS 29 lets Phase 8 spikes measure). Nothing in src/ changes.
The write-up is docs/preflop-source.md.

The game, at effective stack S bb before the blinds (DECISIONS 22), blinds
0.5/1, no ante, hands bucketed into the 169 classes and dealt as class pairs
weighted by the exact card-removal counts (`pair_counts`), as in
src/showdown/games/pushfold.py:

    SB:              fold | raise to 2.5 | all-in
    BB vs raise:     fold | call | 3-bet to 7.5 (3x) | all-in
    SB vs 3-bet:     fold | call | all-in
    BB vs SB all-in: fold | call      (after the 3-bet, and at the root)
    SB vs BB all-in: fold | call      (BB jammed over the raise)

Payoffs to the SB, in bb:
- a fold loses what the folder put in;
- a called all-in nets S(2E - 1), with E the exact all-in equity of the class
  pair (data/preflop_169_exact.npz);
- a pot that reaches the flop with c bb from each player is valued, without
  playing it, at the SB's realized share of the pot: c(2·share - 1), with
  share = 1 - R_oop·(1 - E). The BB is out of position after the flop in
  heads-up, so it realizes R_oop of its equity, and the game stays zero-sum
  by giving what it forfeits to the SB (so the SB's effective R is >= 1).
  R_oop = 1 is a check-down; R_oop = 0.9 is "0.9 OOP / 1.0 IP".

The solver is our generic CFR+ on the compiled tree (`compile_game`,
`cfr_plus`, average policy; DECISIONS 14, 15), and `exploitability` is
NashConv / 2 in bb per hand (DECISIONS 7).

Checks:
1. Continuity: with the raise removed (SB: fold | all-in), the game is
   push/fold. At 20 bb, 1,000 iterations (as DECISIONS 22), it must reproduce
   data/pushfold.json's 20 bb solution.
2. Sanity: the SB can always play push/fold, and the BB's only answers to a
   jam are the same as in push/fold. So at 20 bb, the full game's SB value
   must be at least the push/fold value (less the two exploitabilities).

Run from the repo root. The 2026-11-15 run split the work over two processes
(about 30 minutes of wall time):

    .venv\Scripts\python -I spikes\2026-11-15-preflop-source.py --iterations 300 --stacks 20 25 --save <a.json>
    .venv\Scripts\python -I spikes\2026-11-15-preflop-source.py --iterations 300 --stacks 50 100 --skip-continuity --save <b.json>

`--save` writes every strategy and convergence curve as JSON; give it a path
outside the repo. The process drops itself to idle priority on Windows, so a
concurrent timing spike (S2) keeps the CPU first; its own timings are then
upper bounds.

Results, 2026-11-15 (300 CFR+ iterations per full-game solve):

- Tree: 485,538 nodes and 1,014 infosets at every depth (push/fold: 142,806
  and 338). Compiling takes 1 to 4 s. One iteration takes 0.8 to 0.9 s on an
  otherwise idle machine, and 2.3 s while S2's TexasSolver held all 16 cores,
  so a solve takes 4 to 5 minutes.
- Continuity: the jam-only 20 bb game reproduces data/pushfold.json exactly.
  The maximum difference in any push or call probability is 0, the
  exploitability is 2.822e-06 on both sides, and the SB value is -0.183190 on
  both. Gate D's rule scores push 168/168 (1 excluded) and call 169/169.
- Sanity at 20 bb: the full game's SB value beats push/fold's -0.1832 by
  +0.0547 (R_oop 1) and +0.1051 bb/hand (R_oop 0.9). The check passes.

  | Run | Exploitability (bb/hand) | SB value | SB fold / raise / jam | BB vs raise: fold / call / 3-bet / jam |
  |---|---|---|---|---|
  | 20 bb, R 1 | 2.3e-04 | -0.128 | 49% / 31% / 21% | 3% / 71% / 0% / 26% |
  | 20 bb, R 0.9 | 2.2e-04 | -0.078 | 43% / 50% / 7% | 17% / 53% / 0% / 30% |
  | 25 bb, R 1 | 2.6e-04 | -0.131 | 46% / 45% / 9% | 1% / 76% / 0% / 23% |
  | 25 bb, R 0.9 | 2.5e-04 | -0.059 | 41% / 57% / 2% | 15% / 56% / 0% / 29% |
  | 50 bb, R 1 | 7.2e-04 | -0.089 | 37% / 63% / 0% | 0% / 82% / 9% / 8% |
  | 50 bb, R 0.9 | 4.6e-04 | +0.037 | 27% / 73% / 0% | 9% / 70% / 0% / 21% |
  | 100 bb, R 1 | 1.6e-03 | -0.098 | 38% / 62% / 0% | 0% / 80% / 20% / 0% |
  | 100 bb, R 0.9 | 1.0e-03 | +0.122 | 16% / 84% / 0% | 5% / 78% / 11% / 6% |

- R moves the strategy far more than solver error does. At 100 bb the SB
  value swings by 0.22 bb/hand, and the mean total-variation distance at the
  main nodes is 0.09 to 0.41. docs/preflop-source.md has the details.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from showdown import pushfold as pf
from showdown.cfr import Tree, cfr_plus, compile_game, exploitability, policy_value
from showdown.equity.cards import CLASS_COMBOS, CLASS_NAMES
from showdown.equity.matrix import PreflopMatrix
from showdown.games.base import CHANCE, TERMINAL

MATRIX = "data/preflop_169_exact.npz"
PUSHFOLD = "data/pushfold.json"

FOLD, CALL, RAISE, JAM = 0, 1, 2, 3
ACTION_NAMES = ("fold", "call", "raise", "all-in")
CODE = "fcrj"
OPEN_TO = 2.5
THREEBET_TO = 3 * OPEN_TO

_ACTIONS: dict[tuple[int, ...], tuple[int, ...]] = {
    (): (FOLD, RAISE, JAM),
    (RAISE,): (FOLD, CALL, RAISE, JAM),
    (RAISE, RAISE): (FOLD, CALL, JAM),
    (RAISE, RAISE, JAM): (FOLD, CALL),
    (RAISE, JAM): (FOLD, CALL),
    (JAM,): (FOLD, CALL),
}
NODE_LABELS = {
    "": "SB first in",
    "r": "BB vs 2.5 bb raise",
    "rr": "SB vs 3-bet",
    "rrj": "BB vs SB 4-bet jam",
    "rj": "SB vs BB jam",
    "j": "BB vs SB jam",
}
COMBOS = np.array([len(c) for c in CLASS_COMBOS], dtype=float)


# --- the game --------------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class _Table:
    stack: float
    raises: bool
    allin: np.ndarray
    """[i, j]: SB's net on a called all-in, S(2E - 1)."""
    flop_open: np.ndarray
    """[i, j]: SB's net when the 2.5 bb raise is called."""
    flop_3bet: np.ndarray
    """[i, j]: SB's net when the 3-bet is called."""
    outcomes: tuple[tuple[int, float], ...]


@dataclass(frozen=True)
class PreflopState:
    table: _Table
    deal: int = -1
    history: tuple[int, ...] = ()

    def current_player(self) -> int:
        if self.deal < 0:
            return CHANCE
        if self.history and self.history[-1] in (FOLD, CALL):
            return TERMINAL
        return len(self.history) % 2

    def legal_actions(self) -> tuple[int, ...]:
        if not self.history and not self.table.raises:
            return (FOLD, JAM)
        return _ACTIONS[self.history]

    def chance_outcomes(self) -> tuple[tuple[int, float], ...]:
        return self.table.outcomes

    def child(self, action: int) -> PreflopState:
        if self.deal < 0:
            return PreflopState(self.table, action)
        return PreflopState(self.table, self.deal, self.history + (action,))

    def returns(self) -> tuple[float, float]:
        h, t = self.history, self.table
        ij = divmod(self.deal, 169)
        if h[-1] == FOLD:
            u = {
                (FOLD,): -0.5,
                (RAISE, FOLD): 1.0,
                (JAM, FOLD): 1.0,
                (RAISE, RAISE, FOLD): -OPEN_TO,
                (RAISE, JAM, FOLD): -OPEN_TO,
                (RAISE, RAISE, JAM, FOLD): THREEBET_TO,
            }[h]
        elif h == (RAISE, CALL):
            u = float(t.flop_open[ij])
        elif h == (RAISE, RAISE, CALL):
            u = float(t.flop_3bet[ij])
        else:  # a called all-in
            u = float(t.allin[ij])
        return (u, -u)

    def information_state(self) -> str:
        sb, bb = divmod(self.deal, 169)
        player = len(self.history) % 2
        name = CLASS_NAMES[sb] if player == 0 else CLASS_NAMES[bb]
        return f"{('SB', 'BB')[player]}:{name}:{''.join(CODE[a] for a in self.history)}"


class PreflopGame:
    """The S3 preflop game at `stack` bb; `r_oop` is the BB's postflop realization."""

    name = "preflop-s3"

    def __init__(
        self, stack: float, matrix: PreflopMatrix, *, r_oop: float = 1.0, raises: bool = True
    ) -> None:
        if raises and stack <= THREEBET_TO:
            raise ValueError(f"the 3-bet to {THREEBET_TO} bb needs a stack above it")
        weights = matrix.pair_counts.astype(np.int64)
        total = int(weights.sum())
        outcomes = tuple(
            (169 * i + j, int(weights[i, j]) / total) for i in range(169) for j in range(169)
        )
        e = matrix.equity
        share = 1.0 - r_oop * (1.0 - e)
        self.stack, self.r_oop, self.raises = float(stack), float(r_oop), raises
        self._table = _Table(
            stack=self.stack,
            raises=raises,
            allin=self.stack * (2 * e - 1),
            flop_open=OPEN_TO * (2 * share - 1),
            flop_3bet=THREEBET_TO * (2 * share - 1),
            outcomes=outcomes,
        )

    def initial_state(self) -> PreflopState:
        return PreflopState(self._table)

    def action_name(self, action: int) -> str:
        return ACTION_NAMES[action]


# --- solving and reading the strategy ---------------------------------------------------


@dataclass
class Run:
    label: str
    stack: float
    r_oop: float
    raises: bool
    iterations: int
    nodes: int
    infosets: int
    compile_s: float
    solve_s: float
    curve: list[tuple[int, float]]
    """(iteration, exploitability in bb per hand) at each checkpoint."""
    value_sb: float
    strategy: dict[str, tuple[tuple[int, ...], np.ndarray]]
    """Per node history: (actions, 169 x len(actions) probabilities)."""

    @property
    def exploitability(self) -> float:
        return self.curve[-1][1]


def read_strategy(tree: Tree, policy) -> dict[str, tuple[tuple[int, ...], np.ndarray]]:
    index = {name: k for k, name in enumerate(CLASS_NAMES)}
    out: dict[str, tuple[tuple[int, ...], np.ndarray]] = {}
    for key, actions, probs in zip(tree.infoset_key, tree.infoset_actions, policy, strict=True):
        _, name, hist = key.split(":")
        if hist not in out:
            out[hist] = (actions, np.full((169, len(actions)), np.nan))
        out[hist][1][index[name]] = probs
    for hist, (_, table) in out.items():
        if np.isnan(table).any():
            raise ValueError(f"node {hist!r} is missing classes")
    return out


def solve(
    label: str,
    stack: float,
    matrix: PreflopMatrix,
    *,
    r_oop: float = 1.0,
    raises: bool = True,
    iterations: int,
    checkpoints: tuple[int, ...] = (),
) -> Run:
    t0 = time.perf_counter()
    tree = compile_game(PreflopGame(stack, matrix, r_oop=r_oop, raises=raises))
    t1 = time.perf_counter()
    solver = cfr_plus(tree)
    curve: list[tuple[int, float]] = []
    solve_s = 0.0
    for stop in sorted({c for c in checkpoints if c < iterations} | {iterations}):
        s = time.perf_counter()
        solver.iterate(stop - solver.iteration)
        solve_s += time.perf_counter() - s
        curve.append((stop, exploitability(tree, solver.average_policy())))
        print(f"  {label}: it {stop:>5}  exploitability {curve[-1][1]:.2e} bb  "
              f"({solve_s:.0f} s solving)", flush=True)
    average = solver.average_policy()
    return Run(
        label=label,
        stack=float(stack),
        r_oop=r_oop,
        raises=raises,
        iterations=iterations,
        nodes=tree.num_nodes,
        infosets=tree.num_infosets,
        compile_s=t1 - t0,
        solve_s=solve_s,
        curve=curve,
        value_sb=policy_value(tree, average),
        strategy=read_strategy(tree, average),
    )


def reach_weights(run: Run, hist: str) -> np.ndarray:
    """Combos of the acting player's classes that reach `hist`, by its own earlier actions.

    Card removal against the opponent's range is ignored: this is for range sizes only.
    """
    w = COMBOS.copy()
    actor = len(hist) % 2
    for k in range(actor, len(hist), 2):
        actions, table = run.strategy[hist[:k]]
        w = w * table[:, actions.index(CODE.index(hist[k]))]
    return w


def range_shares(run: Run, hist: str) -> dict[str, float]:
    """Share of the reaching combos that take each action at node `hist`."""
    actions, table = run.strategy[hist]
    w = reach_weights(run, hist)
    return {ACTION_NAMES[a]: float(w @ table[:, k] / w.sum()) for k, a in enumerate(actions)}


def tv_distance(a: Run, b: Run, hist: str) -> float:
    """Mean total-variation distance between two runs' actions at `hist`, weighted by a's reach."""
    w = reach_weights(a, hist)
    tv = 0.5 * np.abs(a.strategy[hist][1] - b.strategy[hist][1]).sum(axis=1)
    return float(w @ tv / w.sum())


def pure_action(table: np.ndarray) -> np.ndarray:
    """Index of the action played with probability >= 0.99, or -1 (DECISIONS 22's rule)."""
    best = table.argmax(axis=1)
    return np.where(table.max(axis=1) >= pf.PURE, best, -1)


def switches(a: Run, b: Run, hist: str) -> list[str]:
    """Classes pure in both runs at `hist` whose pure action differs."""
    actions = a.strategy[hist][0]
    pa, pb = pure_action(a.strategy[hist][1]), pure_action(b.strategy[hist][1])
    return [
        f"{CLASS_NAMES[k]} {ACTION_NAMES[actions[pa[k]]]}->{ACTION_NAMES[actions[pb[k]]]}"
        for k in np.flatnonzero((pa >= 0) & (pb >= 0) & (pa != pb))
    ]


def mixed_share(run: Run, hist: str) -> float:
    """Share of reaching combos whose action at `hist` is mixed (no action >= 0.99)."""
    w = reach_weights(run, hist)
    return float(w @ (pure_action(run.strategy[hist][1]) < 0) / w.sum())


# --- reporting ----------------------------------------------------------------------------


def print_run(run: Run) -> None:
    print(f"\n### {run.label}")
    print(f"tree {run.nodes:,} nodes, {run.infosets} infosets; compile {run.compile_s:.1f} s, "
          f"{run.iterations} iterations in {run.solve_s:.0f} s "
          f"({run.solve_s / run.iterations:.2f} s each)")
    print("exploitability (bb/hand) by iteration: "
          + ", ".join(f"{i}: {e:.2e}" for i, e in run.curve))
    print(f"SB value {run.value_sb:+.4f} bb/hand")
    print("| Node | " + " | ".join(ACTION_NAMES) + " | mixed |")
    print("|---|---|---|---|---|---|")
    for hist in run.strategy:
        shares = range_shares(run, hist)
        cells = [f"{shares[a]:.1%}" if a in shares else "" for a in ACTION_NAMES]
        print(f"| {NODE_LABELS[hist]} | " + " | ".join(cells) + f" | {mixed_share(run, hist):.1%} |")


def to_json(run: Run) -> dict:
    return {
        "label": run.label,
        "stack": run.stack,
        "r_oop": run.r_oop,
        "raises": run.raises,
        "iterations": run.iterations,
        "nodes": run.nodes,
        "infosets": run.infosets,
        "compile_s": run.compile_s,
        "solve_s": run.solve_s,
        "curve": run.curve,
        "value_sb": run.value_sb,
        "strategy": {
            hist: {
                ACTION_NAMES[a]: dict(zip(CLASS_NAMES, table[:, k].tolist(), strict=True))
                for k, a in enumerate(actions)
            }
            for hist, (actions, table) in run.strategy.items()
        },
    }


def continuity(matrix: PreflopMatrix) -> Run:
    print("\n## Continuity: 20 bb, jam-only branch, 1,000 iterations vs data/pushfold.json")
    run = solve("20 bb jam-only", 20, matrix, raises=False, iterations=1000,
                checkpoints=(100, 500))
    ref = pf.PushFoldSolution.load(PUSHFOLD).at(20)
    root_actions, root = run.strategy[""]
    call_actions, call = run.strategy["j"]
    push = root[:, root_actions.index(JAM)]
    calls = call[:, call_actions.index(CALL)]
    cp, cc = pf.compare(push, ref.push), pf.compare(calls, ref.call)
    print(f"tree {run.nodes:,} nodes (push/fold: 142,806), {run.infosets} infosets; "
          f"{run.solve_s / run.iterations:.2f} s per iteration")
    print(f"max |push diff| {np.abs(push - ref.push).max():.2e}, "
          f"max |call diff| {np.abs(calls - ref.call).max():.2e}")
    print(f"exploitability {run.exploitability:.3e} (pushfold.json {ref.exploitability:.3e}); "
          f"SB value {run.value_sb:+.6f} (pushfold.json {ref.value_sb:+.6f})")
    print(f"Gate D rule: push {cp.agree}/{cp.compared} ({cp.excluded} excluded), "
          f"call {cc.agree}/{cc.compared} ({cc.excluded} excluded)")
    return run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--iterations", type=int, default=300,
                        help="CFR+ iterations per full-game solve (default 300)")
    parser.add_argument("--stacks", type=float, nargs="+", default=[20, 25, 50, 100])
    parser.add_argument("--r-oop", type=float, nargs="+", default=[1.0, 0.9])
    parser.add_argument("--skip-continuity", action="store_true")
    parser.add_argument("--save", type=Path, help="write every run as JSON here")
    args = parser.parse_args()

    if sys.platform == "win32":  # leave the CPU to S2's timed solves first
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), 0x00000040)  # IDLE

    started = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"S3 preflop spike, started {started}")
    matrix = PreflopMatrix.load(MATRIX)
    runs: list[Run] = []
    if not args.skip_continuity:
        runs.append(continuity(matrix))

    checkpoints = (50, 100, 200)
    full: dict[tuple[float, float], Run] = {}
    for stack in args.stacks:
        for r in args.r_oop:
            label = f"{stack:g} bb, R_oop {r:g}"
            print(f"\n## {label}", flush=True)
            run = solve(label, stack, matrix, r_oop=r, iterations=args.iterations,
                        checkpoints=checkpoints)
            full[(stack, r)] = run
            runs.append(run)
            print_run(run)

    print("\n## How the ranges move with R (R_oop 1 vs 0.9)")
    print("Mean total-variation distance per node (0 = same strategy, 1 = disjoint),")
    print("weighted by the R = 1 reach, and classes whose pure action flips.")
    rs = sorted(args.r_oop, reverse=True)
    for stack in args.stacks:
        if len(rs) < 2:
            break
        a, b = full[(stack, rs[0])], full[(stack, rs[1])]
        print(f"\n{stack:g} bb: SB value {a.value_sb:+.4f} -> {b.value_sb:+.4f}")
        for hist in a.strategy:
            sa, sb = range_shares(a, hist), range_shares(b, hist)
            moves = ", ".join(f"{k} {sa[k]:.1%}->{sb[k]:.1%}" for k in sa)
            flips = switches(a, b, hist)
            print(f"  {NODE_LABELS[hist]:<20} TV {tv_distance(a, b, hist):.3f}; {moves}")
            if flips:
                print(f"    pure flips ({len(flips)}): {', '.join(flips)}")

    if 20 in args.stacks and not args.skip_continuity:
        ref = pf.PushFoldSolution.load(PUSHFOLD).at(20)
        print("\n## 20 bb: the full game vs push/fold")
        for r in args.r_oop:
            run = full[(20, r)]
            bound = ref.value_sb - ref.exploitability - run.exploitability
            print(f"R_oop {r:g}: full-game SB value {run.value_sb:+.4f}, push/fold "
                  f"{ref.value_sb:+.4f}; gain {run.value_sb - ref.value_sb:+.4f} bb/hand; "
                  f"sanity (full >= push/fold - exploitabilities): "
                  f"{'ok' if run.value_sb >= bound else 'FAILED'}")

    for stack in args.stacks:
        for r in args.r_oop:
            run = full[(stack, r)]
            print(f"\nSB first-in chart, {run.label}: raise % (then all-in %)")
            actions, table = run.strategy[""]
            print(pf.chart(table[:, actions.index(RAISE)]))
            print(pf.chart(table[:, actions.index(JAM)]))

    if args.save:
        args.save.write_text(json.dumps([to_json(r) for r in runs]) + "\n", encoding="utf-8")
        print(f"\nsaved {len(runs)} runs to {args.save}")
    print(f"\nfinished {time.strftime('%Y-%m-%d %H:%M:%S')} (started {started})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
