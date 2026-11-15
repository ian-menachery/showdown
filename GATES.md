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
