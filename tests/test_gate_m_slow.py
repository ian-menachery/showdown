"""Gate M, bars 2 and 3: the six-max engine over 102 charts (DECISIONS 53).

Bar 2 checks three directions across antes, limpers and profiles. Bar 3 compares unopened
pots with PokerStrategy's six-max opening ranges. Classes that are close or review in
either chart compared are left out and counted. Run with -s to see the report.
"""

import os
import re
from concurrent.futures import ProcessPoolExecutor

import pytest
from external_data import require

from showdown import sixmax as S
from showdown.equity.cards import CLASS_NAMES, RANKS, class_of
from showdown.equity.ranges import parse_range

pytestmark = pytest.mark.slow

PROFILES = ("tight", "regular", "loose-passive")
ANTES = (0.0, 0.5)
SPOTS = [
    (seat, k)
    for seat, most in S.MAX_LIMPERS.items()
    for k in range(1 if seat == "BB" else 0, most + 1)
]
PREMIUMS = ("AA", "KK", "QQ", "AKs", "AKo")
LESSONS = {"UTG": 2253, "HJ": 2254, "CO": 2255, "BTN": 2256, "SB": 2257}
AGREEMENT = 0.85


def _kind(action: str) -> str:
    return "fold" if action == "fold" else ("raise" if " to " in action else "limp")


def _chart(job: tuple) -> tuple:
    """(job, per class (best action, tier, the best raise size, kind stable)). Kind stable:
    every band point's winner, and a review's runner-up, is the same kind as the best.

    The job is (seat, limpers, ante, profile), with an optional fifth item, R for an
    out-of-position raiser, and sixth, the profile the standard profile's limpers come
    from. They default to what Gates M and M2 were scored at: 0.90 (DECISIONS 56) and
    regular (DECISIONS 57)."""
    seat, k, ante, name, *rest = job
    S.R["raise_oop"] = rest[0] if rest else S.GATED_RAISE_OOP
    limpers = rest[1] if len(rest) > 1 else S.GATED_STANDARD_LIMPERS
    rows = []
    for a in S.chart(S.Spot(seat, k, ante), S.load_profiles(standard_limpers=limpers)[name]):
        raises = [i for i, n in enumerate(a.actions) if " to " in n]
        size = a.actions[max(raises, key=lambda i: a.ev[i])].split(" to ")[1]
        kinds = {_kind(a.best)} | {_kind(w) for _, _, w in a.flips}
        if a.tier == "review":
            kinds.add(_kind(a.runner_up))
        rows.append((a.best, a.tier, float(size), len(kinds) == 1))
    return job, rows


@pytest.fixture(scope="module")
def charts() -> dict:
    jobs = [(s, k, ante, p) for s, k in SPOTS for ante in ANTES for p in PROFILES]
    assert len(jobs) == 102
    with ProcessPoolExecutor(max_workers=min(12, os.cpu_count() or 1)) as pool:
        return dict(pool.map(_chart, jobs))


def _clear(*rows) -> bool:
    return all(r[1] == "clear" for r in rows)


def _raise(row) -> bool:
    return " to " in row[0]


def test_bar2_the_ante_widens(charts) -> None:
    compared = excluded = 0
    bad = []
    for s, k in SPOTS:
        for p in PROFILES:
            no_ante, ante = charts[(s, k, 0.0, p)], charts[(s, k, 0.5, p)]
            for c in range(169):
                if not _clear(no_ante[c], ante[c]):
                    excluded += 1
                    continue
                compared += 1
                if no_ante[c][0] != "fold" and ante[c][0] == "fold":
                    bad.append((s, k, p, CLASS_NAMES[c]))
    print(f"\nbar 2, ante: {compared} compared, {excluded} close or review left out; {bad}")
    assert compared > 0
    assert not bad


def test_bar2_more_limpers_no_new_offsuit_isos(charts) -> None:
    steps = [(s, k) for s in ("BTN", "SB", "BB") for k in (1, 2)] + [("CO", 1)]
    offsuit = [c for c in range(169) if CLASS_NAMES[c].endswith("o")]
    compared = excluded = 0
    bad = []
    for s, k in steps:
        for p in PROFILES:
            for ante in ANTES:
                fewer, more = charts[(s, k, ante, p)], charts[(s, k + 1, ante, p)]
                for c in offsuit:
                    if not _clear(fewer[c], more[c]):
                        excluded += 1
                        continue
                    compared += 1
                    if _raise(more[c]) and not _raise(fewer[c]):
                        bad.append((s, k + 1, p, ante, CLASS_NAMES[c], fewer[c][0]))
    print(f"\nbar 2, limpers: {compared} compared, {excluded} left out; {bad}")
    assert compared > 0
    assert not bad


def test_bar2_looser_limpers_larger_isos(charts) -> None:
    spots = [("HJ", 1), ("CO", 1), ("CO", 2), ("BTN", 1), ("BTN", 2), ("BTN", 3)]
    compared = excluded = 0
    bad, sizes = [], []
    for s, k in spots:
        for ante in ANTES:
            tight, loose = charts[(s, k, ante, "tight")], charts[(s, k, ante, "loose-passive")]
            for hand in PREMIUMS:
                c = S.class_index(hand)
                sizes.append((s, k, ante, hand, tight[c][2], loose[c][2]))
                if not _clear(tight[c], loose[c]):
                    excluded += 1
                    continue
                compared += 1
                if loose[c][2] < tight[c][2]:
                    bad.append((s, k, ante, hand, tight[c][2], loose[c][2]))
    print(f"\nbar 2, sizes: {compared} compared, {excluded} left out; {bad}")
    print("  (seat, k, ante, hand, best size vs tight, vs loose-passive):")
    for row in sizes:
        print(f"  {row}")
    assert compared > 0
    assert not bad


def test_reported_iso_width_by_profile(charts) -> None:
    """Not gated: how many classes isolate against each profile."""
    print("\nisolating classes (best action a raise), tight / regular / loose-passive:")
    for s, k in SPOTS:
        if k == 0:
            continue
        for ante in ANTES:
            counts = [sum(_raise(r) for r in charts[(s, k, ante, p)]) for p in PROFILES]
            print(f"  {s} k={k} ante {ante:g}: {counts}")


def _connectors(listing: str) -> str:
    """Read "65s+" as the suited connectors 65s up to AKs."""

    def expand(m: re.Match) -> str:
        hi, lo = RANKS.index(m.group(1)), RANKS.index(m.group(2))
        if hi - lo != 1:
            return m.group(0)
        return ", ".join(f"{RANKS[h]}{RANKS[h - 1]}s" for h in range(hi, 13))

    return re.sub(r"\b([2-9TJQKA])([2-9TJQKA])s\+", expand, listing)


def chart_range(lesson: int) -> set[str]:
    text = require(f"pokerstrategy/bss-{lesson}.html").read_text("utf-8", errors="replace")
    m = re.search(
        r"Range:\s*</strong>\s*<br>\s*([^<(]+?)\s*\((?:#(\d+) / \d+%|\d+%, #(\d+))\)", text
    )
    listing, count = m.group(1), int(m.group(2) or m.group(3))
    combos = parse_range(listing)
    if len(combos) != count:
        combos = parse_range(_connectors(listing))
    assert len(combos) == count, (lesson, listing)
    return {CLASS_NAMES[class_of(c)] for c in combos}


@pytest.mark.xfail(
    strict=True,
    reason="Gate M bar 3 FAIL (GATES.md, 2026-11-22): HJ 50% of 6 clear classes and SB 65.2% "
    "of 23; the fitted regular blinds fold more than the chart's opponents, so the engine opens "
    "wider. The bar is unchanged; strict, so a pass shows up.",
)
def test_bar3_unopened_against_pokerstrategy(charts) -> None:
    failed = []
    for seat, lesson in LESSONS.items():
        opens = chart_range(lesson)
        ours = charts[(seat, 0, 0.0, "regular")]
        clear = [c for c in range(169) if ours[c][1] == "clear"]
        disagree = [
            (CLASS_NAMES[c], ours[c][0])
            for c in clear
            if _raise(ours[c]) != (CLASS_NAMES[c] in opens)
        ]
        share = 1 - len(disagree) / len(clear)
        print(
            f"\nbar 3, {seat} (lesson {lesson}, {len(opens)} classes open): {len(clear)} clear "
            f"compared, {169 - len(clear)} close or review left out; agreement {share:.1%}"
        )
        print(f"  disagreements (ours): {disagree}")
        if share < AGREEMENT:
            failed.append(seat)
    assert not failed


def test_reported_after_scoring_tiers_and_kind_stable_agreement(charts) -> None:
    """Not a bar; added after Gate M was scored (GATES.md). Per unopened regular chart: the
    tier counts, and bar 3's raise-or-not agreement on every class whose kind of action
    (fold, limp, raise) is the same at all band points, sizes aside."""
    for seat, lesson in LESSONS.items():
        opens = chart_range(lesson)
        ours = charts[(seat, 0, 0.0, "regular")]
        tiers = {t: sum(r[1] == t for r in ours) for t in ("clear", "close", "review")}
        size_only = sum(r[1] == "close" and r[3] for r in ours)
        stable = [c for c in range(169) if ours[c][3]]
        disagree = [
            (CLASS_NAMES[c], ours[c][0])
            for c in stable
            if _raise(ours[c]) != (CLASS_NAMES[c] in opens)
        ]
        print(
            f"\n{seat}: {tiers}, of the close {size_only} size only; kind stable {len(stable)}, "
            f"agreement {1 - len(disagree) / len(stable):.1%}; ours vs chart: {disagree}"
        )
    totals = {
        t: sum(r[1] == t for rows in charts.values() for r in rows)
        for t in ("clear", "close", "review")
    }
    size_only = sum(r[1] == "close" and r[3] for rows in charts.values() for r in rows)
    print(f"\nall 102 charts: {totals}, of the close {size_only} size only")
