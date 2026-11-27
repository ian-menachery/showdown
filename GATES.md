# Gate results

One section per gate in SCOPE, filled in when the gate is run. The thresholds
come from SCOPE and were set before the code existed. Each row gives the
measured number, the bar it had to clear, and PASS or FAIL. Re-run the evidence
with the command shown. Fast checks run on every `py gate.py`; slow ones run on
`py gate.py --full`.

Machine: Ian's Windows laptop, Python 3.12.10, 16 cores.

---

## Gate A: Kuhn: PASS (2026-11-14)

Evidence: `tests/test_gate_a.py` and `tests/test_cfr_kuhn_oracle.py`, both in the
fast suite. Solver: `cfr_plus`, 1,000 iterations, average policy.

| Check | Measured | Bar | Result |
|---|---|---|---|
| Uniform-policy exploitability vs OpenSpiel | ours 0.4583333333333333, OpenSpiel 0.4583333333333333, difference 0 | ≤ 1e-9 | PASS |
| CFR+ exploitability after 1,000 iterations | 8.74e-5 | < 1e-3 | PASS |
| Player 1 game value | -0.055556 (off -1/18 by 3.6e-7) | within 1e-3 of -1/18 | PASS |
| Bet J with α ∈ [0, 1/3] | α = 0.2165 | -0.02 to 0.3533 | PASS |
| Bet K with 3α | 0.6514 vs 0.6494 | ± 0.02 | PASS |
| Call with Q at α + 1/3 | 0.5505 vs 0.5498 | ± 0.02 | PASS |

Beyond the gate:
- Our CFR, CFR+ and both simultaneous-update variants reproduce OpenSpiel's
  average and current policies at iterations 1, 2, 3, 10 and 60. When first
  recorded this was to 1e-10. Since DECISIONS 17 it is exact equality, and the
  test asserts exact equality.
- Exploitability matches OpenSpiel to 1e-9 on three seeded random policies.
- Player 2's unique equilibrium holds within 0.02.

```
showdown solve kuhn --iterations 1000
```

---

## Gate B: Leduc: PASS (2026-11-14)

Evidence: `tests/test_cfr_leduc_oracle.py` (fast suite) and `tests/test_gate_b.py`
(slow suite, `py gate.py --full`). Solver: `cfr_plus`, 200 iterations, average
policy.

| Check | Measured | Bar | Result |
|---|---|---|---|
| Exploitability vs OpenSpiel, uniform policy | match to 1e-9 (2.3736111111) | ≤ 1e-9 | PASS |
| Exploitability vs OpenSpiel, seeded random policy | match to 1e-9 | ≤ 1e-9 | PASS |
| Exploitability vs OpenSpiel, CFR+ iterate (25 iterations) | match to 1e-9 | ≤ 1e-9 | PASS |
| CFR+ exploitability at iteration 200 | ours 0.0049631295504932865, OpenSpiel 0.0049631295504932865, ratio 1.000 | ≤ 1.10× | PASS |
| Wall time for 200 iterations | ours 2.38 s, OpenSpiel 27.35 s | no slower | PASS |

Beyond the gate:
- Our CFR+ is **bit-identical** to OpenSpiel's `CFRPlusSolver`: every average and
  current policy entry is equal at every one of the 200 iterations
  (DECISIONS 17).
- The lockstep walk confirms our Leduc has the same structure as OpenSpiel's at
  all 9,457 nodes (157 chance, 3,780 decision, 5,520 terminal) and the same 936
  infosets.
- After 1,000 iterations (12 s), exploitability is 2.57e-4 and player 1's value
  is -0.08559.
- The first gate run failed the extra bit-identity test: 0.0050008 against
  0.0049631, though both gate bars passed even then. The cause was found and
  fixed before this result was recorded; see DECISIONS 17.
- Wall times move with machine load. OpenSpiel took 27.4 s here, 60.7 s in the
  Phase 3 full-suite run, and 101 s in the Phase 0 spike. Ours took 2.4 s here
  and 16.9 s in the Phase 3 run. Ours was faster in every recorded run, by 3.6×
  to 11.5×.

```
showdown solve leduc --iterations 200
py gate.py --full
```

---

## Gate C: equity: PASS (2026-11-14)

Evidence: `tests/test_gate_c.py` (fast suite) and `tests/test_gate_c_slow.py`
(slow suite). The matrix is `data/preflop_169.npz`: 147,200 boards in 64
batches, seed 20261114, 1,290 s on 16 cores (DECISIONS 18).

| Check | Measured | Bar | Result |
|---|---|---|---|
| eval7 vs phevaluator on random 7-card showdowns | 100,000 of 100,000 agree | all agree | PASS |
| AsAh vs KdKc, exact over 1,712,304 boards | win 0.8106458, tie 0.0038182, equity 0.8125549 | 0.81065 / 0.00382 / 0.81255 ± 1e-5 | PASS |
| 20 matchups (3 preflop, 8 flop, 6 turn, 3 river): eval7 enumeration vs phevaluator enumeration | 20 of 20 identical (win, tie, outcome count) | exact | PASS |
| Same 20 matchups vs pokerkit `calculate_equities`, 4,000 samples each | 20 of 20 within 3 SE (re-run on 2026-11-14 with a reproducible oracle, DECISIONS 28: max \|z\| 2.14) | within 3 SE | PASS |
| Monte Carlo calibration: AsAh vs KdKc, 1,000 samples, 200 seeds | 189 of 200 within ±2 SE (0.945) | 0.90 to 0.99 (0.954 expected) | PASS |
| Matrix symmetry M[i,j] + M[j,i] = 1 | exact, holds by construction (DECISIONS 18) | within cell error | PASS |
| Matrix SE, off-diagonal cells | max 0.00169, median 0.00116 | every cell ≤ 0.002 | PASS |

The pokerkit SE is sqrt(e(1−e)/n) taken at the exact equity e. That is an upper
bound on the standard deviation of any [0, 1] score with mean e.

Beyond the gate, the matrix was checked against exact class-vs-class
enumeration. Suit-isomorphic combo pairs share one enumeration.

| Cell | Matrix | Exact | Off by |
|---|---|---|---|
| AA vs KK | 0.81939 ± 0.00099 | 0.81946 | 0.07 SE |
| AKs vs QQ | 0.45945 ± 0.00141 | 0.46049 | 0.74 SE |
| T9s vs AKo | 0.40559 ± 0.00103 | 0.40524 | 0.34 SE |

The card-removal pair counts are exact. They total 1,326 × 1,225 = 1,624,350
ordered combo pairs. For example, AA vs KK has 36 pairs and AKo vs AA has 36.

**Every cell against exact equity (added 2026-11-14, after the gate).** This
check uses b-inary/poker-cfr's exact equity table for every combo pair
(DECISIONS 20; `spikes/2026-11-14-reference-data.py`).

First, the table was checked against our own engine:
- 8 of 8 combo pairs, AsAh vs KdKc among them, gave the same integer
  2 × wins + ties as our exhaustive enumeration.
- Its card-removal pair counts equal ours.

Against the table, over all 14,196 distinct off-diagonal cells:

| Measure | Value | What a well-calibrated SE gives |
|---|---|---|
| Within 2 SE | 97.2% | 95.4% |
| Within 3 SE | 99.86% | 99.73% |
| Largest \|z\| | 3.83 (T4s vs 33: 0.48313 ± 0.00112, exact 0.48742) | about 3.9 for 14,196 draws |
| Standard deviation of z | 0.93 | 1 |
| Largest \|error\| | 0.00463 | — |
| Mean \|error\| | 0.00086 | — |

The standard errors are honest and slightly conservative. The average signed
error is -0.0001. Every cell is scored on the same boards, so cell errors are
correlated, and that average is not an independent test of bias. It is worth
0.004 bb at 20 bb.

**The exact matrix (added 2026-11-14, DECISIONS 21).** `data/preflop_169_exact.npz`
enumerates all 2,598,960 boards. It does so through one board from each of the
134,459 suit-relabelling classes, weighted by class size. The build took 1,063 s
on 16 cores.

| Check | Result |
|---|---|
| Every cell vs b-inary's exact table (`tests/test_matrix_exact_slow.py`) | 28,561 of 28,561 equal, to the integer |
| Live-pair counts vs exact card-removal counts × C(48,5), checked inside the build | all equal |
| AA vs KK, AKs vs QQ, T9s vs AKo vs exact class-vs-class enumeration | 0.819461, 0.460485, 0.405237, all within 5e-6 |
| Monte Carlo matrix vs exact (`tests/test_matrix_exact.py`) | largest \|z\| 3.83; 97.2% within 2 SE |
| One board's block sums vs brute force, 3 class pairs | equal |
| Block sums unchanged when the board's suits are relabelled | equal |

```
showdown matrix build --exact   # about 18 minutes on 16 cores; reproduces the committed file
```

Bugs found by these tests before the gate was declared:
- **Range parser.** It upper-cased only the first two characters of a token, so
  "A2s-A5s" failed. Fixed.
- **A wrong hand count, in the test rather than the code.** The test claimed
  16/44 winning rivers for AsKs vs QhQd on Ts9s2dJc. The code said 13/44, and
  the code was right: a king gives QQ the straight K-Q-J-T-9. The test was
  corrected, with that reasoning written into it.

**Note added 2026-11-14 (DECISIONS 28).** The pokerkit comparison was not
reproducible as first written. pokerkit's sample depends on Python's
per-process string hashing, so `random.seed` alone did not fix it. The
final full run of the autonomous stretch drew one case beyond 3 SE. The
oracle now runs with a fixed hash seed. The bar is unchanged, and all 20
cases pass, identically on repeated runs.

Full-suite run: 156 passed in 4 min 57 s, coverage 99%. In that run Gate B
measured ours at 16.9 s against OpenSpiel's 60.7 s, which still passes. The
machine was loaded, and both timings were slower than the Phase 2 run.

```
showdown equity AsAh KdKc
showdown matrix build          # about 20 minutes on 16 cores; reproduces the committed file
showdown matrix show AKs QQ
py gate.py --full
```

---

## Gate D: push/fold: PASS (2026-11-14)

Evidence: `tests/test_gate_d.py` (fast suite) and `tests/test_gate_d_slow.py`
(slow suite, which needs `data/external/`). The rule was pre-registered in
DECISIONS 22 before the solve. The solution is `data/pushfold.json`:
- `cfr_plus`, 1,000 iterations at each of 1 to 20 bb, average policy;
- payoffs from the exact matrix (DECISIONS 21);
- 1,242 s on 16 cores.

The reference is HoldemResources' no-ante raw data (DECISIONS 20).

| Check | Measured | Bar | Result |
|---|---|---|---|
| Exploitability at every depth, by our best response on the compiled tree | max 3.6e-6 bb (17 bb); min 7.5e-7 (1 bb) | ≤ 0.001 bb at all 20 depths | PASS |
| SB jams all 169 classes at 1 bb | 169 of 169 at p ≥ 0.99 | all 169 | PASS |
| Pusher vs HoldemResources, 20 depths | 100% of compared classes agree at every depth; 0 to 3 classes excluded as mixed | ≥ 95% at every depth | PASS |
| Caller vs HoldemResources, 20 depths | 100% of compared classes agree at every depth; 0 to 2 classes excluded as mixed | ≥ 95% at every depth | PASS |
| 10 bb re-solved from scratch | identical push and call vectors and exploitability | identical | PASS |

No depth excluded more than 3 classes. The 10% finding threshold is 17.

| Stack (bb) | Exploitability | SB value (bb) | SB jams | BB calls | Push: agree/compared (excluded) | Call: agree/compared (excluded) |
|---|---|---|---|---|---|---|
| 1 | 7.5e-7 | +0.00000 | 100.0% | 100.0% | 169/169 (0) | 169/169 (0) |
| 2 | 2.2e-6 | +0.00955 | 89.8% | 100.0% | 168/168 (1) | 169/169 (0) |
| 3 | 1.6e-6 | +0.05159 | 77.8% | 92.3% | 167/167 (2) | 168/168 (1) |
| 4 | 1.0e-6 | +0.06603 | 73.8% | 74.1% | 169/169 (0) | 169/169 (0) |
| 5 | 2.0e-6 | +0.05620 | 71.5% | 62.1% | 168/168 (1) | 167/167 (2) |
| 6 | 2.2e-6 | +0.03816 | 68.5% | 54.4% | 166/166 (3) | 169/169 (0) |
| 7 | 1.8e-6 | +0.01686 | 66.3% | 48.6% | 168/168 (1) | 168/168 (1) |
| 8 | 2.5e-6 | -0.00414 | 61.9% | 45.0% | 166/166 (3) | 168/168 (1) |
| 9 | 2.7e-6 | -0.02523 | 60.0% | 40.6% | 167/167 (2) | 168/168 (1) |
| 10 | 1.8e-6 | -0.04537 | 58.3% | 37.4% | 168/168 (1) | 168/168 (1) |
| 11 | 1.6e-6 | -0.06466 | 54.5% | 35.0% | 168/168 (1) | 168/168 (1) |
| 12 | 1.7e-6 | -0.08253 | 53.3% | 33.0% | 168/168 (1) | 169/169 (0) |
| 13 | 2.3e-6 | -0.09902 | 51.6% | 30.9% | 167/167 (2) | 167/167 (2) |
| 14 | 2.0e-6 | -0.11382 | 48.4% | 29.3% | 167/167 (2) | 168/168 (1) |
| 15 | 2.1e-6 | -0.12723 | 45.7% | 28.5% | 167/167 (2) | 168/168 (1) |
| 16 | 2.5e-6 | -0.13932 | 44.8% | 26.5% | 166/166 (3) | 167/167 (2) |
| 17 | 3.6e-6 | -0.15081 | 42.9% | 24.8% | 168/168 (1) | 168/168 (1) |
| 18 | 2.9e-6 | -0.16216 | 42.3% | 23.8% | 167/167 (2) | 168/168 (1) |
| 19 | 2.5e-6 | -0.17291 | 40.9% | 22.6% | 169/169 (0) | 169/169 (0) |
| 20 | 2.8e-6 | -0.18319 | 40.1% | 21.7% | 168/168 (1) | 169/169 (0) |

"SB jams" and "BB calls" are shares of the 1,326 starting hands. There were no
disagreements at any depth.

Beyond the gate (`spikes/2026-11-14-gate-d-report.py`), HoldemResources' own
strategies were scored on our exact game:
- Their SB value matches ours to 5 decimals at all 20 depths.
- Their exploitability on our game is at most 1.0e-6 bb (13 bb). So their
  equilibrium is an equilibrium of our game too.
- The largest per-class probability gap is 0.52, at 6 bb. It is in classes that
  one side mixes. Those are the excluded classes, and the strategies are
  equally good there.

Other checks, in the fast suite:
- The tree's value and exploitability equal closed-form sums to 1e-12 on random
  and pure strategies.
- At 1 bb, "jam and call everything" has exploitability 0.

```
showdown pushfold build          # about 20 minutes on 16 cores; reproduces data/pushfold.json
showdown pushfold chart 10
py gate.py --full
```

---

## Gate E: bot and engine: PASS (2026-11-14)

Evidence: `tests/test_gate_e.py` (fast suite) and `tests/test_gate_e_slow.py`
(slow suite). The design is in DECISIONS 23 and 24.

| Check | Measured | Bar | Result |
|---|---|---|---|
| 20,000 bot-vs-bot hands at 10 bb through pokerkit's state machine (seed 20261114) | realised SB −0.03940 bb/hand, SE 0.03202 (SD 4.528); solver value −0.04537; z = +0.19 | within 3 SE | PASS |
| A scripted human seat through the play page's HTTP API, push/fold | 20 hands: alternating seats at 10 bb, BB at random depth, SB at 1 bb, BB at 2 bb | 20 complete hands | PASS |
| A scripted human seat through the HTTP API, Leduc | 20 hands: alternating and second seat, with random legal actions | 20 complete hands | PASS |

Backstops. The 3 SE test alone is too weak to catch a seat swap or a
chip-unit error; see risk 1 in the design review.
- **Every simulated hand's payoff fits the model:** −0.5, +1 or ±10. Every
  called hand's winner agrees with our own evaluator (`evaluate`), so pokerkit's
  showdown and ours never disagree.
- **Jam rate:** 0.5804 against the solution's 0.5828 (0.8 SE).
- **Call rate:** 0.3601 against 0.3664 (1.4 SE). The bar is 4 SE.
- **Seats:** pokerkit's heads-up state has player 0 posting 2 chips (BB) and
  player 1 posting 1 (SB), and the SB acts first. A fixed-card AA vs KK hand
  pays exactly −0.5, +1 and +10. A split pays 0. At 1 bb the BB has no
  decision.
- **API scripts:**
  - Every finished hand's result fits the model.
  - The bot's cards never appear before the hand ends.
  - Summary totals equal the sum of the per-hand grades and results.
  - Host-header and token checks return 403. Bad bodies return 400 or 413.
  - Every route the page calls exists, and the page loads nothing from the
    network.
- **Grading:** the per-class best-response sums reproduce
  `closed_form_exploitability` to 1e-12. Every action that Nash plays purely
  loses less than 0.001 bb at 2, 10 and 20 bb.

**Done 3, checked by hand in the browser pane on 2026-11-14:**
- A push/fold session at a fixed 10 bb, alternating seats. It showed a graded
  mistake (T5o jam: "Lost 0.239 bb", Nash jams 0%), a Nash-consistent BB fold
  (96s), the board and the bot's cards after a call, and the summary.
- A random-depth session (4 bb, then 19 bb), including a bot fold.
- A Leduc session: two hands covering a check-call-showdown, the public card,
  a bot fold, and both seats.

```
showdown play                 # opens http://127.0.0.1:<port>/
py gate.py --full
```

---

## Gate F: analyzer: PASS (2026-11-14)

Evidence: `tests/test_gate_f.py` (fast suite) and `tests/test_gate_f_slow.py`
(slow suite, which needs `data/external/phh`). The design is in DECISIONS 25 to
27, and the pokerkit facts behind it are in `docs/design-review-phases-5-6.md`.

| Check | Measured | Bar | Result |
|---|---|---|---|
| Hand-built fixture (`tests/fixtures/hh/`) | 34 hands: 31 PHH (3-handed, 6-max and heads-up) and 3 PokerStars text. 105 player rows; all 945 hand-counted values (8 flags and the net result per player per hand) match exactly | ≥ 30 hands, every stat exact | PASS |
| All-in EV adjustment against hand-computed values | 17 values in 8 hands, all within 1e-6 bb (see below) | 1e-6 bb | PASS |
| Pluribus hands (phh-dataset, commit e47fbd5) | 10,000 of 10,000 parse and reconcile with the recorded finishing stacks; 8 of them are odd-chip chops (DECISIONS 25) | ≥ 99%, failures printed | PASS |

The 8 all-in hands and how their EVs were computed by hand:
- **4 preflop heads-up all-ins.** These use the exact integers 2 × wins + ties
  from b-inary's independent table, which DECISIONS 21 verified against our
  own enumeration.
- **AA vs 22 on a flop.** 22 wins 83 of 990 runouts: 87 runouts contain a
  deuce, less 4 where AA makes a higher set.
- **Two turn all-ins, AA vs KK.** AA wins 42 of 44 rivers.
- **A 3-way turn all-in with a side pot.** The main pot splits 38:2:2 and the
  side pot 40:2, over 42 rivers.

Each hand's counting is written beside its expected values in
`tests/fixtures/hh/expected.toml`.

How the fixture was made:
- The expected values were written before the analyzer ran on these hands.
- A re-check, before any run, corrected one flag (a non-showdown in h06) and
  three EV decimals that had been slips of hand arithmetic.
- Each fixture hand's finishing stacks were counted by hand and checked
  against pokerkit's replay.
- That check caught a bug in the scratch helper that writes the fixture's show
  actions. pokerkit's history iterator "repairs" a hand that has no show
  actions by showing nothing and splitting the pot, so the helper never saw a
  show was needed. This is the silent split that the parse rule exists to
  catch.

Push/fold grading on the fixture:
- 11 decisions are graded across 7 heads-up hands, at the depths counted by
  hand: 1, 8 (7.5 bb, rounded up), 10 and 15 (uneven stacks).
- 27 hands are correctly not gradable: not heads-up, deeper than 20 bb, or a
  min-raise.
- The grader found a real mistake that the hand count did not mark: folding
  K2o in the BB at 8 bb loses 0.017 bb. HoldemResources' caller chart calls K2o
  up to 8.1 bb.

Beyond the gate:
- **Pluribus's result** from our replay is −7.09 bb/100 raw. Taken straight
  from the files' own stacks it is −7.0864 bb/100; the two agree to the 8 odd
  chips. The EV-adjusted figure is −1.72 bb/100. Pluribus's published win rate
  is variance-reduced (AIVAT), not raw.
- **Pluribus stats:** VPIP 26.9, PFR 18.0, 3-bet 7.3, WTSD 30.6, W$SD 48.8.
- **Pluribus all-ins:** 92, of which 91 were adjusted exactly and 1 (multiway
  preflop) by Monte Carlo.
- **Multiway equity:** a 3-way preflop Monte Carlo agrees with pokerkit's
  `calculate_equities` within 3 SE. Heads-up results equal `hand_vs_hand`, and
  side-pot shares match counted outs (`tests/test_multiway.py`).

```
showdown analyze tests/fixtures/hh
showdown analyze data/external/phh/repo/data/pluribus     # about 100 s
py gate.py --full
```

---

## Done 1 to 5 (SCOPE), checked 2026-11-14

| # | Definition | Evidence | Result |
|---|---|---|---|
| 1 | `py gate.py` exits zero: ruff, format, pytest with ≥ 80% coverage, a clean tree, HEAD pushed | It passes at every phase commit. `py gate.py --full` passed at e667ded with 97.8% coverage; see the final run recorded below | PASS |
| 2 | Gates A to F all PASS | the sections above | PASS |
| 3 | `showdown play` opens a local page, and a full push/fold trainer session and a full Leduc session can each be played in the browser | Played by hand in the browser pane: fixed and random depth, both seats, graded decisions, the board and result after a call, the summary, and Leduc in both seats (Gate E) | PASS |
| 4 | `showdown analyze <file>` prints the stats table for the phh-dataset Pluribus hands | 10,000 hands parsed; a table of 14 players with all-in EV and grading summaries; about 100 s (Gate F) | PASS |
| 5 | The README states what is borrowed and under which license, what is built, every gate result and the known limits | the README after the Phase 7 truth pass | PASS |

**Final full run (2026-11-14, commit e667ded).** `py gate.py --full` passed:
ruff, format, all tests including slow ones, coverage 97.8%, a clean tree, and
HEAD pushed. It took 16 min 56 s on an idle 16-core machine.

The previous full run, at commit 640b178, failed one Gate C case. It drew
beyond 3 SE from pokerkit's then-irreproducible sample. The cause was found
and fixed once (DECISIONS 28), without changing the bar.

---

## Phase 8 spikes (live advisor)

### Gate S2: TexasSolver flop speed: FAIL (2026-11-15)

Evidence: `spikes/2026-11-15-texassolver-speed.py`. The bar, the grid, the tree
and the stop-early rule were all fixed in DECISIONS 30 before the first solve.
TexasSolver v0.2.0 runs as a separate program with 16 threads.

| Check | Measured (10 solves on 2 flops; then stopped early) | Bar | Result |
|---|---|---|---|
| Median wall time per solve | 120 s (timeout) | ≤ 10 s | FAIL |
| 95th percentile | 120 s | ≤ 20 s | FAIL |
| Exploitability | 3BP 1.33–1.81% of pot; SRP 3.1–356% (never converged) | ≤ 2% of pot | FAIL |

- **Single-raised pots** (25, 50 and 100 bb): all six hit the 120 s timeout
  without converging.
- **3-bet pots** (50 and 100 bb): converged, but took 50 to 76 s.
- **Contention.** The second flop ran while a separate session's CFR spike
  shared the CPU: 11 iterations against 51 on the first. The first flop alone
  is 6 to 12 times over the bar, so contention cannot change the verdict.
- **Not retuned,** as DECISIONS 30 requires. Ian's fallback is in DECISIONS
  31.

```
.venv\Scripts\python -I spikes\2026-11-15-texassolver-speed.py
```

### Gate S4: postflop-solver flop speed: FAIL (2026-11-15)

Evidence: `spikes/2026-11-15-postflop-solver-speed.py`. The grid, the ranges,
the tree, the settings, the bars and the stop-early rule were fixed in
DECISIONS 38 (commit 02e5be1) before the first solve. The grid is S2's own,
loaded from S2's spike module.
- **The engine:** b-inary/postflop-solver at 9d1509f, through our JSON bridge,
  as a separate process.
- **The build:** Rust 1.100.0 (gnu), with two build fixes, recorded in the
  spike before any solve:
  - the optional `bincode` feature is off, because its pinned pre-release
    now resolves to an incompatible version;
  - `dangerous_implicit_autorefs` is allowed (Ian's choice).

| Check | Measured (10 solves on 2 flops; then stopped early) | Bar | Result |
|---|---|---|---|
| Median wall time per solve | 47.6 s | ≤ 10 s | FAIL |
| 95th percentile | 120 s (3 timeouts) | ≤ 20 s | FAIL |
| Exploitability | every finished solve 1.47–1.83% of pot; 3 timeouts unmeasured | ≤ 2% of pot | FAIL |

| Spot | postflop-solver (S4) | TexasSolver (S2), same flops |
|---|---|---|
| 3BP50 | 6.7, 10.3 s | 65.2, 49.6 s |
| 3BP100 | 12.6, 17.6 s | 67.1, 76.2 s |
| SRP25 | 27.7, 72.1 s | timeout, timeout |
| SRP50 | 67.6 s, timeout | timeout, timeout |
| SRP100 | timeout, timeout | timeout, timeout |

- **4 to 10 times faster than TexasSolver, but still not live speed for
  single-raised pots.** Those pots have wide ranges, deep stacks and 2.4 to
  3.8 GB trees.
- **Contention.** Other projects' jobs were running, using about one core of
  16. Single-raised pots are 60% of the grid and would need to run 3 to 6 times
  faster to pass, so contention cannot change the verdict.
- **Reported, not gated:**
  - **Node locking works.** On SRP50, Kc7d6c, the BB was locked to never fold to
    the SB's 33% flop bet. The SB's betting after a check rose from 53.1% to
    67.2%, while its betting with its weakest third of hands fell from 53.8%
    to 37.1%: more value bets, fewer bluffs.
  - **The model ranges** gave similar times. 3BP50 was skipped, because the
    model never 3-bets small at 50 bb.
- **Not retuned,** as DECISIONS 38 requires.

```
.venv\Scripts\python -I spikes\2026-11-15-postflop-solver-speed.py
```

---

## Gate G: the V1 advisor: PASS (2026-11-15)

Evidence: `tests/test_gate_g.py` (fast suite). The fixture is
`tests/fixtures/live/spots.toml`. The rules and bars were pre-registered in
DECISIONS 32 before any advisor code existed.

| Check | Measured | Bar | Result |
|---|---|---|---|
| Fixture spots get the expected suggestion | 43 of 43: 10 river and turn, 21 preflop, 2 with no suggestion, 10 flop | ≥ 40 spots | PASS |
| Preflop at 20 bb or less equals the push/fold solution's pure actions | 21 of 21 | all | PASS |
| River and turn equity equal the hand-counted outs | 10 of 10, exactly (e.g. 3/15, 7/44, 8/22) | exact | PASS |
| Flop Monte Carlo against exact enumeration | 10 of 10 within 3 SE, each spot far enough from its threshold that the action is stable | within 3 SE | PASS |
| 95th-percentile time per suggestion, separate process without coverage, idle laptop on AC | 65–70 ms over three runs (max 80 ms) | ≤ 300 ms | PASS |
| Every suggestion is logged | 43 of 43 lines in the JSONL log | all | PASS |

How it got here:
- **One fixture spot was replaced before the gate was recorded.** 96o at 5 bb
  is a hand the solution mixes (18% jam), so it has no pure answer. It became
  96o at 4 bb, where the solution is pure.
- **Latency was not measured validly until an idle run** (DECISIONS 32). An
  earlier in-suite measurement read 937 ms. Reproduced, that came from
  coverage tracing plus other heavy work on the laptop:
  - first, a parallel S3 CFR solve at 93% CPU;
  - then, another project's session.
  
  Under that load, even CPU time per suggestion rose to 344 ms. Those runs
  don't count, and the bar never moved. The idle runs on 2026-11-15 measured
  65 to 70 ms.

```
showdown advise --hero AhKh --seat sb --stack 50 --board Qh7h2c3s --pot 20 --to-call 10 --villain QsQd
.venv\Scripts\python -m pytest tests/test_gate_g.py -s
```

## Gate P: the preflop model above 20 bb: PASS (2026-11-15)

Evidence: `tests/test_gate_p.py` (fast suite, on the committed
`data/preflop_model.json`) and `tests/test_gate_p_slow.py` (`py gate.py
--full`). The solve, grid, lookup rule and bars were pre-registered in
DECISIONS 34 before the product solve ran.

The solve: `showdown preflop build --workers 12`, our CFR+ at 1,000
iterations on the exact matrix. It covers 9 depths (25, 30, 40, 50, 60, 70, 80,
90, 100 bb) at R_oop 0.85, 0.90 and 0.95, plus the two 20 bb check solves: 29
solves in 4,557 s.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. Exploitability at every depth, every R | worst 1.62e-4 bb/hand (80 bb, R 0.95); worst at the product R 0.90 is 1.05e-4 (100 bb) | ≤ 1e-3 | PASS |
| 2. The jam-only 20 bb game equals `data/pushfold.json` at 20 bb | 169 of 169 jam and call frequencies bit-identical; exploitability identical (2.82e-6) | exact | PASS |
| 3. The full game at 20 bb, R 0.90, is worth at least push/fold to the SB | −0.0781 bb/hand against a bound of −0.1832 | ≥ push/fold value − both exploitabilities | PASS |
| 4. Every terminal equals a closed form written from DECISIONS 34 alone | 314,171 terminals (169 × 169 × 11) at each of 25 and 100 bb × 3 values of R | to 1e-12 | PASS |
| Stored exploitability equals a fresh best response on the stored strategy | 25 and 100 bb at R 0.90 | to 1e-12 | PASS |

SB value at R 0.90 rises from −0.059 bb/hand at 25 bb to +0.123 at 100 bb.
Across R it moves far more than solver error: at 100 bb it is +0.229 at R
0.85 and +0.002 at R 0.95.

The "depends on R" flag (DECISIONS 34) marks a (class, node) pair when its most
likely action differs between the R 0.85 and 0.95 solves:
- 102 to 139 of 1,014 pairs per depth;
- 11 to 31 of the 169 SB first-in classes, rising with depth.

What the gate does not show:
- Gate P shows the model is solved correctly. It does not show the model is
  realistic. Its postflop line is an assumption (R), so its charts are labelled
  "model chart" (DECISIONS 33).
- S3's limits still hold (`docs/preflop-source.md`):
  - with one 3-bet size, the BB never 3-bets to 7.5 at 25 and 50 bb at R 0.90;
    it calls or jams instead. At 50 bb it jams over the open with 31% of
    classes;
  - money behind never goes in after a called raise or 3-bet.

```
showdown preflop build --workers 12
showdown preflop chart 50
.venv\Scripts\python -m pytest tests/test_gate_p.py
.venv\Scripts\python -m pytest tests/test_gate_p_slow.py -m slow
```

## Gate G, extended: the preflop model in the advisor: PASS (2026-11-15)

Evidence:
- `tests/test_gate_g_model.py`, on the fixture `tests/fixtures/live/model_spots.toml`;
- `tests/test_gate_g.py`, for the old spots and the latency.

The rules and bars were pre-registered in DECISIONS 35 (commit 3142fc9) before
any wiring code.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. New preflop spots above 20 bb | 34 answered spots (4 to 7 for each of the six decisions) plus 7 no-suggestion spots. Every action, depth and R flag matches the hand-written chart reading. Every mix equals the stored JSON to 1e-12 | ≥ 30 spots, ≥ 4 per decision, ≥ 4 no-suggestion | PASS |
| 2. Raise sizes the model doesn't use | 3 spots: a 3 bb open (3-bet suggested to 9 bb), a 4 bb open, and a 3-bet to 10 bb, each with its note | ≥ 2 | PASS |
| 3a. Model range weights | 3 classes × 4 ranges at 100 bb equal the stored frequencies multiplied by hand | to 1e-12 | PASS |
| 3b. Turn and river equity vs a model range | 4 spots equal a weighted phevaluator brute force, including 15 bb using the 25 bb model | to 1e-12 | PASS |
| 3c. Flop Monte Carlo vs exact weighted enumeration | 2 spots | within 3 SE | PASS |
| 3d. 3-bet pot at 50 bb | uses the fixed top-15% default, labelled | — | PASS |
| 4. Old fixture | 42 of 43 old spots unchanged with `--ranges fixed`. AsKd first in at 40 bb moved to the new fixture by design and gets the model's raise | 42 unchanged | PASS |
| 5. 95th-percentile time, old and new spots, separate process, no coverage, idle laptop | 68 ms over 90 suggestions (max 70 ms) | ≤ 300 ms | PASS |
| 6. Log | every suggestion logged; all 34 chart suggestions carry their mix and notes | all | PASS |

How it got here:
- One fixture typo was fixed before the gate counted: a turn spot's hero,
  AcTc, shared the Tc with its board. It became AdTd.
- No bar or expected answer was changed.

What the gate does not show: as with Gate P, that the model's answers are
good poker. They come from a model chart, R 0.90, with S3's limits.

```
showdown advise --hero Kh9h --seat bb --stack 100 --facing bb_vs_raise --pot 4 --to-call 2
showdown advise --hero AsKd --seat sb --stack 50 --board Ts9s2d --pot 5 --ranges fixed
.venv\Scripts\python -m pytest tests/test_gate_g.py tests/test_gate_g_model.py -s
```

## Gate J: the jam-vs-range helper: PASS (2026-11-15)

Evidence: `tests/test_gate_j.py` (fast suite), `tests/test_gate_j_slow.py`
(`py gate.py --full`), and the latency test in `tests/test_gate_g.py`. The
fixture is `tests/fixtures/live/jam_spots.toml`. The rules and bars were
pre-registered in DECISIONS 36 (commit d0547e8) before any helper code.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. Best response to the solution's own jam range reproduces its pure calls and folds | push/fold 1–20 bb: 3,363 pure classes agree, 1 indifferent. The model: `j` at 25 and 30 bb (161, 153), `rj` at all nine depths (127 to 167 each), `rrj` at 70–100 bb (25, 28, 30, 41). No class disagrees | every pure class, except within 0.001 bb | PASS |
| 2. Matrix equity vs exact board enumeration | 6 spots, including a hero that blocks both villain classes (AKo vs AA,AKs) | to 1e-9 | PASS |
| 3. Hand-worked spots | 10 fully hand-worked (2 close calls, 1 close fold, the exploit view beside Nash and the model, `--villain-top`), 3 default-range spots, 1 no-suggestion spot, 5 errors | ≥ 10 | PASS |
| 4. 95th-percentile time over every Gate G and Gate J spot, separate process, no coverage, idle laptop | 67 ms over 102 suggestions (max 75 ms) | ≤ 300 ms | PASS |

How it got here:
- **The test's own non-vacuity floor was wrong, and was not a bar.** Bar 1's
  model test first asserted more than 100 pure classes per case. At `rrj` the
  model mixes most classes, so only 25 to 41 are pure, though none disagree.
  The floor became 20.
- **One edit to my latency script did not apply** the first time, so the
  first run lacked Gate J's spots. It was fixed and rerun.
- **No pre-registered bar or expected answer was changed.**
- **The core `answer()` accepts a to-call of 0.** That case is the 1 bb
  push/fold jam, which bar 1 covers. The advisor still rejects a live jam spot
  with no to-call.

Changes to Gate G's fixture, by design (DECISIONS 36): KhKd facing a first-in
jam at 50 bb, and AhAd facing a 4-bet jam at 60 bb, moved from "no
suggestion" to Gate J's default spots.

```
showdown advise --hero Kc8d --seat bb --stack 10 --facing bb_vs_jam --pot 11 --to-call 9 --villain TT
showdown advise --hero KhKd --seat bb --stack 50 --facing bb_vs_jam --pot 51 --to-call 49 --villain-top 20
.venv\Scripts\python -m pytest tests/test_gate_j.py -s
.venv\Scripts\python -m pytest tests/test_gate_j_slow.py -m slow
```

## Push/fold exploit charts (DECISIONS 37): PASS (2026-11-15)

Evidence: `tests/test_pushfold_exploit.py` (fast suite). The bars were
pre-registered in DECISIONS 37 (commit 02e5be1) before any code.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. EVs equal the compiled tree's own `best_response` and `policy_value` | 5 and 15 bb, both seats, reads of 15% and 60%: equal to the 12th decimal (e.g. 15 bb vs SB jams top 60%: 0.176805107161 both ways) | to 1e-9 | PASS |
| 2. The measured numbers | 10 bb vs BB calls top 15%: best response +0.427, Nash +0.133 over the game value. 20 bb vs SB jams any two: gain +0.747 bb/hand (+37.3 bb/100) | to 1e-3 | PASS |
| 3. Risk never beats the game value | worst over 1–20 bb, both seats, reads 15/50/100% | ≤ 1e-5 | PASS |
| 4. The chart is the per-class argmax, and equals the tree's pure best response away from ties | every case in bar 1 | exact | PASS |

```
showdown pushfold exploit 10 --villain-calls 15
showdown pushfold exploit 20 --villain-jams 100
```

## Gate X: exploit solves between sessions: FAIL, X3 only (2026-11-15)

Evidence: `tests/test_gate_x.py` (`py gate.py --full`). The bars, the reads
and the seed were pre-registered in DECISIONS 40 (commit 3511218) before any
bridge code.
- **The engine:** postflop-solver at 9d1509f, through the AGPL bridge in
  `bridges/postflop/` (binary SHA-256 c45af752…).
- **The spot:** SRP50, the hero as the SB, the model's ranges at 50 bb,
  tree T1.
- **The flops:** 10, seed 20261116.
- **Solves:** 30: one baseline per flop, shared by both reads, and one
  locked solve per read.
- **Cached** under `data/external/postflop-solver/cache/gate-x`, so a rerun
  with the same binary replays them.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. The lock holds | all 20 locked solves: the reported strategy at the locked node equals the lock for every hand | to 1e-6 | PASS |
| 2. Convergence | all 30 solves 1.30–1.95% of the pot, in 50–110 iterations; median 115 s, max 508 s (QcJdTh baseline) | ≤ 2% within 10 min | PASS |
| 3. Against `never-folds`, the weakest third bets less | falls on 3 flops (Tc6c2c 87→85%, KcQc2c 85.5→85.4%, Qc6c2c 90→84%); rises on 7 | ≥ 8 of 10 | **FAIL** |
| 4. Against `over-folds`, the weakest third bets more | rises on 10 flops (e.g. Tc5d3c 76→99%, Jc7d7c 80→100%) | ≥ 8 of 10 | PASS |
| 5. The command prints both strategies and both EVs | CLI test at 25 bb, `never-bets` | — | PASS |

Against `never-folds`, the SB's first flop decision after a check:

| Flop | Bets overall | Weakest third | Middle | Strongest | SB EV, bb |
|---|---|---|---|---|---|
| Tc5d3c | 77 → 90% | 76 → 80% | 71 → 95% | 84 → 95% | 3.07 → 3.23 |
| Tc6c2c | 87 → 93% | 87 → 85% | 81 → 98% | 92 → 97% | 3.27 → 3.50 |
| KcQc2c | 83 → 94% | 85.5 → 85.4% | 74 → 99% | 91 → 97% | 3.38 → 3.72 |
| Qc6c2c | 89 → 93% | 90 → 84% | 84 → 98% | 94 → 97% | 3.30 → 3.56 |
| AhAdAc | 100 → 100% | 100 → 100% | 100 → 100% | 100 → 100% | 4.03 → 4.20 |
| Jc8d8c | 78 → 100% | 84 → 100% | 70 → 100% | 81 → 100% | 3.34 → 3.73 |
| QcJdTh | 98 → 99% | 97 → 99% | 96 → 99% | 99 → 100% | 3.85 → 4.17 |
| KcQd3d | 88 → 98% | 90 → 96% | 82 → 99% | 90 → 99% | 3.40 → 3.76 |
| Jc7d7c | 71 → 100% | 80 → 100% | 59 → 100% | 74 → 100% | 3.22 → 3.56 |
| Kc9c2d | 90 → 98% | 91 → 96% | 88 → 99% | 92 → 99% | 3.37 → 3.69 |

Reading:
- **Not a bridge bug.** S4 ran the same lock on SRP50 Kc7d6c through its own
  bridge, with S2's top-% ranges: the weakest third's betting fell from 53.8%
  to 37.1%. This bridge, with those ranges, gives 53.3% to 34.2%, and overall
  betting rises from 51.3% to 65.6% (S4: 53.1% to 67.2%). It is kept in the
  file as `test_the_bridge_reproduces_s4s_node_lock`, which is evidence, not a
  bar.
- **The ranges make the difference.** With the model's ranges the solved SB
  already bets its 33% size with 71–100% of its range after a check, and with
  76–100% of its weakest third. There is little bluffing left to cut.
- **Probably the lock's other half.** The lock is DECISIONS 40's: the BB
  "calls with every hand, never folds or raises". So it also takes away the
  BB's check-raise, and the BB reaches the turn with every weak hand, while
  turn and river play stays solved. A small bet then gains for every third.
  Which part drives it is not measured.
- **What it means for play.** The command's answers are solver answers for
  these ranges and this tree. "Bluff less against a station" is not what they
  say for the SB's flop bet at 50 bb. The 25 bb check before the gate pointed
  the same way: Kc7d6c, weakest third 82% to 91%.
- **No bar was moved.** X3 is a strict expected failure in the test file, so
  a pass would show up.
- **The `never-folds` text** in the command's output now says "never raises"
  too, matching DECISIONS 40's wording.

```
showdown postflop exploit --stack 50 --flop Tc5d3c --hero sb --read never-folds
.venv\Scripts\python -m pytest tests/test_gate_x.py -m slow -s -rxX
```

## Gate R: replaying a saved hand with legal advice: PASS (2026-11-16)

Evidence:
- `tests/test_gate_r.py` (fast suite);
- `tests/test_gate_r_slow.py` (`py gate.py --full`);
- the saved hands in `tests/fixtures/live/hands/`.

The bars were pre-registered in DECISIONS 41 (commit b561d9b) before any
code. `showdown replay` reads the hand state from a PHH hand through pokerkit.
That state is the pot, the amount to call, both stacks, the legal actions and
the history. The preflop decision and the pot type are read from the action.
`Advisor.suggest` then keeps its advice to legal actions and sizes. The
decision rules are unchanged.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. A full saved hand | `hu_full_hand.phh`, SB at 50 bb: raise 2.5 (model), bet 1.65 (flop), call (turn), call (river); preflop read as `sb_first`, then `bb_vs_raise`; pot type `srp` | advice at a hero decision on every street | PASS |
| 2. Reconciliation | after every player action, in the 3 saved hands and the 500 simulated ones: pot and both stacks equal an independent count from the PHH text, and pot plus stacks equals the starting chips | to 1e-9 bb | PASS |
| 3. Legality | 500 seeded hands (seed 20261116), stacks of 10–100 bb each: 3,099 decisions. Counts: 2,654 suggestions, all legal (941 check, 510 call, 388 bet, 351 fold, 286 raise, 105 all-in, 73 jam) and 445 "no suggestion"; every size within pokerkit's limits and the opponent's bet plus stack; 44 s | all legal | PASS |
| 4. Regression | `hu_short_stack_river.phh`, river with a 45 bb pot and 2.5 bb behind: **ALL-IN 2.5 bb**, with the note "bet 33.75 bb is more than can be matched: all-in" | all-in 2.5 or check | PASS |
| 5. Nothing else moves | every Gate G, J and P test passes with its fixture unchanged; `showdown advise`, which has no hand state, prints exactly what it did | unchanged | PASS |

**River trace** (reported, not gated). `showdown replay --trace` was run on
two hands that are identical to the river. On the river the BB either bets
5.5 into 16.4, or shoves 41.8 all-in.

| | Third of the pot | Shove |
|---|---|---|
| History given to the advisor | 8 moves, ending "river BB bets 5.5" | 8 moves, ending "river BB bets 41.8 (all-in)" |
| To call, and the pot | 5.5 into 21.9 | 41.8 into 58.2 |
| Range into the equity calculation | 1,326 combos, weight 923.6458, fingerprint c70a1aad9e1e | **the same:** 1,326 combos, 923.6458, c70a1aad9e1e |
| Equity | 92.2% | 92.2% |
| Threshold, and the advice | 25.1%: CALL | 46.8%: CALL, "calling puts you all-in" |

- **The same range, explicitly.** The advisor now receives each line's
  history, but `advisor.villain` (`live/advisor.py:177-193`) does not read it.
  So both lines reach `range_vs_range` with the BB's whole preflop calling
  range. Only the price changes.
- **Where range narrowing goes** (step 3 of the plan). `villain` would weight
  each combo by how often the opponent's strategy takes this line. On the
  flop that weight comes from the flop library's per-hand frequencies; on the
  turn and river, from S2b's solves. Range narrowing has its own entry and
  gate.

How it got here:
- **The first draft of `hu_river_shove.phh` had the shove wrong.** It gave
  36.3 bb, but the BB had 41.8 bb left. The analyzer's own replay rejected
  it, because the finishing stacks did not reconcile. It was fixed before any
  test.
- **pokerkit warns** when the simulation deals its own seeded cards instead
  of pokerkit's deck. That is deliberate (`docs/design-review-phases-5-6.md`),
  so the test silences it.
- **No bar was moved.**

```
showdown replay tests/fixtures/live/hands/hu_full_hand.phh --hero sb
showdown replay tests/fixtures/live/hands/hu_short_stack_river.phh --hero sb
showdown replay tests/fixtures/live/hands/hu_river_shove.phh --hero sb --trace
.venv\Scripts\python -m pytest tests/test_gate_r.py tests/test_gate_r_slow.py -m "slow or not slow" -s
```

## Gate T: the live tracker and overlay, from table frames: PASS on the second run (2026-11-17)

Evidence:
- `tests/test_gate_t.py` (fast suite);
- `tests/test_gate_t_slow.py` (`py gate.py --full`);
- the simulator in `tests/live_sim.py`.

The bars and the frame contract were pre-registered in DECISIONS 42 (commit
9e5e497) before the evidence runs. No screen is read yet: the frames come
from replayed hands, as the reader's output would.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. Hero-turn frames | 200 simulated hands (seed 20261117, Ian alternately SB and BB), only Ian's turns and the end seen: all 595 of Ian's decisions equal step 1's replay field for field (street, board, history, pot, to call, stacks, bets, legal actions, preflop line); 20 hands had no turn for Ian (the SB folded) | every one equal | PASS |
| 2. Every-change frames | 200 of 200 hands written; betting actions and board equal the hand's own; every PHH reconciles; no unseen sizes | equal, reconciles | PASS |
| 3. Minimal frames | 180 hands written, all reconcile. 31 had a last bet whose size can't be seen: folded to, or called all-in for less. Those are written at the smallest legal size and marked | all reconcile; unseen counted | PASS |
| 4. 3-handed | 20 frames from five 3-handed hands: 5 "no suggestion: 3 players dealt in", no PHH | no advice, nothing written | PASS |
| 5. Latency | 164 suggestions over 60 hands, every-change frames, the full 20,000-sample flop equity, separate process, no coverage, idle machine: **95th percentile 106 ms**, max 135 ms | ≤ 300 ms | PASS |
| 6. The overlay | the tkinter window opens on top (`-topmost`), shows "ALL-IN 2.5 bb" with its note and state line, then "no suggestion: 3 players dealt in", and closes | shown and read back | PASS |

**How it got here.** The gate rule (`docs/plan-phases-4-7.md`) is:
reproduce, fix once if it is a clear code bug, record it in DECISIONS, re-run,
and stop if it still fails. Here one round of six fixes came between two
evidence runs, and they are recorded in DECISIONS 42's amendment.
- **The first evidence run failed twice:**
  - **bar 2:** whole chip counts were written as `68.0`;
  - **bar 5:** 306 ms, but measured while a full-suite run was going, which
    DECISIONS 32's idle rule does not allow.
- **A 200-hand sweep then showed the tracker failing on real table states.**
  Each failure was reproduced on a named hand before it was fixed:
  1. Whole chip counts kept whole.
  2. Bets are swept into the pot only when the frame shows it, since the
     table can show a closed street's bets for a moment (hand 5, an all-in
     call).
  3. The search's prune "stacks only fall" was wrong once an uncalled bet
     comes back. It became "stack plus bet only falls".
  4. The prune "bets only rise" was wrong across a sweep into the pot. It now
     applies only while a street is open.
  5. After an all-in, the hands are shown before the run-out is dealt:
     - the opponent's cards are shown when the frame shows them;
     - Ian's, which are always on his screen, at the run-out or the result.
  6. A raise called all-in for less than a legal raise (hand 144) is written
     at the smallest legal size and marked unseen. The returned excess makes
     its real size unknowable.

  The sweep then had no errors in either frame mode, and the second evidence
  run is the one recorded above.
- **No bar was moved.**
- **Bar 2's wording was tightened before any run.** It compares betting
  actions and board cards, not show and muck lines, because whether Ian shows
  a losing hand never changes the result.

What it means for live play:
- **Reading every change works.** The reader should send a frame on every
  change it sees. With only Ian's turns, 31 of 180 last bets lose their size.
  The advice is unaffected, but the hand log, which the opponent model
  (step 5) will read, loses those sizes.

```
showdown live --replay tests/fixtures/live/hands/hu_full_hand.phh --hero sb
showdown live --replay tests/fixtures/live/hands/hu_short_stack_river.phh --hero sb --no-window
.venv\Scripts\python -m pytest tests/test_gate_t.py tests/test_gate_t_slow.py -m "slow or not slow" -s
```

## Gate S2b: live turn and river solves: FAIL, on the turn's tail rule only (2026-11-17)

Evidence: `spikes/2026-11-17-turn-river-speed.py`. The grid, the narrowing,
the tree, the settings and the bars were fixed in DECISIONS 44 (commit
703908c) before any bridge code.
- **The engine:** postflop-solver at 9d1509f. The new turn and river binary,
  `bridges/postflop/src/bin/streets.rs` (SHA-256 ef5ab1cf…), takes raw
  1,326-combo ranges. The flop bridge is unchanged (c45af752…), so Gate X's
  cache still holds.
- **The grid:** 3BP100 and SRP50, 10 boards each, seed 20261117. Each board
  has one turn start and one river start: 40 timed solves.
- **The ranges:** the model's ranges, narrowed by the flop line, using the
  four stored flop nodes. The library is empty, so the spike solved its 20
  flops with the library's spec, untimed: 53–254 s each, 1.38–2.00% of the
  pot. The river starts assume a checked turn, the slow case.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. River, median | 0.03 s (20 solves; all 0.02–0.06 s) | ≤ 3 s | PASS |
| 1. River, 95th percentile | 0.05 s | ≤ 6 s and ≤ 2 × median (0.07 s) | PASS |
| 2. Turn, median | 0.30 s (20 solves; all 0.18–1.12 s) | ≤ 15 s | PASS |
| 2. Turn, 95th percentile | 0.90 s | ≤ 30 s: PASS; ≤ 2 × median (0.60 s): **FAIL** | **FAIL** |
| 3. Accuracy | every solve 0.55–1.94% of its pot, in 30–60 iterations; no timeouts | ≤ 2% | PASS |

| Spot | Street | Flop line | Solves | Median s | Max s | Narrowed combos, OOP / IP |
|---|---|---|---|---|---|---|
| 3BP100 | turn | check-check | 2 | 0.68 | 1.12 | 150–185 / 772–985 |
| 3BP100 | turn | bet-call | 6 | 0.28 | 0.64 | 151–186 / 436–792 |
| 3BP100 | turn | check-bet-call | 2 | 0.24 | 0.28 | 131–172 / 838–925 |
| SRP50 | turn | check-check | 4 | 0.71 | 0.89 | 854–868 / 647–796 |
| SRP50 | turn | bet-call | 2 | 0.37 | 0.42 | 638–646 / 818–884 |
| SRP50 | turn | check-bet-call | 4 | 0.25 | 0.30 | 514–658 / 837–894 |
| both | river | all three | 20 | 0.03 | 0.06 | — |

Reading:
- **Live turn and river solves are fast.** The slowest turn took 1.12 s,
  against a 15 s median bar. The slowest river took 0.06 s, against 3 s.
  Turn trees need at most 0.05 GB of memory, and river trees under 1 MB.
- **Why bar 2 fails.** DECISIONS 44 required the 95th percentile to be
  within both 30 s and double the measured median. The second holds only if
  the times are narrowly spread, and the turn times split by line:
  - checked-through flops keep wider ranges and a smaller pot, so a deeper
    stack. SRP50's took 0.65–0.89 s;
  - bet-call and check-bet-call turns took 0.18–0.64 s.

  The first solve, 1.12 s, also carries 0.58 s of cold process start; the
  solver itself took 0.54 s. The next two slowest turns, 0.89 and 0.72 s, are
  above 0.60 s too, so the cold start alone does not decide the verdict.
- **Not a code bug.** The narrowing looks right:
  - the SRP50 BB checks almost all of its range on the flop;
  - the 3-bettor at 3BP100 checks little: 6.8 of its 133.5 combos of weight on
    Jc7d6d.

  So no fix was due, and none was made.
- **Five boards took the next line,** because the planned line left under 5
  combos:
  - at 3BP100, the 3-bettor almost never checks on KcJd3h, Kc7c6d and
    AcJd7h;
  - at SRP50, the BB almost never leads into the raiser on Qc8c2d.

  3BP100 therefore ran 6 bet-call boards, 2 check-check and 2 check-bet-call.
- **Contention.** During the timed run another session's drive-wide `find`
  used one core of 16. No solver or test was running.
- **What this does not cover.** Every turn and river start needs the flop's
  frequencies to narrow from. Solving the flop live takes 1–4 minutes (these
  20 flops, and Gate S4). So live narrowing waits on the flop library, which
  is still empty, and on a rule for opponent bet sizes that are off the tree.
- **No bar was moved.** DECISIONS 44 rules out changing them after the first
  timed solve.

```
.venv\Scripts\python -I spikes\2026-11-17-turn-river-speed.py --flops-only
.venv\Scripts\python -I spikes\2026-11-17-turn-river-speed.py
```

## Gate S2c: live turn and river solves, on new boards with absolute tail bars: PASS (2026-11-18)

Evidence: `spikes/2026-11-17-turn-river-speed.py --s2c`. Ian chose this re-gate
after S2b, and its bars were pre-registered in DECISIONS 45 (commit 3ac12af)
before its first solve. Everything else is S2b's: the same binaries, spots,
narrowing, tree, settings and timing. The seed is new (20261118), so the 20
boards are new. Their flops were solved first, untimed: 27–213 s each,
1.19–1.97% of the pot.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. River, median | 0.03 s (20 solves) | ≤ 3 s | PASS |
| 1. River, 95th percentile | 0.09 s; max 0.69 s | ≤ 6 s | PASS |
| 2. Turn, median | 0.38 s (20 solves) | ≤ 15 s | PASS |
| 2. Turn, 95th percentile | 1.17 s; max 1.18 s | ≤ 30 s | PASS |
| 3. Accuracy | every solve 0.80–1.98% of its pot, in 30–60 iterations; no timeouts | ≤ 2% | PASS |

| Spot | Street | Flop line | Solves | Median s | Max s |
|---|---|---|---|---|---|
| 3BP100 | turn | check-check | 2 | 0.70 | 0.92 |
| 3BP100 | turn | bet-call | 8 | 0.29 | 0.38 |
| SRP50 | turn | check-check | 4 | 1.14 | 1.18 |
| SRP50 | turn | bet-call | 3 | 0.41 | 0.55 |
| SRP50 | turn | check-bet-call | 3 | 0.36 | 0.40 |
| both | river | all | 20 | 0.03 | 0.69 |

Reading:
- **The same picture as S2b, on new boards.** Live turn solves take about a
  second at worst, and river solves a few hundredths of a second.
- **Under S2b's ratio rule** it would have failed on both streets (river
  0.09 s against 0.07 s, turn 1.17 s against 0.75 s). That rule is reported
  here, not gated (DECISIONS 45), and S2b stays a FAIL.
- **One river solve took 0.69 s** (SRP50, Jc9d6d6c3h, 40 iterations, under
  1 MB). The other 19 took 0.03–0.06 s. Nothing in the spot explains it, so
  it is probably the laptop. It is still far inside the bars.
- **Five of the ten 3BP100 boards took the next line,** because the 3-bettor
  almost never checks there: KcQd7h, KcTd4h, AcKcTd, KcJd5h and Tc4d3h. As
  a result 3BP100 ran 8 bet-call boards and 2 check-check.
- **Contention:** as in S2b, another session's `find` used under one core.
- **What it still doesn't cover** is what S2b said: live narrowing needs the
  flop's frequencies, and the flop library is empty.

```
.venv\Scripts\python -I spikes\2026-11-17-turn-river-speed.py --s2c --flops-only
.venv\Scripts\python -I spikes\2026-11-17-turn-river-speed.py --s2c
```

## Gate N: the stopgap range model: PASS after one loader fix (2026-11-18)

Evidence:
- `tests/test_gate_n.py` (bar 2) and `tests/test_gate_r.py` (bar 1), both in
  the fast suite;
- `tests/test_rangefit.py`;
- the curves in `data/range_model.json`.

The model, the fit set and both bars were pre-registered in DECISIONS 46
(commit 1591f66) before any code. Ian chose every piece: narrowing by the
villain's moves, equity against a random hand, soft floors, and curves fitted
to the solver.

**The fit.** `showdown postflop fit-ranges` ran once, after Gate S2c's timed
run, in about two minutes.
- **The solves:** S2b's and S2c's 40 flop entries, plus 344 turn and river
  solves, all within 2% of the pot. 34 flop lines were skipped for leaving
  under 5 combos: mostly 3BP100 lines in which the 3-bettor checks, and SRP50
  lines in which the BB leads.
- **The turns and rivers** were drawn by a shuffle seeded with
  "20261119|flop|line", one per (flop, line).
- **The result:** 32 keys (pot type × street × position × node), each with
  per-band frequencies and mean sizes.
- **The curves look like poker:**
  - river bets are polar. At SRP50 the OOP's 75% bet runs 0.43, 0.13, 0.05
    … 0.34, 0.58, 0.39 from the weakest band to the strongest;
  - calls sit in the middle and top bands;
  - folds sit at the bottom;
  - raises and all-ins sit in the top band.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. Gate R's trace differs | third-pot river bet: weight 208.66, fingerprint 34963a1eef09, equity 74.0%, CALL. Shove: weight 199.61, fingerprint 00cd1995844b, equity 70.9%, CALL. Before: both c70a1aad9e1e at 92.2% | different ranges | PASS |
| 2. Hand-worked weights | 7 spots on AsKsQd7c2h with five villain combos, one per odd band, and a curve table in the test: a bet at an anchor size, between the anchors and past them; a call interpolated by the size faced; a check at the 0.25 floor; a check then a raise re-ranked within the narrowed range; moves with no curve | to 1e-9 | PASS |

**How it got here.** Bar 1 failed on its first run: every villain move found
"no curve".
- **The cause:** the fit writes each key's curves under `"actions"`, and the
  loader read them one level up. That is a clear code bug, reproduced by
  bar 1 itself.
- **The fix,** made once: the loader reads `"actions"`. A round-trip test (the
  model reads what the fit writes) is now in `test_rangefit.py`.
- **Nothing else changed:** no rule, floor, band, curve or seed.

**Reported, not gated:**
- **Advice changes.** Over the 3 saved hands and Gate T's 200 simulated
  hands, 647 postflop decisions (either player's) were narrowed. The advice
  changed at 40 of them:

  | Street | Changes |
  |---|---|
  | flop | call → fold 5 |
  | turn | call → fold 9; all-in → check 4; bet → check 4; check → bet 3 |
  | river | call → fold 5; all-in → check 4; bet → check 3; check → bet 2; check → all-in 1 |

  The hero's equity moved by −3.8% on average, from −53.3% to +24.1%. The
  saved hands' own advice is unchanged: `hu_full_hand.phh` still bets the
  flop, calls the turn and calls the river.
- **The shove barely differs from the third-pot bet** (70.9% against 74.0%).
  The solver's all-in range is polar too, and with more bluffs at bigger
  sizes.
- **Latency,** by Gate T bar 5's method (a separate process, no coverage,
  every-change frames, 60 hands): 164 suggestions, 95th percentile 170 ms
  (106 ms before), median 48 ms, max 264 ms. The flop costs most, about 90 ms
  for the 45-runout strength, cached once per board.
- **The slow suites still pass.** Gate R bar 3's 500 simulated hands: all
  3,099 decisions legal (calls 510 → 448, folds 351 → 413). Gate T's own latency
  test: 95th percentile 191 ms.

What it means for play:
- **The advice now reacts to the line,** but only through equity. Postflop
  actions still come from the 60% rule and pot odds, so the stopgap never
  raises or bluffs. Step 3c would change that.
- **The curves come from the solver,** with the model's ranges, at 50 and
  100 bb. A friend's real bets need not follow them, and the label says
  "assumed, not solved".

```
showdown postflop fit-ranges
showdown replay tests/fixtures/live/hands/hu_river_shove.phh --hero sb --trace
.venv\Scripts\python -m pytest tests/test_gate_n.py tests/test_gate_r.py tests/test_rangefit.py -s
```

## Gate V: live turn and river solves in the advice: PASS (2026-11-18)

Evidence:
- `tests/test_gate_v.py` (bar 1 and the rules behind it, fast suite);
- `tests/test_gate_v_slow.py` (bars 2 to 4, `py gate.py --full`).

The pieces, the four bars and the changes to older tests were pre-registered in
DECISIONS 47 (commit 6c5123e) before any code. Ian picked them on 2026-11-18.
- **The code:** `live/solve.py`. At a turn or river decision in a replayed or
  tracked hand, the streets binary solves the street from the hand's real pot
  and stacks. The tracker starts the solve on the frame that shows the card.
- **The ranges:** the model's at the nearest depth. The stopgap's curves narrow
  the flop; the turn solve's per-hand frequencies narrow the turn. The villain's
  range at the node is narrowed by the solve's own frequencies for its moves.
- **The advice:** Ian's action is his hand's most likely action at the node,
  with the mix. Off-tree sizes map to the nearest T1 size, with a note.
- **The binaries are unchanged:** streets ef5ab1cf…, flop c45af752….

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. Gate R's two river hands | Third-pot bet: solved. The BB's range is 929 combos, weight 0.38, fingerprint 5690c46d7f83; CALL (call 55%, all-in 45%), equity 73.6%. Shove: solved. 658 combos, weight 0.98, fingerprint 7fbe701f944f; CALL (100%), equity 45.2%. `--trace` prints both | different ranges, both shown | PASS |
| 2. Legal over 500 hands | 216 solved suggestions (128 turn, 88 river), all legal: check 72, all-in 69, call 29, fold 25, bet 21 | all legal, at least 100 | PASS |
| 3. The bridge's own strategy | the first 40 solved answers (hands 14 to 51): every mix equals a second bridge run's row to 1e-6; every action is that row's most likely; the legality rule changed none | to 1e-6 | PASS |
| 4. Latency from the card | turn: 70 decisions, median 0.27 s, 95th percentile 1.18 s, max 1.74 s. River: 51, median 0.05 s, 95th percentile 0.15 s, max 0.18 s | turn ≤ 3 s, river ≤ 1 s, at least 30 each | PASS |

**Reported, not gated:**
- **Most random hands are not solved.** Over bar 2's 500 hands, 216 of 1,211
  turn and river decisions were solved. The fallbacks:
  - 956: the preflop line is not an open and a call, or a 3-bet and a call
    (the simulator limps, min-raises and 4-bets at random);
  - 16: the model almost never reaches the pot;
  - 15: the line left the solved tree (8 turn, 7 river);
  - 8: a range weighs under 1 combo at the river.

  In bar 4, 14 of the 121 timed decisions were fallbacks after a solve
  started. They count at their full time.
- **Off-tree sizes:** 55 of the 216 solved answers carry a mapping note. The
  legality rule changed one action.
- **Solve times** in bar 2's replays: turn median 0.11 s, max 2.20 s; river
  median 0.04 s, max 0.12 s.
- **No raise among the 216 solved actions.** The random stacks of 10 to 100 bb
  leave little behind, so T1's all-in threshold turns most raises into all-ins.
- **How the advice changed from the stopgap.** These are Ian's turn and river
  decisions in Gate T's 200 hands and the 3 saved hands: 226 decisions, 57
  solved, 17 changed.

  | Street | Changes |
  |---|---|
  | turn | check → all-in 4; bet → check 2; call → raise 2; all-in → check 1; bet → all-in 1; call → fold 1; fold → call 1 |
  | river | check → all-in 4; bet → check 1 |

  The saved hands:
  - `hu_full_hand.phh` now raises the turn to 13.81 bb (call 36%, raise 64%),
    where the 60% rule called;
  - its river call is unchanged;
  - `hu_short_stack_river.phh` still goes all-in for 2.5 bb.
- **The older gates still pass:**
  - Gate R bar 3: all 3,099 decisions legal;
  - Gate T bars 1 to 3;
  - Gate T bar 5, equity-helper answers only: 151 suggestions, 95th
    percentile 259 ms (170 ms in Gate N), max 349 ms, bar 300 ms.

**A finding for Ian: solver narrowing has no floor.** In `hu_full_hand.phh` the
solved BB checks the turn 98.9% of the time after check-calling the flop.
- Its real turn lead leaves 1.9 combos of weight, and 0.38 by the river.
- The advice still comes out, but it plays against the few hands the solver
  would lead with.
- The stopgap keeps a floor of 0.10 because friends mix and misplay. DECISIONS
  47 has none for solved streets. Adding one needs an amendment.

**How it got here.** The evidence run is the first and only one; no code was
changed after it.
- During the build, two test expectations were wrong and were fixed before
  that run:
  - a slice one move short;
  - a raise facing a node with an all-in, which maps to the all-in by
    DECISIONS 47's rule.
- The trace keeps its label "range into the equity calculation". The advice
  shows equity against that range.
- No bar was moved.

What it means for play:
- **On the turn and river of an open-call or 3-bet-call pot, the advice now
  comes from a solve.** That includes raises, all-ins and bluffs, and it
  arrives about a second after the turn card and a tenth of a second after the
  river.
- **The flop is still the equity helper** against the stopgap's range, until
  the flop library (Gate L).
- **Off-strategy lines from friends narrow hard.** See the finding above.

```
showdown replay tests/fixtures/live/hands/hu_full_hand.phh --hero sb --trace
showdown live --replay tests/fixtures/live/hands/hu_river_shove.phh --hero sb
.venv\Scripts\python -m pytest tests/test_gate_v.py tests/test_gate_v_slow.py -m "slow or not slow" -s
```

### Amendment: a floor on solver narrowing: bar 5 PASS (2026-11-19)

Ian chose this after the finding above. The rule and bar 5 were pre-registered in
DECISIONS 47's amendment (commit f20eb03) before any code.
- **The rule.** On a solved street each move multiplies the mover's hands by
  max(the solver's frequency, the floor). The floor is DECISIONS 46's: 0.25 for
  a check, 0.10 otherwise.
- **Who gets it:** both players.
- **What it does not change:** Ian's action on the current street, which still
  comes from the solve.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 5. Hand-worked floors | 5 walks on hand-made nodes, each with three hands in the range and one outside it: check-check (a check below and above 0.25), check-bet-call (both players on one line), bet-call (a bet below 0.10, and a call), an off-tree bet then a raise mapped to the tree, and check-bet-raise. Every multiplier and narrowed weight equals the hand calculation, and the hand outside the range stays at 0. The older walk test's 0/1 multipliers are now 0.10/1 | to 1e-9 | PASS |

**How it got here.** The first run of bar 5's test passed, but it had only 4
walks, one short of the pre-registered "at least 5".
- **The fix:** a fifth walk (check-bet-raise) was added, and the rerun passed.
- **Nothing else changed:** no rule, floor or expected number.

**Gate R's river trace with the floor** (reported, not gated). The BB's range
after its turn lead weighs 42.2 combos at Ian's turn node, where it was 1.9.

| | Third of the pot | Shove |
|---|---|---|
| The BB's range at the river node | 1,081 combos, weight 5.54 (was 0.38), fingerprint 2486afb6d1ca | 1,081 combos, weight 4.42 (was 0.98), fingerprint c7fd172f9315 |
| The advice | ALL-IN 41.8 bb (call 7%, all-in 93%); was CALL | CALL (100%), unchanged |
| Equity against it | 91.6% (was 73.6%) | 87.1% (was 45.2%) |

- **The turn advice is unchanged:** raise to 13.81 bb (call 36%, raise 64%).
  The floor changes the river solve's starting ranges, not the turn solve.
- **Bars 1 to 4 were not re-measured,** as Ian chose. Bar 1's fast test still
  passes with the floor: the two lines keep different ranges.

```
.venv\Scripts\python -m pytest tests/test_gate_v.py -k "bar5 or off_tree" -s
```

## Gate PA: heads-up push/fold with a 10% ante: PASS (2026-11-19)

Evidence:
- `tests/test_gate_pa.py` (fast suite): bars 1, 4 and 5;
- `tests/test_gate_pa_slow.py` (`py gate.py --full`): bar 3, and 10 bb
  re-solved from scratch with and without the ante.

The bars were pre-registered in DECISIONS 48 (commit 2d95739) before any code.
The amendment capping both fold payoffs at the stack was added while coding,
before any solve. Every bar passed on the first run.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. Exploitability, ante 0.1 | worst 3.77e-6 bb (14 bb); 7.99e-7 at 1 bb | ≤ 1e-5 at every depth, 1–20 bb | PASS |
| 2. Ante 0 reproduces today | all 20 depths re-solved with `--ante 0`: the file is byte-identical to `data/pushfold.json` (`cmp`) | exact | PASS |
| 3. HoldemResources "Ante 10%" | 100% of compared classes agree at every depth, pusher and caller; no disagreements; at most 9 exclusions at a depth (the caller at 4 bb) | ≥ 95% per depth; > 17 exclusions is a finding | PASS |
| 4. Closed forms with the ante | tree value and exploitability equal the closed forms at 1 and 6 bb, on random and pure strategies; fold EVs −0.6 (SB) and −1.1 (BB) at 10 bb | to 1e-12 | PASS |
| 5. The export | `data/pushfold_ante10.json`: `data/pushfold.json`'s format plus `"ante": 0.1`; `load` reads 0 for files without it; stored exploitability and value equal a fresh tree's at 1, 10 and 20 bb | exact, 1e-12 | PASS |

**The solve.** `cfr_plus`, 1,000 iterations per depth, as Gate D:

| Stack | Exploitability | SB value | SB jams | BB calls | (no ante: jams, calls) |
|---|---|---|---|---|---|
| 1 | 7.99e-7 | +0.00000 | 100.0% | 100.0% | 100.0%, 100.0% |
| 5 | 1.90e-6 | +0.05513 | 73.8% | 67.7% | 71.5%, 62.1% |
| 10 | 2.39e-6 | −0.04935 | 61.7% | 41.2% | 58.3%, 37.4% |
| 15 | 3.75e-6 | −0.14475 | 50.2% | 30.7% | 45.7%, 28.5% |
| 20 | 3.25e-6 | −0.20931 | 42.9% | 24.1% | 40.1%, 21.7% |

The ante solve took 3,451 s and the ante-0 re-solve 1,119 s, one after the other.

**Calibration of bar 3's parser** (not a bar). The same parser and rule, run on
the page's "No Ante" tab against Gate D's `data/pushfold.json`, agree at 99.4%
or more at every depth. The three disagreements are 53s at 4 bb, 43s at 8 bb
and 84s at 9 bb, all pusher cells near a chart boundary. So the parser reads the
page correctly, and a perfect match on the ante tab is not the parser hiding
misses.

**Conventions.** The page does not say how it counts the ante. Its chart agrees
with ours on every compared class, which suggests the same convention: each
player posts 0.1 bb, and S is the stack before the blinds and antes.

**Rerun:**
```
showdown pushfold build --ante 0.1 --out data/pushfold_ante10.json
.venv\Scripts\python -m pytest tests/test_gate_pa.py tests/test_gate_pa_slow.py -m "slow or not slow" -s
```

## Gate Q: the preflop re-solve with a 4× 3-bet and fitted R: FAIL, bars 4 and 5 (2026-11-21)

Evidence:
- `tests/test_gate_q.py` (fast suite);
- `tests/test_gate_q_slow.py` (`-m "slow or not slow"`): 61 passed, 2 failed, in 377 s;
- `data/preflop_r_fit.json` (commit 1411d6c);
- the product model, now `data/preflop_model_v2.json`;
- bar 5's fixture, `tests/fixtures/live/model_spots_q.toml`.

The bars were pre-registered in DECISIONS 49 (commit 50c910a) before any code. The one
amendment, bar 6's 200 hands of its own, came before the first fit run (7f30b22). The fixture
was written from `showdown preflop chart` on the product model, before bar 5's test ran.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. Exploitability | all 27 solves (9 depths × R −0.05, fit, +0.05); worst 2.87e-4 bb/hand (100 bb, −0.05); a fresh best response at 25 and 100 bb matches the stored value | ≤ 1e-3 | PASS |
| 2. Closed-form payoffs | every terminal utility at 25 and 100 bb, for all three R sets: 428,415 terminals each (169 × 169 × 15) | to 1e-12 | PASS |
| 3. The jam lean at 50 bb | the BB jams over the open in 3.1% and 3-bets in 30.4%, all of it to 10 | jam ≤ 10%, 3-bets ≥ 5% | PASS |
| 4. R settles | the 3× pot was measured in neither round (the model reaches it in at most 0.006% of deals); the measured cells moved 0.036 to 0.098 | each pot measured in both rounds at some depth; every cell within 0.02 | **FAIL** |
| 5. Advisor spots | all 31 spots match: action, R flag, size, notes, and the mix to 1e-12. Latency p95 is 67 ms over 133 suggestions. But there are 0 `bb_vs_jam` spots, 0 at the 3× size, and 0 suggested 3× 3-bets: the model reaches the 3× 3-bet (at most 0.002%), the jam over it (0.000%) and the SB's first-in jam (at most 0.034%) at no depth | ≥ 4 per decision and per size, ≥ 2 suggested per size; a size reached at no depth is a FAIL | **FAIL** |
| 6. Live solves legal | Gate V's 500 hands: 221 answers, all legal (11 in 4× pots). Bar 6's 200 4× hands: 574 answers, all legal | ≥ 100; ≥ 20 in the 4× hands | PASS |
| 7. Live latency | on bar 6's hands, 119 decisions with a live solve. Turn: 68, p95 1.81 s. River: 51, p95 0.13 s | turn ≤ 3.0 s, river ≤ 1.0 s, ≥ 30 per street | PASS |

**R by round** (20 flops a cell, seed 20261119; "fill" means taken from another depth or the 0.90 default):

| Pot | Depth | Round 1 (SE) | Round 2 (SE) | Change |
|---|---|---|---|---|
| open | 25 | 0.721 (0.040) | 0.626 (0.050) | −0.095 |
| open | 50 | 0.774 (0.015) | 0.711 (0.037) | −0.063 |
| open | 100 | 0.777 (0.019) | 0.679 (0.038) | −0.098 |
| 4× | 25 | 1.020 (fill: 50 bb) | 1.101 (fill: 50 bb) | not measured |
| 4× | 50 | 1.020 (0.026) | 1.101 (0.012) | +0.081 |
| 4× | 100 | 1.021 (0.016) | 1.057 (0.012) | +0.036 |
| 3× | all | 0.90 (fill) | 0.90 (fill) | not measured |

**What the model does** (reported, not gated). As R fell, calling the open got worse:
- At 100 bb, the BB facing the open folds 35.1% (old model 3.0%), calls 20.1% (75.7%) and
  3-bets to 10 in 44.8% (the old model 3-bet to 7.5 in 12.8%).
- The BB's jam over the open is 44.8% at 25 bb (old 36.7%) and 0.0% at 100 bb.
- The SB opens 86.6% at 100 bb (old 87.9%) and 80.2% at 25 bb (old 58.0%).
- The 3-bet to 7.5 is never used. Its R stayed at the 0.90 fill while the 4× pot measured
  1.06 to 1.10, so the 3× size was never reached and never measured.

**Gate R's three saved hands** under the new model:
- preflop and the flop are unchanged;
- `hu_full_hand`: the turn goes from a raise to 13.81 to a call, and the river from all-in
  to a call;
- `hu_river_shove`: the turn is a call, not a raise, and the river call is now 81.5%;
- `hu_short_stack_river`: unchanged.

**Older tests on the new model** (DECISIONS 49's report rule): `py gate.py` with the new model
in place gave 2 failed and 486 passed. Both failures came from the switch:
- `tests/test_gate_g_model.py:307`: the `showdown advise` CLI facing a 3 bb open with K9s
  now says "RAISE 12 bb" (4×), not "RAISE 9 bb";
- `tests/test_postflop.py:43`: the typed 100 bb 3-bet pot now uses the 3-bet to 10 (pot 200,
  stack 900 chips), not 7.5 (150, 925), by Ian's more-common-size rule.

Both pass again with the old model back.

**Solve times:**
- round 1: 5,149 s for the run that finished, resumed from the cache after two stops (the
  laptop went on battery once, and a session ended once);
- round 2: 12,445 s;
- the product build: 7,064 s with 12 workers, after one rerun (the first run died when its
  session ended).

**After the gate.** Ian chose to stop step 4 here (DECISIONS 49, Result):
- the old model stays live, and `data/preflop_model.json` is byte-identical to before;
- the new model is kept, unused, as `data/preflop_model_v2.json`;
- step 5 builds on the old model;
- no successor gate is registered.

While the old model is live, Gate Q's slow tests skip: their fixture wants a version 2
`data/preflop_model.json`.

**Rerun** (on AC; the fit takes about 6 h and the build about 2 h):
```
showdown preflop fit-r --round 1
showdown preflop fit-r --round 2
showdown preflop build --workers 12
.venv\Scripts\python -m pytest tests/test_gate_q.py tests/test_gate_q_slow.py -m "slow or not slow" -s -rs
```
To rerun only the tests, copy `data/preflop_model.json` to `data/preflop_model_v1.json`, and
`data/preflop_model_v2.json` to `data/preflop_model.json`; afterwards, put them back.

## Gate M: the six-max preflop spot engine: FAIL, bar 3 only (2026-11-22)

Evidence:
- `tests/test_gate_m.py` (fast suite): bar 1;
- `tests/test_gate_m_slow.py` (`-m "slow or not slow"`): bars 2 and 3, over 102 charts
  (every allowed seat and limper count, 3 profiles, 2 antes, 169 classes, 40,000 deals
  each);
- the engine at aa25000, the profiles in `data/sixmax_profiles.json` (f296dda).

The bars were pre-registered in DECISIONS 53 (commit b7657ee) before any spike or engine
code. The study-only amendment (SCOPE A13) came before scoring and moved no bar. Gate M
was scored once, at aa25000, in 302 s on 12 processes. A rerun with an added diagnostic
(below) reproduced every gated number exactly.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. Closed forms | 21 of 21. Everyone folds: each raise's EV is the pot, at every allowed seat and limper count, both antes, 4 hands. One caller holding KK, the BB's limped pot against QQ, and the stack-off against a limp-reraising AA: exact. The 3-way pot (AsAh, KhKd, QcQs): within 4 SE of `multiway.pot_shares` at all 3 sizes | 1e-9; 4 SE | PASS |
| 2. Monotonic | **Ante:** 1,393 classes compared, none that enters with no ante folds with it. **Limpers:** 765 offsuit classes compared, no new iso with one more limper. **Sizes:** 23 premium spots compared, the best size against loose-passive is never smaller than against tight. Left out as close or review: 7,226, 2,511 and 37 | no violation | PASS |
| 3. PokerStrategy's opens | Raise or not, on the classes our tier calls clear: UTG 100% (36 classes), HJ 50.0% (6), CO 100% (13), BTN 100% (32), SB 65.2% (23). Ours opens A9s, ATo, A9o from the HJ, and A5o–A8o and 22–55 from the SB, where the chart folds | ≥ 85% at each seat | **FAIL** |

**Why bar 3 failed: no bug, so no fix.** One reproduce, as the rule allows.
- SB 22, opening to 2.5: the CLI gives +0.94 bb, as worked by hand. The fitted regular
  BB calls 17.3% and 3-bets 7.5% against a 3 bb open, and calls 2.5 points more against
  2.5 bb, so it folds about 73%.
- HJ A9o: +0.29 bb, from the same fold-heavy players behind.
- The engine answers its profile correctly. The 2009 online regulars defend less than
  PokerStrategy's "standard opponent", so the engine steals wider from the HJ and SB.
- The bar is unchanged. Its test is a strict xfail, so a pass would show up.

**The tier leaves few clear classes** (a finding). Across the 102 charts: 6,322 clear,
10,629 close (4,338 of them size only: every band point picks the same kind of action)
and 287 review. In the unopened regular charts, only 6 (HJ) to 36 (UTG) classes are
clear. So bars 2 and 3 compare a small, strong-or-weak subset.

**Reported after scoring, not a bar.** The same raise-or-not comparison on every class
whose kind of action (fold, limp, raise) is the same at all 9 band points:

| Seat | Kind-stable classes | Agreement | Ours opens, the chart folds |
|---|---|---|---|
| UTG | 43 | 100% | none |
| HJ | 18 | 77.8% | A9s, A8s, ATo, A9o |
| CO | 37 | 89.2% | A5o–A8o |
| BTN | 112 | 96.4% | Q6o, K2o–K4o |
| SB | 169 | 39.1% | everything the chart folds: the engine opens all 169 classes against the regular BB |

**Reported, not gated: classes that isolate** (best action a raise), against tight /
regular / loose-passive limpers:

| Spot | No ante | Ante 0.5 |
|---|---|---|
| HJ, 1 limper | 40 / 46 / 29 | 169 / 107 / 62 |
| CO, 1 limper | 51 / 56 / 41 | 169 / 160 / 81 |
| CO, 2 limpers | 36 / 58 / 40 | 91 / 99 / 57 |
| BTN, 1 limper | 89 / 76 / 54 | 169 / 169 / 128 |
| BTN, 2 limpers | 46 / 64 / 49 | 116 / 116 / 78 |
| BTN, 3 limpers | 36 / 66 / 47 | 44 / 97 / 63 |
| SB, 1 limper | 165 / 130 / 59 | 169 / 169 / 150 |
| SB, 2 limpers | 38 / 67 / 47 | 102 / 115 / 62 |
| SB, 3 limpers | 36 / 63 / 44 | 37 / 73 / 51 |
| BB, 1 limper | 169 / 165 / 100 | 169 / 169 / 169 |
| BB, 2 limpers | 37 / 81 / 52 | 94 / 123 / 83 |
| BB, 3 limpers | 35 / 65 / 46 | 37 / 86 / 52 |

- Against loose-passive limpers the engine isolates fewer hands, not more. They call more
  and fold only 39% to an iso, against tight limpers' 54%.
- With the 0.5 ante, 3 bb is dead, so isolating one limper with any two cards is often
  the answer.
- Best iso sizes against loose-passive and tight were equal in 54 of 60 premium spots.
  In the other 6, loose-passive's was 1 bb larger: HJ and CO with one limper, mostly
  with no ante.

**The example the brief asked for:** `showdown sixmax BTN A5s --limpers 2 --ante 0.5
--profile loose-passive` prints the ranges, then fold 0.00, overlimp +0.49, iso to 5
+1.92, iso to 6 +1.99, and iso to 7 +2.16 (SE 0.05, best). Its verdict is clear, 7.2
standard errors ahead of iso to 6.

**Rerun** (about 5 minutes on 12 processes; needs the PokerStrategy pages in
`data/external/pokerstrategy/`):
```
.venv\Scripts\python -I spikes\2026-11-22-phh-sixmax-profiles.py
.venv\Scripts\python -m pytest tests/test_gate_m.py tests/test_gate_m_slow.py -m "slow or not slow" -s -rx
```
The spike reads the 20 GB PHH zip in about 13 minutes and rewrites
`data/sixmax_profiles.json`.

## Gate M2: the "standard" six-max profile: FAIL, bar 3 only (2026-11-22)

Evidence:
- `tests/test_gate_m.py` and `tests/test_gate_m2.py` (fast suite): bar 1;
- `tests/test_gate_m2_slow.py` (`-m "slow or not slow"`): the fit check, and bars 2 and 3
  over the standard profile's 34 charts;
- the profile at 1e2c80e. The BB's defence is fitted to VIP-Grinders' "Big blind defense"
  (`data/external/vip-grinders/`). The SB and other players behind are assumed.

The bars were pre-registered in DECISIONS 54 (commit cca2bed) before the profile existed.
Ian then chose a fit over hand-picked numbers, recorded as a dated amendment before
scoring. A run on the hand-picked numbers (e156792) was stopped and its output never read.
Gate M2 was scored once, at 1e2c80e, in 117 s.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. Closed forms | Gate M bar 1's 21 checks pass unchanged. The seat lookup is exact at both antes: UTG 72o folds to the BB's 3-bet (EV −X); from the HJ every open wins the pot. The profile equals the regular profile except for its seat defence, and its BB rates equal the saved page's midpoints | 1e-9 | PASS |
| 2. Directions, kind-stable classes | **Ante:** 1,135 compared, none that enters with no ante folds with it. **Limpers:** 565 offsuit classes compared, no new iso with one more limper | none; ≥ 100 and ≥ 50 compared | PASS |
| 3. PokerStrategy's opens, kind-stable classes | UTG 12 compared (100% agree), HJ 15 (86.7%), CO 26 (96.2%), BTN 85 (81.2%), SB 88 (59.1%) | ≥ 30 compared and ≥ 85% at each seat | **FAIL** |

**Bar 3, seat by seat.** The clear-only agreement (Gate M's rule) is in brackets.
- **UTG, HJ and CO: too few kind-stable classes** (12, 15, 26; clear only 5, 7, 16).
  Where they are compared, they agree 87 to 100%. The band's "players behind call 10
  points less" corner drops the cold-callers' 4% and the SB's 0% calls to 0, and the BB's
  to 10 to 23%. At that corner, stealing pays with almost any hand. So even UTG 72o
  (−0.43 bb to open at the base point) is close, not kind-stable.
- **BTN: 81.2%** (77.5% clear). The engine folds 16 hands the chart opens: weak suited
  connectors and gappers (T3s, 94s, 84s, 74s, 64s, 53s, 43s and others) and T6o, 96o,
  86o, 76o, 65o. It opens 63 classes, the chart 120. The chart opens to 2 bb. The
  engine's smallest open is 2.5 bb, against a BB that calls 40.5% and 3-bets 12%.
- **SB: 59.1%** (46.2% clear). The engine opens all 169 classes at the base point. The
  BB folds about 42% to a 2.5 bb SB open. With R 0.90 for the SB as an out-of-position
  raiser, even 72o is +0.03 bb (close). Gate Q measured an out-of-position caller's R at
  0.63 to 0.78, so 0.90 is likely generous here.

**Why no fix.** One reproduce (UTG 72o, SB 72o): every number follows from the profile, the
band and R as registered. Nothing is a bug, so the result stands and the bar is a strict
xfail.

**What it says:**
- With "standard" the engine opens about as a standard chart does from UTG to CO.
- From the BTN it opens tighter than PokerStrategy's 2 bb chart.
- From the SB it still opens too wide.
- Kind-stability needs a narrower fold band, or players behind who call more, to say
  much in early seats.

**Rerun:**
```
.venv\Scripts\python -m pytest tests/test_gate_m.py tests/test_gate_m2.py tests/test_gate_m2_slow.py -m "slow or not slow" -s -rx
```

## Gate K: the six-max drill trainer: PASS (2026-11-22)

Evidence: `tests/test_gate_k_slow.py` (`-m "slow or not slow"`), with the trainer at
80e0c4e. The bars were pre-registered in DECISIONS 55 (commit 26406c6) before any trainer
code. Gate K was scored once, in 365 s. Two scripted sessions of 300 drills each used seed
20261122, the standard profile and a random ante. Every drill was checked against a fresh
`sixmax.answer`, worked out in 12 processes.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. Grading | Session A (best kind every time): 300 of 300 good. Session B (a kind drawn uniformly, seed 7): 107 good, 40 marginal, 153 review, 0 mismatches. Every review's bb lost is exact (largest gap 0) | all match; review bb to 1e-9; ≥ 30 good, ≥ 10 marginal, ≥ 30 review | PASS |
| 2. Speed | Start of a drill to its prompt, session A, first deals included: median 0.34 s, 95th percentile 0.72 s, max 1.50 s | median ≤ 2 s, p95 ≤ 5 s | PASS |
| 3. The log | Each session's log has 300 lines, each with an answer. The summaries' counts and bb totals (0.000 and 344.107) equal the sums over the lines | exact; bb to 1e-9 | PASS |

**Reported, not gated:**
- 16 of the 300 drills had a clear fold as their best action, after the 1-in-5 thinning.
- Session B's grades by tier:

  | Tier | Good | Marginal | Review |
  |---|---|---|---|
  | Clear | 20 | 0 | 53 |
  | Close | 76 | 40 | 76 |
  | Review | 11 | 0 | 24 |

  Marginal grades occur only in close spots, as the rule implies.

**Why the grades equal a fresh answer.** The trainer deals each seat and limper count once
per session; the ante changes no deal. It puts the deal's random state back before each
hand, so the engine draws the same hero combos as `sixmax.answer` would.

**Rerun:**
```
.venv\Scripts\python -m pytest tests/test_gate_k_slow.py -m "slow or not slow" -s
```

## Gate M4: R 0.75 for an out-of-position raiser and loose-passive limpers in "standard": FAIL, bar 3 only (2026-11-22)

Evidence:
- `tests/test_gate_m.py`, `tests/test_gate_m2.py` and `tests/test_gate_m4.py` (fast suite):
  bar 1;
- `tests/test_gate_m4_slow.py` (`-m "slow or not slow"`): bars 2 and 3 over the standard
  profile's 34 charts, plus the reported charts;
- the code at 6f06a4c.

The bars were pre-registered in DECISIONS 57 (commit d6e2d93) before fix (b) was coded.
Gate M4 replaces Gate M3, which was registered and never scored. It was scored once, at
6f06a4c, in 127 s.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. Closed forms | Gate M's 21 checks and Gate M2's 3 pass unchanged (Gate M2's profile check on the profile as scored). The BB raising a KK limper who always calls matches 0.75 × M[hero, KK] × (0.5 + 6 × ante + 2X) − (X − 1) for AA, KK, A5s and 72o, every size, both antes. "standard" equals regular except the seat defence and the five limper rates, which equal loose-passive's | 1e-9 | PASS |
| 2. Directions, kind-stable classes | **Ante:** 1,019 compared, none that enters with no ante folds with it. **Limpers:** 610 offsuit classes compared, no new iso with one more limper | none; ≥ 100 and ≥ 50 compared | PASS |
| 3. PokerStrategy's opens, kind-stable classes | UTG **7** compared (100% agree), HJ 13 (100%), CO 21 (100%), SB 25 (100%). The BTN, not scored, is identical to Gate M2's chart, as required | ≥ 10 compared and ≥ 85% at each of UTG, HJ, CO, SB | **FAIL** (UTG count) |

**Bar 3, seat by seat.** The clear-only agreement is in brackets.
- **UTG: 7 kind-stable classes**, under the minimum of 10. All 7 agree with the chart: AA,
  KK, QQ, JJ, TT, AKs, AKo (no clear classes). Gate M2 had 12.
- **HJ: 13, 100%** (5 clear, 100%). The engine opens 38 classes, the chart 40.
- **CO: 21, 100%** (11 clear, 100%). The engine opens 55, the chart 68.
- **SB: 25, 100%** (12 clear, 100%). The engine opens **78 classes**, the chart 66. Under
  Gate M2 (R 0.90) it opened all 169.
- **BTN (reported):** 85 compared, 81.2% (77.5% clear), as in Gate M2. It opens 63, the
  chart 120.

**Why UTG fell short: no bug, so no fix.** One reproduce, as the rule allows: the UTG chart
at R 0.90 and at 0.75.
- Five classes stable at 0.90 are not at 0.75: AQs, AJs, ATs, AQo and AJo.
- Each still opens to 2.5 at the base point, for +0.18 to +0.33 bb.
- Each flips to fold at one band point only: R −0.1, so 0.65 out of position, with players
  behind calling 10 points more.
- That follows from the registered R, the band and the profile. The result stands. The
  bar's test is a strict xfail, so a pass would show up.

**Reported, not gated:**
- **Regular profile at the new R:** UTG 65 kind-stable (100%), HJ 12 (100%), CO 28
  (92.9%: A8o, A7o open), BTN 112 (96.4%), SB 169 (39.1%). Regular still fails at the SB,
  where the engine opens every class against the 2009 blinds.
- **The SB's opens** (unopened, no ante): standard 78 of 169; regular, tight and
  loose-passive 169.
- **Classes that isolate under "standard"** (no ante / ante 0.5):

  | Spot | Isolates |
  |---|---|
  | HJ, 1 limper | 25 / 69 |
  | CO, 1 limper | 31 / 87 |
  | CO, 2 limpers | 29 / 49 |
  | BTN, 1 limper | 39 / 68 |
  | BTN, 2 limpers | 33 / 49 |
  | BTN, 3 limpers | 31 / 42 |
  | SB, 1 limper | 23 / 43 |
  | SB, 2 limpers | 24 / 29 |
  | SB, 3 limpers | 24 / 27 |
  | BB, 1 limper | 45 / 169 |
  | BB, 2 limpers | 30 / 43 |
  | BB, 3 limpers | 30 / 30 |

**What it says:**
- R 0.75 fixes the SB. It now opens 78 classes, close to the chart's 66, and every
  kind-stable class agrees.
- UTG to CO agree wherever they are kind-stable. At UTG the band's harshest corner leaves
  only the strongest 7 hands stable.
- The BTN is unchanged, still tighter than PokerStrategy's 2 bb chart.

**Rerun** (about 2 minutes on 12 processes):
```
.venv\Scripts\python -m pytest tests/test_gate_m.py tests/test_gate_m2.py tests/test_gate_m4.py tests/test_gate_m4_slow.py -m "slow or not slow" -s -rx
```

## Gate W: six-max hand review by spot: PASS (2026-11-22)

Evidence:
- `tests/test_gate_w.py` (fast suite): bar 1, on the fixture `tests/fixtures/sixmax_review/`;
- `tests/test_gate_w_slow.py` (`-m "slow or not slow"`): bars 2 and 3, on the fixture and
  the 10,000 Pluribus hands (phh-dataset, DECISIONS 25);
- the review at 5adbd88.

The bars were pre-registered in DECISIONS 58 (commit d6e2d93) before any review code. The
fixture and its labels were committed on their own at 00a0330, before the classifier
existed. Gate W was scored once, at 5adbd88, in 221 s. Bar 1's test had also run once
during development and passed. The classifier did not change after that.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. Classification | 55 hands (52 PHH files, 3 hands in one PokerStars file), all match their labels. 33 graded: every seat, 0 to 3 limpers, both antes, every kind. 21 skipped: all 10 causes, and two hands where an earlier cause wins. One hand without Hero is not counted | every hand exact; coverage as listed | PASS |
| 2. Grading | 33 fixture decisions and 300 Pluribus decisions (seed 20261122) against fresh `sixmax.answer`s: 0 mismatches in grade, best action or tier. Largest bb-lost gap 0 | all match; bb to 1e-9 | PASS |
| 3. Real hands | 10,000 of 10,000 Pluribus hands parse. Pluribus is in all 10,000: 5,255 graded, 4,745 skipped (raised before you 4,482, no decision 165, the SB completed 98), none unexplained. The report's tier and grade counts, bb lost (in all and on clear spots) and each leak's count and bb equal the sums over the decisions | ≥ 99% parse; all accounted for; ≥ 2,000 graded; sums to 1e-9 | PASS |

**Reported, not gated** (Pluribus, standard profile):
- **Speed:** loading and reviewing the 10,000 hands took 46 s.
- **Grades by tier:**

  | Tier | Good | Marginal | Review |
  |---|---|---|---|
  | Clear | 469 | 0 | 16 |
  | Close | 3,712 | 827 | 73 |
  | Review | 151 | 0 | 7 |

- **bb lost against the engine's best action:** 128.87 in all, 3.30 on clear spots.
- **The top 3 "leaks"**, all in the small blind, unopened. They mostly show the engine's
  limits:
  1. **Limps where the best is a raise:** 18 hands, 22.45 bb. Pluribus sometimes limps
     KK, QQ, AK and AQ from the SB. The engine treats every raise behind a limp as a fold,
     so these limps look worse than they are: the five shown lose 1.7 to 6.8 bb each.
  2. **Folds where the best is to complete:** 58 hands, 7.44 bb, about 0.19 bb each (Q4o,
     Q3o). Under "standard" the BB raises only 11% of hands against a limp, which makes
     completing cheap.
  3. **Folds where the best is a raise:** 9 hands, 2.30 bb (K2o, K3o). All close spots.

**After scoring** (display only, no gated number changes): the report now names each hand
by its full source. File names alone repeat across Pluribus's folders (`29.phh`).

**Not part of the gate:** the plan's check on Ian's own hands, which is coverage plus five
hands reviewed per leak. It waits for a file from an allowed source (DECISIONS 58).

**Rerun** (about 4 minutes; needs the Pluribus hands in `data/external/phh/`):
```
.venv\Scripts\python -m pytest tests/test_gate_w.py tests/test_gate_w_slow.py -m "slow or not slow" -s
```

## Trainer step 0: the pivot recorded: PASS (2026-11-27)

DECISIONS 59 and SCOPE A18 and A19, at 2204521. Docs only; no code or bar changed.
`py gate.py`, run by the worktree recipe, printed `GATE PASS` in 2 min 25 s.

## Gate Y: grades on GTO Wizard's scale, player types, push/fold with types: PASS (2026-11-27)

Evidence:
- `tests/test_gate_y.py` (fast suite): bar 4 and the grade's branches;
- `tests/test_gate_y_slow.py` (`-m "slow or not slow"`): bars 1 to 3;
- the code at 6afc847.

The bars were pre-registered in DECISIONS 60 at be08937, before the type fit, the grade or
any code. The type fit, `spikes/2026-11-27-phh-sixmax-types.py`, ran once on AC in 572 s
(`docs/sixmax-types.md`). Gate Y was scored once, at 6afc847; the slow file took 311 s.
`py gate.py` printed `GATE PASS` in 194 s.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. The grade rule | 300 drills (seed 20261127, random types and ante, answers uniform over the spot's actions, seed 7): 0 mismatches against labels worked from fresh answers; bb and % gaps 0. Best 86, Correct 50, Inaccuracy 31, Wrong 41, Blunder 92 | all match; bb to 1e-9; each label ≥ 5 | PASS |
| 2. The band floor | 54 answers win at a band point, all 54 not the base best; none graded below Correct | none below Correct; ≥ 10 not the base best | PASS |
| 3. Type directions | Steals, kind-stable: Nit table vs LAG 384 compared, raises 384 vs 267, 0 violations; Weak-tight rec vs Calling station 478 compared, 478 vs 334, 0 violations. Isos with limpers' fold to an iso 10 points lower: 1,668 offsuit compared, 0 new isos | no violation; ≥ 50 compared; the tighter table raises at least as many | PASS |
| 4. Push/fold | 7 types × 5, 10, 15, 20 bb × both seats: best-response and Nash EVs equal `cfr.best_response` and `policy_value` to 1e-9; charts equal the tree's best response off ties | to 1e-9 | PASS |
| 5. Old gates | Re-run once: Gate K (pinned to the kind-only drill) 107 good, 40 marginal, 153 review, 344.107 bb, as recorded; Gates M, M2, M4 and W: 51 passed, 3 xfailed (the recorded bar 3 FAILs), every printed number as recorded. compose("standard", "standard") is the standard profile | unchanged | PASS |

**Reported, not gated:**
- **The groups** (players with 500+ hands): Nit 1,095; TAG 8,535; LAG 2,042; Maniac 627;
  Weak-tight rec 985; Calling station 6,463; all 19,747. The trait cards are in
  `docs/sixmax-types.md`.
- **Drill speed with types:** median 0.12 s, 95th percentile 0.40 s, max 0.78 s.
- **Labels by tier:** clear 22 / 4 / 13 / 16 / 57 (Best to Blunder); close 60 / 45 / 17 / 23 /
  28; review 4 / 1 / 1 / 2 / 7.
- **Classes isolated**, standard table, no ante: at the CO with one limper, 26 against Nit
  limpers up to 69 against Maniacs. The 0.5 ante roughly triples it. The full list is in the
  test's output.

**Rerun** (about 8 minutes on 12 processes):
```
.venv\Scripts\python -m pytest tests/test_gate_y.py tests/test_gate_y_slow.py tests/test_gate_k_slow.py -m "slow or not slow" -s
```

## Gate Z: facing one open raise: FAIL, bar 3 only (2026-11-27)

Evidence:
- `tests/test_gate_z.py` (fast suite): bar 1;
- `tests/test_gate_z_slow.py` (`-m "slow or not slow"`): bars 2 and 3;
- the code at 39c50d3.

The bars were pre-registered in DECISIONS 61 at fd3863c, before any code for this step. Gate
Z was scored once, at 39c50d3: 37 charts in 62 s. `py gate.py` printed `GATE PASS` at
39c50d3. The slow tests of Gates Y, M4 and W were re-run once and printed every number as
recorded.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. Closed forms | Everyone folds (BTN vs CO, BB vs SB), a call heads-up, a 3-bet called, a 4-bet (KK folds, AA stacks off), the jam called: AA, KK, A5s, 72o, both antes, both opens, all to 1e-9 | to 1e-9 | PASS |
| 2. Directions | Nit vs LAG opener: 915 compared, nothing that continues vs the Nit folds vs the LAG; 3-bets or jams 915 vs 915. Nit vs Maniac: 919 compared, none; 919 vs 919 | no violation; Nit ≤ the other; ≥ 100 compared | PASS |
| 3. The chart | PokerStrategy's vs-open ranges (lessons 2256, 2257), 3 bb open, no ante, standard: 134 kind-stable classes over 7 spots; 107 agree on continue vs fold (79.9%). Per spot: BTN vs UTG 12/19, vs HJ 17/21, vs CO 26/32; SB vs UTG 10/10, vs HJ 9/10, vs CO 13/13, vs BTN 20/29. Three-way agreement 23.1% | ≥ 85% of ≥ 100 | **FAIL** |

**Bar 3's 27 disagreements** are all ours 3-bet, theirs fold:
- BTN vs UTG: KJs, KTs, QJs, QTs, AJo, KJo, QJo;
- BTN vs HJ: QTs, 44, 33, 22;
- BTN vs CO: A8s, A7s, A9o, 44, 33, 22;
- SB vs HJ: AJs;
- SB vs BTN: A8s, A7s, A6s, A9o, A8o, A7o, A6o, A5o, 55.

**Not a bug.** One hand was worked by hand: 72o on the BTN, CO opens to 3 bb, standard.
- Folds come 52.9% of the time; it is called 31.6%, with 30.4% equity in a 19.5 bb pot;
  it is re-raised 15.5%.
- That gives +0.014 bb for the 3-bet to 9, equal to the engine to 1e-15.

The cause is the model, under DECISIONS 61's assumptions:
- the opener folds 55% of its range to a 3× 3-bet;
- its call share falls 0.049 per bb of extra size (decided without Ian), so a 4× 3-bet gets
  67% folds;
- a called 3-bet in position realises R 1.00, whatever the hand.

Bar 2's "3-bet less against a Nit" holds only trivially, since every kind-stable class
3-bets against all three opener types.

**After the FAIL:** the result stands, and the bar is unchanged. Bar 3's test is a strict
xfail, so a pass would show up. The limit is documented in `docs/sixmax-preflop.md`. The
choice between a fix entry with a re-gate and a documented limit went to Ian through the
master session on 2026-11-27.

**Reported, not gated:** opener widths by type and seat, as fractions of hands:

| Type | UTG | HJ | CO | BTN | SB |
|---|---|---|---|---|---|
| standard | 0.150 | 0.190 | 0.270 | 0.450 | 0.400 |
| Nit | 0.100 | 0.127 | 0.181 | 0.301 | 0.268 |
| TAG | 0.158 | 0.200 | 0.285 | 0.474 | 0.422 |
| LAG | 0.217 | 0.274 | 0.390 | 0.650 | 0.578 |
| Maniac | 0.281 | 0.356 | 0.506 | 0.844 | 0.750 |
| Weak-tight rec | 0.066 | 0.084 | 0.119 | 0.198 | 0.176 |
| Calling station | 0.106 | 0.134 | 0.191 | 0.318 | 0.282 |

**Rerun** (about 2 minutes):
```
.venv\Scripts\python -m pytest tests/test_gate_z.py tests/test_gate_z_slow.py -m "slow or not slow" -s -rx
```

## Gate U: the trainer page in `showdown play`: PASS (2026-11-27)

Evidence:
- `tests/test_gate_u.py` (fast suite);
- `tests/test_gate_u_slow.py` (`-m "slow or not slow"`): bars 1 to 3;
- bar 4 in the browser through the preview tools;
- the code at db7aa21.

The bars were pre-registered in DECISIONS 62 at 6a9b430, before the session, page or lesson
code. The page was tried in the browser once before the commit. Gate U was scored once, at
db7aa21. `py gate.py` printed `GATE PASS` in 266 s. Gates K and Y's slow tests were re-run
once and printed every number as recorded.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. Grades through the API | 300 drills over HTTP (seed 20261128, answers uniform, seed 7): facing an open 106, six-max 107, push/fold 87. 0 mismatches against fresh answers; the API's results equal the log's; bb and % gaps 0 | all match; each family ≥ 50 | PASS |
| 2. Latency | `/api/hand` round trip, first deals included: median 0.11 s, 95th percentile 0.38 s, max 0.70 s | median ≤ 2 s, p95 ≤ 5 s | PASS |
| 3. The log | 300 lines; summary Best 101, Correct 38, Inaccuracy 20, Wrong 50, Blunder 91, bb lost 346.772, equal to the lines' sums | exact; bb to 1e-9 | PASS |
| 4. The browser | `showdown play` via `.claude/launch.json` (port 8766), `/trainer`. One drill per family, each with a graded result card: six-max (CO, A4o, unopened: open to 2.5, Best, "Steal from tight blinds"); facing an open (SB, 93o, UTG opens, ante 0.5: 3-bet to 7.5, Inaccuracy, 0.51 bb, 7.3% of the pot, with the Gate Z note); push/fold (BB, 11 bb, Q9s against a Maniac's jam: call, Best). No console errors. Screenshot taken | all three graded | PASS |

**Reported, not gated:** labels by family:

| Family | Best | Correct | Inaccuracy | Wrong | Blunder |
|---|---|---|---|---|---|
| Six-max | 36 | 12 | 12 | 17 | 30 |
| Facing an open | 29 | 14 | 8 | 20 | 35 |
| Push/fold | 36 | 12 | 0 | 13 | 26 |

**Rerun** (about 2 minutes):
```
.venv\Scripts\python -m pytest tests/test_gate_u.py tests/test_gate_u_slow.py -m "slow or not slow" -s
```

## Gate W2: the leak finder on PokerStars exports: PASS (2026-11-27)

Evidence:
- `tests/test_gate_w2.py` (fast suite): bar 1, on the fixture `tests/fixtures/sixmax_review_w2/`;
- `tests/test_gate_w2_slow.py` (`-m "slow or not slow"`): bars 2 and 3, and the reported
  Pluribus run;
- Gate W's tests, for bar 4;
- bar 5 in the browser;
- the code at 9b75002.

**History:**
- The bars were pre-registered in DECISIONS 63 at 8264372.
- The fixture's generator, hands and labels were committed on their own at 11b3389, before
  any review code.
- **A fixture bug, found before scoring.** A dry run of the new classifier skipped 9 hands
  for "ante". The generator had written the 0.5 bb ante as 0.5 chips, while the labels say
  0.5 bb. Fixed at 520515f: only those 9 files changed, labels.toml did not.
- Gate W2 was scored once, at 9b75002. `py gate.py` printed `GATE PASS` in 493 s.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. The fixture | 48 hands (45 PHH, 3 PokerStars), all classified as labelled: 21 facing an open, 24 unopened or limped, 3 skipped (raised before you, open called before you, open size). All 7 players' stats equal the labels to 1e-12, and their types: Ned Weak-tight rec, Sue Calling station, Mo Maniac, Tom TAG, Fay and Lou standard (20 and 28 hands), Hero Maniac | exact | PASS |
| 2. Grades | 45 graded fixture decisions against fresh answers under the composed profile and opener: 0 mismatches in label, best action or tier; bb gap 0 | all match; bb to 1e-9 | PASS |
| 3. The report | Labels (Best 22, Correct 10, Inaccuracy 4, Wrong 4, Blunder 5), by family (24 and 21) and bb lost (21.270) equal the sums. The fixture makes no leak group of 3 or more, so the per-leak sums held only vacuously here | exact | PASS |
| 4. Gate W unchanged | Gate W's fast and slow tests, with the CLI pinned to `--kind-only`: 6 passed; 33 fixture and 300 Pluribus decisions match, 5,255 Pluribus decisions graded, as recorded | unchanged | PASS |
| 5. The Review tab | `/trainer`'s Review tab, the fixture's `session.txt` picked: "Reviewed session.txt for Hero", 3 hands parsed, 3 graded (2 unopened or limped, 1 facing an open), all Best, 5 opponents standard (under 30 hands). Screenshot taken | the report shown | PASS |

**Reported, not gated:** the new review on Pluribus's 10,000 hands, in 778 s.
- **Coverage:** 8,947 graded (5,255 unopened or limped, 3,692 facing an open), against
  5,255 before. Skipped: raised before you 432, open called before you 343, no decision 165,
  the SB completed 98, open size 15.
- **Labels:** Best 4,180, Correct 3,527, Inaccuracy 183, Wrong 592, Blunder 465;
  1,989.07 bb lost.
- **Opponents:** 13 typed: Weak-tight rec 5, LAG 4, TAG 4.
- **The top 5 "leaks",** four of them Gate Z's limit (the engine overrates 3-bets facing an
  open):
  - BB vs LAG opener, calls where a 3-bet is best: 125 hands, 99.32 bb;
  - BB vs TAG, the same: 82 hands, 77.91 bb;
  - BTN vs LAG, the same: 52 hands, 67.09 bb;
  - SB vs LAG, the same: 47 hands, 44.99 bb;
  - UTG unopened vs a LAG table, opens where the best is a fold: 77 hands, 37.03 bb.

**Waiting on Ian, not a bar:** his own PokerStars export, with coverage by cause and 5 hands
per top leak checked by him.

## Gate Z2: the facing-an-open fix: FAIL, bar 3's count only (2026-11-27)

Evidence:
- `tests/test_gate_z2.py` (fast suite): bar 1, and unopened and limped answers unchanged;
- `tests/test_gate_z2_slow.py` (`-m "slow or not slow"`): bars 2 and 3;
- the code at a8daf5e.

**History:**
- Ian chose the fix and a re-gate on 2026-11-27 (option A).
- The bars were pre-registered in DECISIONS 64 at 83e8004, before the fix was coded.
- Gate Z2 was scored once, at a8daf5e: 5 min 21 s.
- **Under the pins, the old records reproduce.** With the scored model pinned
  (`GATED_OPENER_SLOPE`, `GATED_THREEBET_IP`), Gates Z, U and W2 were re-run once: Gate Z
  again gets 79.9% of 134, a strict xfail; Gate U and Gate W2 (and its Pluribus run) give
  every recorded number. 15 passed, 1 xfailed.
- **Two fast tests I had not run before committing, fixed afterwards.** `py gate.py` at
  9cb4f22 failed on them:
  - Gate M4's check compared the whole R table, so the two new entries broke it. It now
    compares only its four values, which are unchanged;
  - Gate U's test looks for "Gate Z" in the page's note, which my new wording had changed.
    The note was reworded back.
  - Neither touches Gate Z2's bars. The re-run gate is recorded in the next commit's line
    below.

| Bar | Measured | Bar | Result |
|---|---|---|---|
| 1. Closed forms | Gate Z bar 1's checks at the new model, the 3-bet called at R 0.85: AA, KK, A5s, 72o, both antes, both opens, to 1e-9. The opener's call share is identical at both 3-bet sizes | to 1e-9 | PASS |
| 2. Directions | Nit vs LAG opener: 889 compared, no violation; Nit vs Maniac: 839, none. 3-bets or jams: equal counts | as Gate Z | PASS |
| 3. The chart | 70 kind-stable classes over the 7 spots, 63 agree on continue vs fold (90.0%). Per spot: BTN vs UTG 4/4, HJ 6/6, CO 9/9; SB vs UTG 8/8, HJ 9/10, CO 12/12, BTN 15/21. Three-way 28.6%. Disagreements (ours 3-bet, theirs fold): SB vs HJ AJs; SB vs BTN A8s, A7s, A6s, A9o, A8o, A7o | ≥ 85% of **≥ 100** | **FAIL** (count) |

**What the fix did:**
- 72o on the BTN against a CO open to 3 bb now folds: the 3-bet to 9 is −0.27 bb and the
  3-bet to 12 is −1.19 (before: +0.01 and +0.40).
- The smaller 3-bet is now the better value size.
- But at the base point the engine still 3-bets most hands. Over the 5 spots × 2 antes it
  3-bets or jams 1,593 of 1,690 class-spots against a Nit opener, 1,600 against a LAG and
  1,290 against a Maniac. Most of those are close calls between fold and 3-bet, so fewer
  classes are kind-stable (70, against 134 before), and bar 3's minimum of 100 is missed.
- The agreement on those 70 classes passes the 85% share.

**After the FAIL:** the result stands, and the bar is unchanged. Bar 3's test is a strict
xfail, as Gates M's and Z's are. Ian was told through the master session. A further fix
(R by hand playability, or a lower opener fold to 3-bets) needs its own entry.

**Ian's answer (2026-11-27): a documented limit** (DECISIONS 64). No Z3 and no more tuning
towards the bar. The fix stays, and the page keeps its note on near-ties facing an open.

**Rerun** (about 5 minutes):
```
.venv\Scripts\python -m pytest tests/test_gate_z2.py tests/test_gate_z2_slow.py -m "slow or not slow" -s
```

**Rerun** (about 18 minutes, most of it Pluribus):
```
.venv\Scripts\python -m pytest tests/test_gate_w2.py tests/test_gate_w2_slow.py -m "slow or not slow" -s
```
