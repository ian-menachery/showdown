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
- OpenSpiel's time differs between runs: 27 s here, 101 s in the Phase 0 spike.
  Ours was 10× to 40× faster in every run.

```
showdown solve leduc --iterations 200
py gate.py --full
```
