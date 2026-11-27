"""Gate W, bar 1: six-max hand review classifies a hand-labelled fixture (DECISIONS 58).

The fixture's hands and labels (`tests/fixtures/sixmax_review/`) were committed before any
review code. Also here, not bars: answers equal fresh ones at a small sample, the report's
sums, and the CLI.
"""

import math
import tomllib
from pathlib import Path

import numpy as np
import pytest

from showdown import sixmax as S
from showdown import sixmax_review as V
from showdown.cli import main
from showdown.equity.cards import class_index
from showdown.hh.parse import load

FIXTURE = Path(__file__).parent / "fixtures" / "sixmax_review"
LABELS = tomllib.loads((FIXTURE / "labels.toml").read_text(encoding="utf-8"))


def key(source: str) -> str:
    path, _, hand = source.partition("#")
    return Path(path).stem + (f"#{hand}" if hand else "")


@pytest.fixture(scope="module")
def parsed():
    return load([FIXTURE])


def test_bar1_every_hand_matches_its_label(parsed) -> None:
    assert parsed.found == parsed.parsed == len(LABELS) and not parsed.failures
    seen = set()
    for record in parsed.records:
        k, d = key(record.source), V.classify(record, "Hero")
        label = LABELS[k]
        seen.add(k)
        if label.get("absent"):
            assert d is None, k
            continue
        if "cause" in label:
            assert d.cause == label["cause"], k
            continue
        got = (d.cause, d.seat, d.limpers, d.ante, d.hand, d.kind)
        want = (None, label["seat"], label["limpers"], label["ante"], label["hand"], label["kind"])
        assert got == want, k
        if "size" in label:
            assert d.size is not None and math.isclose(d.size, label["size"]), k
        else:
            assert d.size is None, k
    assert seen == set(LABELS)


def test_bar1_the_fixture_covers_what_it_must() -> None:
    graded = [v for v in LABELS.values() if "seat" in v]
    assert len(LABELS) >= 40
    assert sum("#" in k for k in LABELS) >= 2
    assert {v["seat"] for v in graded} == set(S.SEATS)
    assert {v["limpers"] for v in graded} == {0, 1, 2, 3}
    assert {v["ante"] for v in graded} == set(V.ANTES)
    assert {v["kind"] for v in graded} == {"fold", "limp", "raise"}
    assert {v["cause"] for v in LABELS.values() if "cause" in v} == set(V.CAUSES)


def test_answers_equal_fresh_ones(parsed) -> None:
    """Not a bar: the cached answers equal `sixmax.answer` exactly, at a small sample."""
    std = S.load_profiles()["standard"]
    picks = {"g09_co_overlimp_66", "g10_co_iso_qq_ante", "g26_bb_raise_jj_limper_ante"}
    picks |= {"g05_hj_overlimp_t9s", "g06_hj_iso_ajo_ante"}
    records = [r for r in parsed.records if key(r.source) in picks]
    grader = V.Grader(std, samples=1_500)
    for r in records:
        d = V.classify(r, "Hero")
        spot = S.Spot(d.seat, d.limpers, d.ante)
        mine = grader.answer(spot, class_index(d.hand))
        fresh = S.answer(spot, std, class_index(d.hand), samples=1_500)
        assert np.array_equal(mine.ev, fresh.ev) and mine.flips == fresh.flips


def test_the_report_and_the_cli(parsed, capsys) -> None:
    std = S.load_profiles()["standard"]
    decisions = V.review(parsed.records, "Hero", std, samples=1_500)
    summary = V.summarize(decisions)
    graded = [d for d in decisions if d.cause is None]
    assert summary["hands"] == len(LABELS) - 1
    assert summary["graded"] == len(graded) == sum("seat" in v for v in LABELS.values())
    assert sum(summary["skipped"].values()) == summary["hands"] - summary["graded"]
    assert sum(sum(row.values()) for row in summary["tiers"].values()) == summary["graded"]
    assert summary["bb_lost"] == pytest.approx(sum(d.bb_lost for d in graded), abs=1e-9)
    assert all(d.grade in V.GRADES and d.tier in V.TIERS for d in graded)

    review = V.Decision("x.phh", seat="BTN", limpers=2, kind="limp", grade="review")
    leaks = V.summarize([replace_lost(review, b) for b in (1.0, 2.0, 0.5)])["leaks"]
    assert [(x["count"], x["bb_lost"], x["pot"]) for x in leaks] == [(3, 3.5, "limped")]

    argv = ["sixmax", "review", str(FIXTURE), "--player", "Hero", "--samples", "1500"]
    argv.append("--kind-only")  # Gate W was scored on DECISIONS 58's review (DECISIONS 63)
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "Six-max hand review for Hero" in out and "55 hands, 55 parsed, 0 failed" in out
    assert f"Graded: {summary['graded']}." in out and "not six-handed 3" in out
    with pytest.raises(SystemExit, match="--player"):
        main(["sixmax", "review", str(FIXTURE)])
    with pytest.raises(SystemExit, match="give a hand"):
        main(["sixmax", "BTN", "AA", "KK"])


def replace_lost(d: V.Decision, bb: float) -> V.Decision:
    out = V.Decision(**vars(d))
    out.bb_lost, out.best = bb, "iso to 6"
    return out
