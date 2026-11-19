"""Gate PA bar 3: the 10% ante solve against HoldemResources' "Ante 10%" chart (DECISIONS 48).

The chart gives, per class, the largest effective stack at which it pushes (or calls), at
0.1 bb resolution and capped at "20+". Three pusher cells are starred: those hands push in
two stack ranges, which the footnotes give (e.g. "63s: 8.9 - 4.7, 2.8" pushes at 2.8 bb or
less and from 4.7 to 8.9 bb). Also: 10 bb re-solved from scratch, with and without the ante.
"""

import re
from pathlib import Path

import numpy as np
import pytest
from external_data import require

from showdown import pushfold as pf
from showdown.equity.cards import RANKS, class_index

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]
GRID = RANKS[::-1]  # A first, as on the page
WITHIN = 0.1
"""A class whose chart boundary lies within this of the depth is excluded (the resolution)."""


def chart(tab: str = "ante10") -> dict[str, dict[str, list[tuple[float, float]]]]:
    """{"Pusher"|"Caller": {class: [(low, high), ...] stacks where it plays}} for one tab:
    "ante10", or "regular" (no ante)."""
    text = require("holdemresources/hune.html").read_text(encoding="utf-8")
    start = text.index(f'id="{tab}"')
    section = text[start : text.index('id="ante10"')] if tab == "regular" else text[start:]
    notes = {}
    footnotes = re.search(r'<table class="simple">(.*?)</table>', section, re.S).group(1)
    for stars, hand, high, mid, low in re.findall(
        r"<td>(\*+)</td>\s*<td>(\w+):</td>\s*<td>\s*([\d.]+)\s*-\s*([\d.]+),\s*([\d.]+)</td>",
        footnotes,
    ):
        notes[stars] = (hand, [(0.0, float(low)), (float(mid), float(high))])
    out = {}
    tables = re.findall(r'<table class="table handgrid"[^>]*>(.*?)</table>', section, re.S)
    for table in tables[:2]:
        title = re.search(r'<th colspan="14">([^<]*)</th>', table).group(1)
        ranges = {}
        for row in re.findall(r"<tr>(.*?)</tr>", table, re.S)[2:]:
            r = GRID.index(re.search(r"<th>([^<]*)</th>", row).group(1))
            for c, cell in enumerate(re.findall(r"<td[^>]*>([^<]*)</td>", row)):
                hi, lo = GRID[min(r, c)], GRID[max(r, c)]
                name = hi + lo + ("" if r == c else "s" if c > r else "o")
                cell = cell.strip()
                if cell.startswith("*"):
                    hand, spans = notes[cell]
                    assert hand == name, (cell, hand, name)
                    ranges[name] = spans
                else:
                    ranges[name] = [(0.0, np.inf if cell == "20+" else float(cell))]
        out[title] = ranges
    return out


def reference(spans: dict[str, list[tuple[float, float]]], depth: int) -> np.ndarray:
    """1 where the chart plays at `depth`, 0 where it doesn't, 0.5 (excluded) near a boundary."""
    out = np.zeros(169)
    for name, ranges in spans.items():
        bounds = [b for lo, hi in ranges for b in (lo, hi) if 0 < b < np.inf]
        if any(abs(b - depth) <= WITHIN + 1e-9 for b in bounds):
            out[class_index(name)] = 0.5
        elif any(lo <= depth <= hi for lo, hi in ranges):
            out[class_index(name)] = 1.0
    return out


@pytest.mark.parametrize(
    ("tab", "path"),
    [("ante10", "data/pushfold_ante10.json"), ("regular", "data/pushfold.json")],
    ids=["bar3-ante10", "parser-check-no-ante"],
)
def test_matches_holdemresources_chart(tab, path) -> None:
    """Bar 3 on the ante tab. The no-ante tab against Gate D's solve checks the parsing and
    the comparison rule; it is not a bar."""
    ref = chart(tab)
    assert sorted(ref) == ["Caller", "Pusher"] and all(len(v) == 169 for v in ref.values())
    solution = pf.PushFoldSolution.load(ROOT / path)
    rows = []
    print(f"\n{tab}:")
    for depth in pf.DEPTHS:
        d = solution.at(depth)
        push = pf.compare(d.push, reference(ref["Pusher"], depth))
        call = pf.compare(d.call, reference(ref["Caller"], depth))
        rows.append((depth, push, call))
        print(
            f"{depth:>2} bb  push {push.agree}/{push.compared} ({push.excluded} excl) "
            f"{push.disagree}  call {call.agree}/{call.compared} ({call.excluded} excl) "
            f"{call.disagree}"
        )
    for depth, push, call in rows:
        assert push.passed and call.passed, (depth, push.disagree, call.disagree)


@pytest.mark.parametrize(
    ("ante", "path"), [(0.0, "data/pushfold.json"), (0.1, "data/pushfold_ante10.json")]
)
def test_ten_bb_re_solved_from_scratch(ante, path) -> None:
    stored = pf.PushFoldSolution.load(ROOT / path).at(10)
    fresh = pf.solve_depth(10.0, ante=ante)
    assert np.array_equal(fresh.push, stored.push) and np.array_equal(fresh.call, stored.call)
    assert fresh.exploitability == stored.exploitability and fresh.value_sb == stored.value_sb
