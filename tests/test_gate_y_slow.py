"""Gate Y, bars 1 to 3 (DECISIONS 60): the grade rule and the band floor on a scripted drill
session with player types, and the type directions on charts. Run with -s to see the report.
"""

import json
import os
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import numpy as np
import pytest

from showdown import sixmax as S
from showdown import sixmax_drill as D
from showdown.equity.cards import CLASS_NAMES, class_index

pytestmark = pytest.mark.slow

SEED, DRILLS, CHOICE_SEED = 20261127, 300, 7
MIN_LABEL, MIN_FLOORED, MIN_COMPARED = 5, 10, 50
CUTS = ((3.0, "Correct"), (10.0, "Inaccuracy"), (25.0, "Wrong"))


def _reply(action: str) -> str:
    if action == "fold":
        return "f"
    return action.split(" to ")[1] if " to " in action else "l"


@pytest.fixture(scope="module")
def session(tmp_path_factory) -> tuple[list[dict], dict]:
    trainer = D.Trainer(S.load_profiles()["standard"], seed=SEED, types=True)
    pick = random.Random(CHOICE_SEED)

    def ask(prompt: str) -> str:
        return _reply(pick.choice(trainer.last.answer.actions))

    log = tmp_path_factory.mktemp("drills")
    summary = D.run(trainer, DRILLS, log_dir=log, ask=ask, show=lambda s: None)
    with open(summary["log"], encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    return rows, summary


def _expected(row: dict) -> tuple:
    """DECISIONS 60's rule, worked here from a fresh answer: (label, bb lost, % lost, the
    answer wins at a band point, it is not the base best)."""
    spot = S.Spot(row["seat"], row["limpers"], row["ante"])
    profile = S.compose(row["limpers_type"], row["table_type"])
    a = S.answer(spot, profile, class_index(row["class"]))
    ev = dict(zip(a.actions, (float(e) for e in a.ev), strict=True))
    act, best = row["action"], a.best
    lost = ev[best] - ev[act]
    pct = 100.0 * lost / spot.pot
    winners = {w for _, _, w in a.flips}
    size_only = winners and all(S.kind(w) == S.kind(best) for w in winners)
    if lost <= 1e-9 or (size_only and S.kind(act) == S.kind(best)):
        label = "Best"
    elif act in winners:
        label = "Correct"
    else:
        label = next((name for cut, name in CUTS if pct <= cut), "Blunder")
    return label, lost, pct, act in winners, act != best


@pytest.fixture(scope="module")
def expected(session) -> list[tuple]:
    rows, _ = session
    with ProcessPoolExecutor(max_workers=min(12, os.cpu_count() or 1)) as pool:
        return list(pool.map(_expected, rows))


def test_bar1_the_grade_rule(session, expected) -> None:
    rows, summary = session
    assert len(rows) == summary["drills"] == DRILLS
    wrong = [
        (r["seat"], r["limpers"], r["class"], r["action"], r["grade"], e[0])
        for r, e in zip(rows, expected, strict=True)
        if r["grade"] != e[0]
    ]
    off = max(abs(r["bb_lost"] - e[1]) for r, e in zip(rows, expected, strict=True))
    off_pct = max(abs(r["pct_lost"] - e[2]) for r, e in zip(rows, expected, strict=True))
    counts = {label: sum(r["grade"] == label for r in rows) for label in S.LABELS}
    by_tier = {
        t: {label: sum(r["grade"] == label and r["tier"] == t for r in rows) for label in S.LABELS}
        for t in ("clear", "close", "review")
    }
    print(f"\nbar 1: labels {counts}; mismatches {wrong}; worst bb gap {off:.2e}, % {off_pct:.2e}")
    print(f"  (reported) labels by tier: {by_tier}")
    assert not wrong
    assert off < 1e-9 and off_pct < 1e-7
    assert all(n >= MIN_LABEL for n in counts.values())
    assert summary["grades"] == counts
    assert abs(summary["bb_lost"] - sum(r["bb_lost"] for r in rows)) < 1e-9


def test_bar2_the_band_floor(session, expected) -> None:
    rows, _ = session
    floored = [(r, e) for r, e in zip(rows, expected, strict=True) if e[3]]
    below = [
        (r["class"], r["action"], r["grade"])
        for r, _ in floored
        if r["grade"] not in ("Best", "Correct")
    ]
    not_best = sum(e[4] for _, e in floored)
    print(
        f"\nbar 2: {len(floored)} answers win at a band point, {not_best} not the base best; below Correct: {below}"
    )
    assert not below
    assert not_best >= MIN_FLOORED


def test_reported_speed(session) -> None:
    rows, _ = session
    seconds = np.array([r["seconds"] for r in rows])
    print(
        f"\n(reported) drill speed with types: median {np.median(seconds):.2f} s, "
        f"95th percentile {np.percentile(seconds, 95):.2f} s, max {seconds.max():.2f} s"
    )


# --- bar 3: type directions --------------------------------------------------------

ANTES = (0.0, 0.5)
STEAL_SEATS = ("CO", "BTN", "SB")
STEAL_PAIRS = (("nit", "lag"), ("weak-tight", "station"))
ISO_SPOTS = (("CO", 1), ("BTN", 1), ("BTN", 2))
FITTED = S.TYPE_KEYS[1:]


def _chart(job: tuple) -> tuple:
    """(job, per class (best kind, kind stable)). Kind stable: every band point's winner,
    and a review's runner-up, is the same kind as the best (DECISIONS 54)."""
    seat, k, ante, limpers, table, lower = job
    profile = S.compose(limpers, table)
    if lower:
        profile = replace(profile, iso_fold=max(0.0, profile.iso_fold - 0.10))
    rows = []
    for a in S.chart(S.Spot(seat, k, ante), profile):
        kinds = {S.kind(a.best)} | {S.kind(w) for _, _, w in a.flips}
        if a.tier == "review":
            kinds.add(S.kind(a.runner_up))
        rows.append((S.kind(a.best), len(kinds) == 1))
    return job, rows


@pytest.fixture(scope="module")
def charts() -> dict:
    tables = sorted({t for pair in STEAL_PAIRS for t in pair})
    jobs = [
        (s, 0, ante, "standard", t, False) for s in STEAL_SEATS for ante in ANTES for t in tables
    ]
    jobs += [
        (s, k, ante, lt, "standard", lower)
        for s, k in ISO_SPOTS
        for ante in ANTES
        for lt in FITTED
        for lower in (False, True)
    ]
    with ProcessPoolExecutor(max_workers=min(12, os.cpu_count() or 1)) as pool:
        return dict(pool.map(_chart, jobs))


def test_bar3_steals_widen_against_tighter_blinds(charts) -> None:
    for tight, loose in STEAL_PAIRS:
        compared, bad, raises = 0, [], {tight: 0, loose: 0}
        for s in STEAL_SEATS:
            for ante in ANTES:
                t = charts[(s, 0, ante, "standard", tight, False)]
                lo = charts[(s, 0, ante, "standard", loose, False)]
                for c in range(169):
                    if not (t[c][1] and lo[c][1]):
                        continue
                    compared += 1
                    raises[tight] += t[c][0] == "raise"
                    raises[loose] += lo[c][0] == "raise"
                    if lo[c][0] == "raise" and t[c][0] != "raise":
                        bad.append((s, ante, CLASS_NAMES[c]))
        print(
            f"\nbar 3, steals {tight} vs {loose} tables: {compared} compared (at least "
            f"{MIN_COMPARED}); raises {raises}; violations {bad}"
        )
        assert compared >= MIN_COMPARED
        assert not bad
        assert raises[tight] >= raises[loose]


def test_bar3_no_new_offsuit_isos_when_limpers_fold_less(charts) -> None:
    offsuit = [c for c in range(169) if CLASS_NAMES[c].endswith("o")]
    compared, bad = 0, []
    isos = {}
    for s, k in ISO_SPOTS:
        for ante in ANTES:
            for lt in FITTED:
                base = charts[(s, k, ante, lt, "standard", False)]
                lower = charts[(s, k, ante, lt, "standard", True)]
                isos[(s, k, ante, lt)] = sum(base[c][0] == "raise" for c in range(169))
                for c in offsuit:
                    if not (base[c][1] and lower[c][1]):
                        continue
                    compared += 1
                    if lower[c][0] == "raise" and base[c][0] != "raise":
                        bad.append((s, k, ante, lt, CLASS_NAMES[c]))
    print(f"\nbar 3, isos: {compared} offsuit compared (at least {MIN_COMPARED}); violations {bad}")
    print(f"  (reported) classes isolated, standard table: {isos}")
    assert compared >= MIN_COMPARED
    assert not bad
