"""Gate M2, bars 2 and 3: the "standard" profile over its 34 charts (DECISIONS 54).

Only kind-stable classes count: at all 9 band points the winner is the same kind of action
(fold, limp or raise) as the best, and for a review the runner-up is too. Run with -s to
see the report.
"""

import os
from concurrent.futures import ProcessPoolExecutor

import pytest
from test_gate_m_slow import ANTES, LESSONS, SPOTS, _chart, _raise, chart_range

from showdown.equity.cards import CLASS_NAMES

pytestmark = pytest.mark.slow

AGREEMENT = 0.85
MIN_ANTE, MIN_LIMPERS, MIN_SEAT = 100, 50, 30


@pytest.fixture(scope="module")
def charts() -> dict:
    jobs = [(s, k, ante, "standard") for s, k in SPOTS for ante in ANTES]
    assert len(jobs) == 34
    with ProcessPoolExecutor(max_workers=min(12, os.cpu_count() or 1)) as pool:
        return dict(pool.map(_chart, jobs))


def _stable(*rows) -> bool:
    return all(r[3] for r in rows)


def test_bar2_the_ante_widens(charts) -> None:
    compared, bad = 0, []
    for s, k in SPOTS:
        no_ante, ante = charts[(s, k, 0.0, "standard")], charts[(s, k, 0.5, "standard")]
        for c in range(169):
            if not _stable(no_ante[c], ante[c]):
                continue
            compared += 1
            if no_ante[c][0] != "fold" and ante[c][0] == "fold":
                bad.append((s, k, CLASS_NAMES[c]))
    print(f"\nbar 2, ante: {compared} kind-stable compared (at least {MIN_ANTE}); {bad}")
    assert compared >= MIN_ANTE
    assert not bad


def test_bar2_more_limpers_no_new_offsuit_isos(charts) -> None:
    steps = [(s, k) for s in ("BTN", "SB", "BB") for k in (1, 2)] + [("CO", 1)]
    offsuit = [c for c in range(169) if CLASS_NAMES[c].endswith("o")]
    compared, bad = 0, []
    for s, k in steps:
        for ante in ANTES:
            fewer, more = charts[(s, k, ante, "standard")], charts[(s, k + 1, ante, "standard")]
            for c in offsuit:
                if not _stable(fewer[c], more[c]):
                    continue
                compared += 1
                if _raise(more[c]) and not _raise(fewer[c]):
                    bad.append((s, k + 1, ante, CLASS_NAMES[c], fewer[c][0]))
    print(f"\nbar 2, limpers: {compared} kind-stable compared (at least {MIN_LIMPERS}); {bad}")
    assert compared >= MIN_LIMPERS
    assert not bad


def test_bar3_unopened_against_pokerstrategy(charts) -> None:
    failed = []
    for seat, lesson in LESSONS.items():
        opens = chart_range(lesson)
        ours = charts[(seat, 0, 0.0, "standard")]
        stable = [c for c in range(169) if ours[c][3]]
        clear = [c for c in range(169) if ours[c][1] == "clear"]

        def misses(classes, ours=ours, opens=opens):
            return [
                (CLASS_NAMES[c], ours[c][0])
                for c in classes
                if _raise(ours[c]) != (CLASS_NAMES[c] in opens)
            ]

        disagree = misses(stable)
        share = 1 - len(disagree) / len(stable) if stable else 0.0
        clear_share = 1 - len(misses(clear)) / len(clear) if clear else float("nan")
        opened = sum(_raise(r) for r in ours)
        print(
            f"\nbar 3, {seat}: {len(stable)} kind-stable compared, agreement {share:.1%} "
            f"(clear only: {len(clear)}, {clear_share:.1%}); ours opens {opened} classes, "
            f"the chart {len(opens)}"
        )
        print(f"  disagreements (ours): {disagree}")
        if len(stable) < MIN_SEAT or share < AGREEMENT:
            failed.append(seat)
    assert not failed
