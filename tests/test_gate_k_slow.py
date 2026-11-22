"""Gate K: the six-max drill trainer (DECISIONS 55).

Two scripted sessions of 300 drills, seed 20261122, the standard profile, random ante.
Session A answers the best kind; session B a kind drawn uniformly (seed 7). Every grade
is checked against one worked out here, by DECISIONS 55's rule, from a fresh
`sixmax.answer` for the same spot and hand. Run with -s to see the report.
"""

import json
import os
import random
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pytest

from showdown import sixmax as S
from showdown import sixmax_drill as D
from showdown.equity.cards import class_index

pytestmark = pytest.mark.slow

SEED, DRILLS, CHOICE_SEED = 20261122, 300, 7
KEY = {"fold": "f", "limp": "l", "raise": "r"}


def _kinds(a: S.Answer) -> list[str]:
    return sorted({S.kind(n) for n in a.actions})


def _session(tmp_path, name: str, choose) -> tuple[list[dict], dict]:
    std = S.load_profiles()["standard"]
    trainer = D.Trainer(std, seed=SEED)

    def ask(prompt: str) -> str:
        return KEY[choose(trainer.last.answer)]

    summary = D.run(trainer, DRILLS, log_dir=tmp_path / name, ask=ask, show=lambda s: None)
    with open(summary["log"], encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    return rows, summary


def _expected(row: dict) -> tuple[str, float]:
    """DECISIONS 55's grade, from a fresh answer."""
    spot = S.Spot(row["seat"], row["limpers"], row["ante"])
    a = S.answer(spot, S.load_profiles()["standard"], class_index(row["class"]))
    ev = dict(zip(a.actions, a.ev, strict=True))
    mine = max(ev[n] for n in a.actions if S.kind(n) == row["answer"])
    lost = float(ev[a.best] - mine)
    if row["answer"] == S.kind(a.best):
        return "good", lost
    if any(S.kind(w) == row["answer"] for _, _, w in a.flips):
        return "marginal", lost
    return "review", lost


@pytest.fixture(scope="module")
def sessions(tmp_path_factory) -> dict:
    tmp = tmp_path_factory.mktemp("drills")
    a_rows, a_sum = _session(tmp, "a", lambda a: S.kind(a.best))
    pick = random.Random(CHOICE_SEED)
    b_rows, b_sum = _session(tmp, "b", lambda a: pick.choice(_kinds(a)))
    with ProcessPoolExecutor(max_workers=min(12, os.cpu_count() or 1)) as pool:
        expected = list(pool.map(_expected, a_rows + b_rows))
    return {
        "a": (a_rows, a_sum, expected[: len(a_rows)]),
        "b": (b_rows, b_sum, expected[len(a_rows) :]),
    }


def test_bar1_grading(sessions) -> None:
    a_rows, _, a_expected = sessions["a"]
    b_rows, _, b_expected = sessions["b"]
    assert len(a_rows) == len(b_rows) == DRILLS
    assert [r["class"] for r in a_rows] == [r["class"] for r in b_rows]
    assert all(r["grade"] == "good" for r in a_rows)
    assert [(r["grade"]) for r in a_rows] == [g for g, _ in a_expected]
    wrong = [
        (r["seat"], r["limpers"], r["class"], r["answer"], r["grade"], g)
        for r, (g, _) in zip(b_rows, b_expected, strict=True)
        if r["grade"] != g
    ]
    off = [
        abs(r["bb_lost"] - lost)
        for r, (g, lost) in zip(b_rows, b_expected, strict=True)
        if g == "review"
    ]
    counts = {g: sum(r["grade"] == g for r in b_rows) for g in ("good", "marginal", "review")}
    by_tier = {
        t: {g: sum(r["grade"] == g and r["tier"] == t for r in b_rows) for g in counts}
        for t in ("clear", "close", "review")
    }
    print(
        f"\nbar 1: session B grades {counts}; mismatches {wrong}; worst review bb gap "
        f"{max(off, default=0.0):.2e}"
    )
    print(f"  (reported) session B grades by tier: {by_tier}")
    assert not wrong
    assert max(off, default=0.0) < 1e-9
    assert counts["good"] >= 30 and counts["marginal"] >= 10 and counts["review"] >= 30


def test_bar2_speed(sessions) -> None:
    a_rows, _, _ = sessions["a"]
    seconds = np.array([r["seconds"] for r in a_rows])
    median, p95 = float(np.median(seconds)), float(np.percentile(seconds, 95))
    clear_folds = sum(r["best"] == "fold" and r["tier"] == "clear" for r in a_rows)
    print(f"\nbar 2: median {median:.2f} s, 95th percentile {p95:.2f} s, max {seconds.max():.2f} s")
    print(f"  (reported) drills whose best is a clear fold: {clear_folds} of {len(a_rows)}")
    assert median <= 2.0 and p95 <= 5.0


def test_bar3_log_and_summary(sessions) -> None:
    for name in ("a", "b"):
        rows, summary, _ = sessions[name]
        assert len(rows) == summary["drills"] == DRILLS
        assert all(r["answer"] in KEY for r in rows)
        for g in ("good", "marginal", "review"):
            assert summary["grades"][g] == sum(r["grade"] == g for r in rows)
        assert abs(summary["bb_lost"] - sum(r["bb_lost"] for r in rows)) < 1e-9
        print(
            f"\nbar 3, session {name.upper()}: {summary['grades']}, bb lost "
            f"{summary['bb_lost']:.3f}"
        )
