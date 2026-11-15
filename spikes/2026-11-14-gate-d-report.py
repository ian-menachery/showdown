r"""Gate D report, 2026-11-14: the per-depth table in GATES.md, plus HoldemResources' strategies
scored on our exact game. Needs data/external (DECISIONS 20).

Run from the repo root:

    .venv\Scripts\python -I spikes\2026-11-14-gate-d-report.py
"""


import sys
from pathlib import Path

sys.path.insert(0, str(Path("tests").resolve()))

import numpy as np  # noqa: E402
from test_gate_d_slow import load_holdemresources  # noqa: E402

from showdown import pushfold as pf  # noqa: E402
from showdown.equity.matrix import PreflopMatrix  # noqa: E402

sol = pf.PushFoldSolution.load("data/pushfold.json")
m = PreflopMatrix.load(sol.matrix_path)
hp_stacks, hp = load_holdemresources("push")
hc_stacks, hc = load_holdemresources("call")

print("| Stack | Exploitability | SB value | SB jams | BB calls | Push: agree/compared (excluded) | Call: agree/compared (excluded) | Disagreements |")
print("|---|---|---|---|---|---|---|---|")
worst_share = 1.0
notes = []
for d in sol.depths:
    rp = hp[np.flatnonzero(np.isclose(hp_stacks, d.stack))[0]]
    rc = hc[np.flatnonzero(np.isclose(hc_stacks, d.stack))[0]]
    cp, cc = pf.compare(d.push, rp), pf.compare(d.call, rc)
    worst_share = min(worst_share, cp.share, cc.share)
    dis = []
    if cp.disagree:
        dis.append("push " + ", ".join(cp.disagree))
    if cc.disagree:
        dis.append("call " + ", ".join(cc.disagree))
    print(
        f"| {d.stack:g} | {d.exploitability:.1e} | {d.value_sb:+.5f} | {d.push_share():.1%} | {d.call_share():.1%} "
        f"| {cp.agree}/{cp.compared} ({cp.excluded}) | {cc.agree}/{cc.compared} ({cc.excluded}) | {'; '.join(dis) or '—'} |"
    )
    hrc_value = pf.sb_value(rp, rc, d.stack, m)
    hrc_expl = pf.closed_form_exploitability(rp, rc, d.stack, m)
    max_diff_push = np.abs(d.push - rp).max()
    max_diff_call = np.abs(d.call - rc).max()
    notes.append((d.stack, d.value_sb, hrc_value, hrc_expl, max_diff_push, max_diff_call))
print(f"\nworst share {worst_share:.4f}")
print("\nstack  ours value  HRC strategies' value  HRC exploitability on our game  max|p diff| max|q diff|")
for s, v, hv, he, dp, dc in notes:
    print(f"{s:>5g}  {v:+.5f}     {hv:+.5f}               {he:.2e}                      {dp:.3f}       {dc:.3f}")
