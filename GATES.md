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
| Same 20 matchups vs pokerkit `calculate_equities`, 4,000 samples each | 20 of 20 within 3 SE | within 3 SE | PASS |
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

Bugs found by these tests before the gate was declared:
- **Range parser.** It upper-cased only the first two characters of a token, so
  "A2s-A5s" failed. Fixed.
- **A wrong hand count, in the test rather than the code.** The test claimed
  16/44 winning rivers for AsKs vs QhQd on Ts9s2dJc. The code said 13/44, and
  the code was right: a king gives QQ the straight K-Q-J-T-9. The test was
  corrected, with that reasoning written into it.

Full-suite run: 156 passed in 4 min 57 s, coverage 99%. In that run Gate B
measured ours at 16.9 s against OpenSpiel's 60.7 s, which still passes. The
machine was loaded, and both timings were slower than the Phase 2 run.

```
showdown equity AsAh KdKc
showdown matrix build          # about 20 minutes on 16 cores; reproduces the committed file
showdown matrix show AKs QQ
py gate.py --full
```
