"""Gate W2, bars 2 and 3 (DECISIONS 63): the leak finder's grades against fresh answers on the
fixture, and the report's sums; reported, the new review on the 10,000 Pluribus hands. Run
with -s to see the report.
"""

import os
import time
from concurrent.futures import ProcessPoolExecutor

import pytest
from external_data import require_pluribus
from test_gate_w2 import FIXTURE

from showdown import lessons
from showdown import sixmax as S
from showdown import sixmax_review as V
from showdown.equity.cards import class_index
from showdown.hh.parse import load

pytestmark = pytest.mark.slow

CUTS = ((3.0, "Correct"), (10.0, "Inaccuracy"), (25.0, "Wrong"))


@pytest.fixture(scope="module")
def fixture_review() -> tuple:
    parsed = load([FIXTURE])
    decisions, players = V.review_typed(parsed.records, "Hero")
    return parsed, decisions, players, V.summarize_typed(decisions, players, "Hero")


def _expected(d: V.Decision) -> tuple:
    """DECISIONS 60's rule from a fresh answer: (label, bb lost, best, tier)."""
    if d.family == "open":
        spot = S.OpenSpot(d.seat, S.opener(d.opener, d.opener_type), d.open, d.ante)
        profile = S.compose("standard", d.table_type)
    else:
        spot = S.Spot(d.seat, d.limpers, d.ante)
        profile = S.compose(d.limpers_type, d.table_type)
    a = S.answer(spot, profile, class_index(d.hand))
    ev = dict(zip(a.actions, (float(e) for e in a.ev), strict=True))
    lost = ev[a.best] - ev[d.action]
    pct = 100.0 * lost / spot.pot
    winners = {w for _, _, w in a.flips}
    size_only = bool(winners) and all(S.kind(w) == S.kind(a.best) for w in winners)
    if lost <= 1e-9 or (size_only and S.kind(d.action) == S.kind(a.best)):
        label = "Best"
    elif d.action in winners:
        label = "Correct"
    else:
        label = next((name for cut, name in CUTS if pct <= cut), "Blunder")
    return label, lost, a.best, a.tier


def test_bar2_grades_equal_fresh_answers(fixture_review) -> None:
    _, decisions, _, _ = fixture_review
    graded = [d for d in decisions if d.cause is None]
    with ProcessPoolExecutor(max_workers=min(12, os.cpu_count() or 1)) as pool:
        expected = list(pool.map(_expected, graded))
    wrong = [
        (d.source, d.action, d.grade, d.best, d.tier, e)
        for d, e in zip(graded, expected, strict=True)
        if (d.grade, d.best, d.tier) != (e[0], e[2], e[3])
    ]
    gap = max(abs(d.bb_lost - e[1]) for d, e in zip(graded, expected, strict=True))
    print(f"\nbar 2: {len(graded)} fixture decisions checked; mismatches {wrong}; bb gap {gap:.2e}")
    assert len(graded) >= 40
    assert not wrong and gap < 1e-9


def test_bar3_the_report_sums(fixture_review) -> None:
    _, decisions, _, s = fixture_review
    graded = [d for d in decisions if d.cause is None]
    assert s["graded"] == len(graded) == sum(s["by_family"].values())
    assert sum(s["skipped"].values()) == s["hands"] - s["graded"]
    for label in S.LABELS:
        assert s["grades"][label] == sum(d.grade == label for d in graded)
        assert s["grades"][label] == sum(row[label] for row in s["grades_by_family"].values())
    assert abs(s["bb_lost"] - sum(d.bb_lost for d in graded)) < 1e-9
    for leak in s["leaks"]:
        members = [
            d
            for d in graded
            if d.grade in V.LEAK_LABELS
            and (d.family, d.seat, V.opponent_type(d), S.kind(d.action), S.kind(d.best))
            == (leak["family"], leak["seat"], leak["opponent_type"], leak["answer"], leak["best"])
        ]
        assert leak["count"] == len(members) >= V.LEAK_MIN
        assert abs(leak["bb_lost"] - sum(d.bb_lost for d in members)) < 1e-9
        assert sum(leak["grades"].values()) == leak["count"]
        assert leak["lesson"] in lessons.IDS
    print(
        f"\nbar 3: {s['graded']} graded {s['by_family']}; {s['grades']}; bb {s['bb_lost']:.3f}; "
        f"leaks {[(x['seat'], x['opponent_type'], x['answer'], x['best'], x['count']) for x in s['leaks']]}"
    )


def test_reported_pluribus() -> None:
    start = time.perf_counter()
    parsed = load([require_pluribus()])
    decisions, players = V.review_typed(parsed.records, "Pluribus")
    s = V.summarize_typed(decisions, players, "Pluribus")
    print(
        f"\n(reported) Pluribus: {parsed.parsed} hands parsed, in {s['hands']}; graded "
        f"{s['graded']} {s['by_family']}; skipped {s['skipped']}; {s['grades']}; "
        f"bb lost {s['bb_lost']:.2f}; opponents {s['opponents']}; "
        f"{time.perf_counter() - start:.0f} s"
    )
    for leak in s["leaks"]:
        print(
            f"  leak: {leak['family']} {leak['seat']} vs {leak['opponent_type']}: "
            f"{leak['answer']} for {leak['best']}, {leak['count']} hands, "
            f"{leak['bb_lost']:.2f} bb, lesson {leak['lesson']}"
        )
    assert s["graded"] + sum(s["skipped"].values()) == s["hands"]
