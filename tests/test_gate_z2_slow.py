"""Gate Z2, bars 2 and 3 (DECISIONS 64): Gate Z's directions and PokerStrategy chart at the
fixed model. Run with -s to see the report."""

import os
from concurrent.futures import ProcessPoolExecutor

import pytest
from test_gate_z_slow import AGREEMENT, ANTES, CHART, MIN_CHART, MIN_PAIR, OPENERS, SPOTS, vs_open

from showdown import sixmax as S
from showdown.equity.cards import CLASS_NAMES, class_index

pytestmark = pytest.mark.slow


def _chart(job: tuple) -> tuple:
    """Gate Z's chart rows, at the module's defaults (the fixed model)."""
    hero, seat, size, ante, kind = job
    spot = S.OpenSpot(hero, S.opener(seat, kind), size, ante)
    rows = []
    for a in S.chart(spot, S.load_profiles()["standard"]):
        kinds = {S.kind(a.best)} | {S.kind(w) for _, _, w in a.flips}
        if a.tier == "review":
            kinds.add(S.kind(a.runner_up))
        rows.append((S.kind(a.best), len(kinds) == 1))
    return job, rows


@pytest.fixture(scope="module")
def charts() -> dict:
    jobs = [(h, s, 2.5, ante, k) for h, s in SPOTS for ante in ANTES for k in OPENERS]
    jobs += [(h, s, 3.0, 0.0, "standard") for h, s in CHART]
    with ProcessPoolExecutor(max_workers=min(12, os.cpu_count() or 1)) as pool:
        return dict(pool.map(_chart, jobs))


@pytest.mark.parametrize("loose", ["lag", "maniac"])
def test_bar2_fold_more_and_3bet_less_against_a_nit(charts, loose) -> None:
    compared, bad, nit_raises, loose_raises = 0, [], 0, 0
    for hero, seat in SPOTS:
        for ante in ANTES:
            t, lo = charts[(hero, seat, 2.5, ante, "nit")], charts[(hero, seat, 2.5, ante, loose)]
            for c in range(169):
                if not (t[c][1] and lo[c][1]):
                    continue
                compared += 1
                nit_raises += t[c][0] == "raise"
                loose_raises += lo[c][0] == "raise"
                if t[c][0] != "fold" and lo[c][0] == "fold":
                    bad.append((hero, seat, ante, CLASS_NAMES[c]))
    print(
        f"\nbar 2, Nit vs {loose}: {compared} compared; violations {bad}; 3-bets or jams "
        f"Nit {nit_raises}, {loose} {loose_raises}"
    )
    assert compared >= MIN_PAIR and not bad and nit_raises <= loose_raises


def test_bar3_against_pokerstrategy(charts) -> None:
    compared = agree = agree3 = 0
    disagree, per_spot = [], {}
    for (hero, seat), (lesson, name) in CHART.items():
        theirs = vs_open(lesson, name)
        ours = charts[(hero, seat, 3.0, 0.0, "standard")]
        n = ok = 0
        for c in range(169):
            cls = CLASS_NAMES[c]
            if not ours[c][1] or cls not in theirs:
                continue
            n += 1
            same = (ours[c][0] != "fold") == (theirs[cls] != "fold")
            ok += same
            agree3 += ours[c][0] == theirs[cls]
            if not same:
                disagree.append((hero, seat, cls, ours[c][0], theirs[cls]))
        per_spot[f"{hero} vs {seat}"] = f"{ok}/{n}"
        compared, agree = compared + n, agree + ok
    share = agree / compared if compared else 0.0
    print(
        f"\nbar 3: {compared} kind-stable compared; continue vs fold {share:.1%}; three-way "
        f"{agree3 / max(compared, 1):.1%}\n  per spot: {per_spot}\n  disagreements: {disagree}"
    )
    assert compared >= MIN_CHART and share >= AGREEMENT


def test_reported_72o_and_3bets(charts) -> None:
    a = S.answer(
        S.OpenSpot("BTN", S.opener("CO"), 3.0), S.load_profiles()["standard"], class_index("72o")
    )
    raises = {
        k: sum(r[0] == "raise" for job, rows in charts.items() if job[4] == k for r in rows)
        for k in OPENERS
    }
    print(
        f"\n(reported) 72o BTN vs CO 3 bb: {dict(zip(a.actions, a.ev.round(2), strict=True))}, "
        f"best {a.best}; classes 3-betting or jamming by opener type (5 spots x 2 antes): {raises}"
    )
