"""Gate W, bars 2 and 3: six-max hand review against fresh answers and on the 10,000 Pluribus
hands (DECISIONS 58). Run with -s to see the report.
"""

import os
import random
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import pytest
from external_data import require_pluribus
from test_gate_w import FIXTURE

from showdown import sixmax as S
from showdown import sixmax_review as V
from showdown.equity.cards import class_index
from showdown.hh.parse import load

pytestmark = pytest.mark.slow

SEED, SAMPLED, MIN_GRADED = 20261122, 300, 2_000


def _reviewed(paths, player: str) -> tuple:
    start = time.perf_counter()
    parsed = load(paths)
    decisions = V.review(parsed.records, player, S.load_profiles()["standard"])
    return parsed, decisions, time.perf_counter() - start


@pytest.fixture(scope="module")
def fixture_hands() -> tuple:
    return _reviewed([FIXTURE], "Hero")


@pytest.fixture(scope="module")
def pluribus() -> tuple:
    return _reviewed([require_pluribus()], "Pluribus")


def _expected(d: V.Decision) -> tuple:
    """DECISIONS 55's rule, worked here from a fresh answer: (grade, bb lost, best, tier)."""
    spot = S.Spot(d.seat, d.limpers, d.ante)
    a = S.answer(spot, S.load_profiles()["standard"], class_index(d.hand))
    ev = dict(zip(a.actions, a.ev, strict=True))
    lost = float(ev[a.best] - max(ev[n] for n in a.actions if S.kind(n) == d.kind))
    if d.kind == S.kind(a.best):
        g = "good"
    elif any(S.kind(w) == d.kind for _, _, w in a.flips):
        g = "marginal"
    else:
        g = "review"
    return g, lost, a.best, a.tier


def test_bar2_grades_equal_fresh_answers(fixture_hands, pluribus) -> None:
    graded = [d for d in fixture_hands[1] if d.cause is None]
    sample = random.Random(SEED).sample([d for d in pluribus[1] if d.cause is None], SAMPLED)
    checked = graded + sample
    with ProcessPoolExecutor(max_workers=min(12, os.cpu_count() or 1)) as pool:
        expected = list(pool.map(_expected, checked))
    bad, worst = [], 0.0
    for d, (g, lost, best, tier) in zip(checked, expected, strict=True):
        worst = max(worst, abs(d.bb_lost - lost))
        if (d.grade, d.best, d.tier) != (g, best, tier) or abs(d.bb_lost - lost) > 1e-9:
            bad.append((d.source, d.grade, g, d.best, best, d.tier, tier, d.bb_lost, lost))
    print(
        f"\nbar 2: {len(graded)} fixture and {len(sample)} Pluribus decisions checked; "
        f"mismatches {bad}; largest bb gap {worst:.2e}"
    )
    assert len(graded) == 33 and len(sample) == SAMPLED
    assert not bad


def test_bar3_pluribus_hands(pluribus) -> None:
    parsed, decisions, seconds = pluribus
    summary = V.summarize(decisions)
    graded = [d for d in decisions if d.cause is None]
    with_player = sum(any(p.name == "Pluribus" for p in r.players) for r in parsed.records)
    print(
        f"\nbar 3: {parsed.parsed} of {parsed.found} hands parse ({len(parsed.failures)} "
        f"failed); Pluribus in {with_player}; graded {len(graded)}; reviewed in {seconds:.0f} s"
    )
    print("\n".join(V.describe(parsed, summary, "Pluribus", "standard")))
    assert parsed.parsed >= 0.99 * parsed.found
    assert len(decisions) == with_player
    assert all(d.cause is None or d.cause in V.CAUSES for d in decisions)
    assert summary["graded"] + sum(summary["skipped"].values()) == with_player
    assert len(graded) >= MIN_GRADED
    for t in V.TIERS:
        for g in V.GRADES:
            assert summary["tiers"][t][g] == sum(d.tier == t and d.grade == g for d in graded)
    assert abs(summary["bb_lost"] - sum(d.bb_lost for d in graded)) <= 1e-9
    clear = sum(d.bb_lost for d in graded if d.tier == "clear")
    assert abs(summary["bb_lost_clear"] - clear) <= 1e-9
    groups = Counter(
        (d.seat, "limped" if d.limpers else "unopened", d.kind, S.kind(d.best))
        for d in graded
        if d.grade == "review"
    )
    assert len(summary["leaks"]) == sum(n >= V.LEAK_MIN for n in groups.values())
    for leak in summary["leaks"]:
        members = [
            d
            for d in graded
            if d.grade == "review"
            and (d.seat, "limped" if d.limpers else "unopened", d.kind, S.kind(d.best))
            == (leak["seat"], leak["pot"], leak["answer"], leak["best"])
        ]
        assert leak["count"] == len(members) >= V.LEAK_MIN
        assert abs(leak["bb_lost"] - sum(d.bb_lost for d in members)) <= 1e-9
