"""Gate Z, bars 2 and 3 (DECISIONS 61): directions against opener types, and PokerStrategy's
vs-open ranges (lessons 2256 and 2257, saved under DECISIONS 53, never committed). Run with
-s to see the report.
"""

import html
import os
import re
import time
from concurrent.futures import ProcessPoolExecutor

import pytest
from external_data import require
from test_gate_m_slow import _connectors

from showdown import sixmax as S
from showdown.equity.cards import CLASS_NAMES, RANKS
from showdown.equity.ranges import parse_range

pytestmark = pytest.mark.slow

ANTES = (0.0, 0.5)
SPOTS = (("BTN", "CO"), ("BB", "CO"), ("SB", "BTN"), ("BB", "BTN"), ("BB", "UTG"))
"""(hero, opener) for bar 2."""
OPENERS = ("nit", "lag", "maniac")
MIN_PAIR, MIN_CHART, AGREEMENT = 100, 100, 0.85
CHART = {
    ("BTN", "UTG"): (2256, "UTG"),
    ("BTN", "HJ"): (2256, "MP"),
    ("BTN", "CO"): (2256, "the cut off"),
    ("SB", "UTG"): (2257, "UTG"),
    ("SB", "HJ"): (2257, "MP"),
    ("SB", "CO"): (2257, "the cut off"),
    ("SB", "BTN"): (2257, "the button"),
}


def _chart(job: tuple) -> tuple:
    """(job, per class (best kind, kind stable)), call its own kind."""
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
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=min(12, os.cpu_count() or 1)) as pool:
        out = dict(pool.map(_chart, jobs))
    print(f"\n(reported) {len(jobs)} charts in {time.perf_counter() - start:.0f} s")
    return out


def _pairs(charts, tight: str, loose: str) -> tuple[int, list, int, int]:
    compared, bad, raises_tight, raises_loose = 0, [], 0, 0
    for hero, seat in SPOTS:
        for ante in ANTES:
            t = charts[(hero, seat, 2.5, ante, tight)]
            lo = charts[(hero, seat, 2.5, ante, loose)]
            for c in range(169):
                if not (t[c][1] and lo[c][1]):
                    continue
                compared += 1
                raises_tight += t[c][0] == "raise"
                raises_loose += lo[c][0] == "raise"
                if t[c][0] != "fold" and lo[c][0] == "fold":
                    bad.append((hero, seat, ante, CLASS_NAMES[c]))
    return compared, bad, raises_tight, raises_loose


@pytest.mark.parametrize("loose", ["lag", "maniac"])
def test_bar2_fold_more_and_3bet_less_against_a_nit(charts, loose) -> None:
    compared, bad, nit_raises, loose_raises = _pairs(charts, "nit", loose)
    print(
        f"\nbar 2, Nit vs {loose} opener: {compared} compared (at least {MIN_PAIR}); "
        f"continues vs Nit but folds vs {loose}: {bad}; 3-bets or jams: Nit {nit_raises}, "
        f"{loose} {loose_raises}"
    )
    assert compared >= MIN_PAIR
    assert not bad
    assert nit_raises <= loose_raises


def test_reported_opener_widths() -> None:
    widths = {k: {s: round(S.opener(s, k).width, 3) for s in S.OPEN_WIDTH} for k in S.TYPE_KEYS}
    print(f"\n(reported) opener widths: {widths}")


# --- bar 3: PokerStrategy's vs-open ranges ---------------------------------------------


def _text(lesson: int) -> str:
    raw = require(f"pokerstrategy/bss-{lesson}.html").read_text("utf-8", errors="replace")
    raw = re.sub(r"<script.*?</script>|<style.*?</style>", "", raw, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def _spans(listing: str) -> str:
    """Read "JTs-98s" as the suited connectors 98s to JTs; a bare "KQ" as KQs and KQo."""

    def expand(m: re.Match) -> str:
        a, b, c, d = (RANKS.index(g) for g in m.groups())
        if a - b != 1 or c - d != 1 or a == c:
            return m.group(0)
        return ", ".join(f"{RANKS[h]}{RANKS[h - 1]}s" for h in range(min(a, c), max(a, c) + 1))

    listing = re.sub(r"\b([2-9TJQKA])([2-9TJQKA])s-([2-9TJQKA])([2-9TJQKA])s\b", expand, listing)
    return re.sub(r"\b([2-9TJQKA])(?!\1)([2-9TJQKA])\b(?![so+-])", r"\1\2s, \1\2o", listing)


def _combos(listing: str, count: int) -> set:
    """The list's combos, read as DECISIONS 53 reads the pages: where a token reads two
    ways, the reading whose count equals the page's. The count must match."""
    combos = set(parse_range(_spans(listing)))
    if len(combos) != count:
        combos = set(parse_range(_connectors(_spans(listing))))
    assert len(combos) == count, (listing, len(combos), count)
    return combos


def vs_open(lesson: int, opener: str) -> dict[str, str]:
    """Per class, the chart's action against that opener: fold, call or 3-bet by most
    combos; classes split evenly are left out."""
    text = _text(lesson)
    start = text.index(f"Against an open raise from {opener} ")
    section = text[start : text.find("Against", start + 10)]
    found = re.findall(
        r"(Full range|Defending range|Call|3-Bet/Fold|3-Bet/5-Bet): ([^(]+?) \((?:\d+%, )?#(\d+)\)",
        section,
    )
    lists = {name: _combos(listing, int(n)) for name, listing, n in found}
    defend = lists.get("Full range") or lists["Defending range"]
    call = lists["Call"]
    three = lists["3-Bet/Fold"] | lists["3-Bet/5-Bet"]
    assert call | three == defend and not call & three
    out = {}
    for c in range(169):
        combos = [x for x in parse_range(CLASS_NAMES[c])]
        votes = {
            "call": sum(x in call for x in combos),
            "raise": sum(x in three for x in combos),
        }
        votes["fold"] = len(combos) - votes["call"] - votes["raise"]
        ranked = sorted(votes.values(), reverse=True)
        if ranked[0] > ranked[1]:
            out[CLASS_NAMES[c]] = max(votes, key=votes.get)
    return out


def test_bar3_against_pokerstrategy(charts) -> None:
    compared = agree = agree3 = 0
    disagree = []
    per_spot = {}
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
        compared += n
        agree += ok
    share = agree / compared if compared else 0.0
    print(
        f"\nbar 3: {compared} kind-stable compared (at least {MIN_CHART}); continue vs fold "
        f"agreement {share:.1%} (at least {AGREEMENT:.0%}); three-way {agree3 / max(compared, 1):.1%}"
    )
    print(f"  per spot: {per_spot}")
    print(f"  disagreements (ours, theirs): {disagree}")
    assert compared >= MIN_CHART
    assert share >= AGREEMENT
