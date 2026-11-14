"""Reference-data spike, 2026-11-14. Evidence for DECISIONS 20 and docs/gate-d-reference.md.

Checks the two third-party files Ian approved downloading on 2026-11-14. Both
live in the gitignored data/external/ and are never committed:

- HoldemResources' heads-up push/fold raw data (the Gate D reference):
  data/external/hrc/holdemresources_hu_equilibrium.zip, with its two CSVs
  extracted by name to data/external/hrc/raw/.
- b-inary/poker-cfr's exact preflop equity table (BSD-2-Clause, commit a534708):
  data/external/b-inary/heads_up_pre_flop_equity.bin.

Run from the repo root:

    .venv\\Scripts\\python -I spikes\\2026-11-14-reference-data.py

Not part of the package and not linted by the gate. The chart values in the HRC
spot checks are a handful of thresholds from the public HUNE page, cited here
only to check that the raw data is the solution behind that chart.

Output on Ian's Windows laptop (Python 3.12.10):

    sha256 ok: 4 files
    HRC push: 169 classes (same names as ours), stacks 1.0-200.0 step 0.05, 3981 rows, values 0.00-1.00 in steps of 0.01
    HRC call: 169 classes (same names as ours), stacks 1.0-200.0 step 0.05, 3981 rows, values 0.00-1.00 in steps of 0.01
    HRC mixed classes (0.01 < p < 0.99) at 2-20 bb: push at most 3 per depth, call at most 2
    HRC every class pushes at 1 bb: True
    HRC vs chart: 10/10 spot checks agree (T3s, 32o, 72o, 63s, 53s, 43s push; Q2o, K2o, 22, A2o call)
    b-inary table: 1326x1326 u32, conflicting pairs 0, T + T' = 2*C(48,5) on every disjoint pair
    b-inary vs our exact enumeration: 8/8 identical integers (2*wins + ties)
    b-inary class pair counts identical to ours: True
    exact AA vs KK 0.819461, AKs vs QQ 0.460485, T9s vs AKo 0.405237
    our matrix vs exact, 14196 unique off-diagonal cells:
      max |error| 0.00463 (T4s vs 33: 0.48313 +- 0.00112 vs 0.48742), mean |error| 0.00086
      z mean -0.0881, sd 0.933, within 2 SE 0.9722, within 3 SE 0.9986, max |z| 3.83

Reading: the HRC raw data is the solution behind the public chart, on the same
game and stack definition as ours, and it mixes rarely enough that excluding
mixed classes costs little. The b-inary table agrees with our own evaluator to
the integer, so it is an exact reference for the whole matrix. Against it, our
Monte Carlo matrix's standard errors are honest and slightly conservative: the
z-scores have sd 0.93, 97.2% fall within 2 SE where a normal gives 95.4%, and
the largest of 14,196 is 3.83, about what that many normal draws give. The mean
z of -0.088 is an average signed error of -0.0001 in equity. Every cell is
scored on the same boards, so cell errors are correlated and that mean is not
an independent test of bias. At 20 bb it is worth 0.004 bb, which does not
matter for Gate D.
"""

import csv
import hashlib
import io
import zipfile
from pathlib import Path

import numpy as np

from showdown.equity.cards import ALL_COMBOS, CLASS_NAMES, class_index, parse_cards
from showdown.equity.exact import hand_vs_hand
from showdown.equity.matrix import PreflopMatrix, _static, exact_pair_counts

EXT = Path("data/external")
SHA256 = {
    "hrc/holdemresources_hu_equilibrium.zip": "650da7525b35e12adbc03df26d6690c30b583ff4b7d930156c104012a040ec9d",
    "hrc/raw/holdemresources_hu_push.csv": "ed588eda85842704adeb233e7f2a22331aa6b83543b23fce838788ba55e32cc2",
    "hrc/raw/holdemresources_hu_call.csv": "fa99898839ca9da23bb6193bdfcb873632fecc95b34079b79ff27670426682d3",
    "b-inary/heads_up_pre_flop_equity.bin": "006404b36d257fc9455da0d0f0ab89aef3e80ece56c8f3e770bad926cfe5ec8a",
}
BOARDS = 1_712_304  # C(48, 5)

for rel, digest in SHA256.items():
    if hashlib.sha256((EXT / rel).read_bytes()).hexdigest() != digest:
        raise SystemExit(f"{rel}: SHA-256 does not match")
print(f"sha256 ok: {len(SHA256)} files")

# The CSVs must be exactly the zip's members.
with zipfile.ZipFile(EXT / "hrc/holdemresources_hu_equilibrium.zip") as z:
    for name in ("holdemresources_hu_push.csv", "holdemresources_hu_call.csv"):
        assert z.read(name) == (EXT / "hrc/raw" / name).read_bytes()


def load_hrc(name):
    text = (EXT / "hrc/raw" / name).read_text()
    rows = [r for r in csv.reader(io.StringIO(text)) if r]
    classes = [h.strip() for h in rows[0][1:]]
    data = np.array([[float(x) for x in r] for r in rows[1:]])
    return classes, data[:, 0], data[:, 1:]


hrc = {}
for side in ("push", "call"):
    classes, stacks, probs = load_hrc(f"holdemresources_hu_{side}.csv")
    hrc[side] = (classes, stacks, probs)
    assert sorted(classes) == sorted(CLASS_NAMES)
    steps = np.unique(np.round(np.diff(stacks), 6))
    levels = np.unique(np.round(probs * 100, 6))
    print(
        f"HRC {side}: {len(classes)} classes (same names as ours), stacks {stacks[0]}-{stacks[-1]}"
        f" step {steps[0]}, {len(stacks)} rows, values {probs.min():.2f}-{probs.max():.2f}"
        f" in steps of {0.01 if np.allclose(levels, np.round(levels)) else '?'}"
    )

mixed_max = {}
for side, (classes, stacks, probs) in hrc.items():
    rows = (stacks >= 2) & (stacks <= 20 + 1e-9)
    mixed = (probs[rows] > 0.01) & (probs[rows] < 0.99)
    mixed_max[side] = int(mixed.sum(axis=1).max())
print(
    "HRC mixed classes (0.01 < p < 0.99) at 2-20 bb:"
    f" push at most {mixed_max['push']} per depth, call at most {mixed_max['call']}"
)
print("HRC every class pushes at 1 bb:", bool((hrc["push"][2][0] >= 0.99).all()))

# Chart thresholds from the public page: the class plays at stacks up to and
# including the threshold, with the listed gaps. The raw data was recalculated
# later than the chart, so a 0.05 bb difference counts as agreement.
CHART = {
    "push": {"T3s": [7.7], "32o": [1.4], "72o": [1.6], "63s": [2.3, 5.1, 7.1],
             "53s": [2.4, 3.8, 12.9], "43s": [2.2, 4.9, 10.0]},
    "call": {"Q2o": [5.6], "K2o": [8.1], "22": [15.0], "A2o": [15.8]},
}
def chart_edges(stacks, probs, classes, name, gapped):
    """Last stack the class plays at (p >= 0.5) up to 20 bb. For a gapped class,
    also the end of its first region and the start of its second."""
    keep = stacks <= 20 + 1e-9
    s, col = stacks[keep], probs[keep, classes.index(name)] >= 0.5
    last = float(s[np.flatnonzero(col)[-1]])
    if not gapped:
        return [last]
    stop = np.flatnonzero(~col)[0]
    restart = stop + np.flatnonzero(col[stop:])[0]
    return [float(s[stop - 1]), float(s[restart]), last]


agree = 0
for side, chart in CHART.items():
    classes, stacks, probs = hrc[side]
    for name, edges in chart.items():
        raw_edges = chart_edges(stacks, probs, classes, name, gapped=len(edges) == 3)
        ok = all(abs(a - b) <= 0.05 + 1e-9 for a, b in zip(raw_edges, edges, strict=True))
        agree += ok
        if not ok:
            print(f"  HRC {side} {name}: raw {raw_edges} vs chart {edges}")
total = sum(len(c) for c in CHART.values())
names = ", ".join(CHART["push"]) + " push; " + ", ".join(CHART["call"]) + " call"
print(f"HRC vs chart: {agree}/{total} spot checks agree ({names})")

# b-inary's table: bincode Vec<u32>, an 8-byte length then little-endian u32s.
raw = (EXT / "b-inary/heads_up_pre_flop_equity.bin").read_bytes()
n = int.from_bytes(raw[:8], "little")
table = np.frombuffer(raw, dtype="<u4", offset=8)
assert n == table.size == 1326 * 1326


def their_index(combo):
    hi, lo = combo  # ours: (high id, low id); theirs: (i < j) in lexicographic order
    return (103 - lo) * lo // 2 + (hi - lo - 1)


perm = np.array([their_index(c) for c in ALL_COMBOS])
assert sorted(perm) == list(range(1326))
T = table.reshape(1326, 1326).astype(np.int64)[np.ix_(perm, perm)]
disjoint = _static()["disjoint"]
assert (T[~disjoint] == 0).all()
assert ((T + T.T)[disjoint] == 2 * BOARDS).all()
print("b-inary table: 1326x1326 u32, conflicting pairs 0, T + T' = 2*C(48,5) on every disjoint pair")

rng = np.random.default_rng(20261114)
pos = {c: k for k, c in enumerate(ALL_COMBOS)}
pairs = [(parse_cards("AsAh"), parse_cards("KdKc"))]
while len(pairs) < 8:
    a, b = rng.choice(1326, size=2, replace=False)
    if disjoint[a, b]:
        pairs.append((ALL_COMBOS[a], ALL_COMBOS[b]))
same = 0
for h, v in pairs:
    h, v = tuple(sorted(h, reverse=True)), tuple(sorted(v, reverse=True))
    e = hand_vs_hand(h, v)
    same += round(BOARDS * (2 * e.win + e.tie)) == T[pos[h], pos[v]]
print(f"b-inary vs our exact enumeration: {same}/{len(pairs)} identical integers (2*wins + ties)")

starts = _static()["starts"]
num = np.add.reduceat(np.add.reduceat(np.where(disjoint, T, 0), starts, axis=0), starts, axis=1)
cnt = np.add.reduceat(np.add.reduceat(disjoint.astype(np.int64), starts, axis=0), starts, axis=1)
E = num / (2 * BOARDS * cnt)
print("b-inary class pair counts identical to ours:", bool((cnt == exact_pair_counts()).all()))
cells = [("AA", "KK"), ("AKs", "QQ"), ("T9s", "AKo")]
print("exact " + ", ".join(f"{r} vs {c} {E[class_index(r), class_index(c)]:.6f}" for r, c in cells))

M = PreflopMatrix.load("data/preflop_169.npz")
iu = np.triu_indices(169, 1)
err = (M.equity - E)[iu]
z = err / M.se[iu]
w = int(np.argmax(np.abs(z)))
i, j = iu[0][w], iu[1][w]
print(f"our matrix vs exact, {z.size} unique off-diagonal cells:")
print(
    f"  max |error| {np.abs(err).max():.5f} ({CLASS_NAMES[i]} vs {CLASS_NAMES[j]}:"
    f" {M.equity[i, j]:.5f} +- {M.se[i, j]:.5f} vs {E[i, j]:.5f}), mean |error| {np.abs(err).mean():.5f}"
)
print(
    f"  z mean {z.mean():+.4f}, sd {z.std():.3f}, within 2 SE {(np.abs(z) <= 2).mean():.4f},"
    f" within 3 SE {(np.abs(z) <= 3).mean():.4f}, max |z| {np.abs(z).max():.2f}"
)
