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
  average and current policies to 1e-10 at iterations 1, 2, 3, 10 and 60.
- Exploitability matches OpenSpiel to 1e-9 on three seeded random policies.
- Player 2's unique equilibrium holds within 0.02.

```
showdown solve kuhn --iterations 1000
```
