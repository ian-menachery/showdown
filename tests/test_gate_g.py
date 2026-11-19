"""Gate G: the V1 advisor (DECISIONS 32), on a fixture of 42 spots.

DECISIONS 35 runs these spots with the fixed top-% ranges, so their answers
cannot move. A 43rd spot, AsKd first in at 40 bb, moved to model_spots.toml
(test_gate_g_model.py), where the preflop model now answers it.

River and turn equities are counted by hand in tests/fixtures/live/spots.toml.
Preflop actions must equal the push/fold solution's pure actions. Flop Monte
Carlo must land within 3 SE of exact enumeration. The 95th-percentile time is
at most 300 ms, and every suggestion is logged.
"""

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import numpy as np
import pytest

from showdown import pushfold as pf
from showdown.cli import main
from showdown.equity.cards import class_of
from showdown.equity.exact import range_vs_range
from showdown.equity.ranges import parse_range
from showdown.hh.grade import depth_for
from showdown.live.advisor import BET_EQUITY, BET_FRACTION, CALL_MARGIN, Advisor
from showdown.live.spot import Spot, SpotError

FIXTURE = tomllib.loads(
    (Path(__file__).parent / "fixtures" / "live" / "spots.toml").read_text(encoding="utf-8")
)
LATENCY_P95_MS = 300.0
TIMES: list[float] = []


@pytest.fixture(scope="module")
def advisor(tmp_path_factory):
    log = tmp_path_factory.mktemp("live") / "advice.jsonl"
    return Advisor.load(ranges="fixed", log_path=log)


def _spot(row: dict) -> Spot:
    return Spot.parse(
        row["hero"],
        row["board"],
        seat=row["seat"],
        effective_bb=row.get("bb", 50),
        pot_bb=row["pot"],
        to_call_bb=row["to_call"],
        pot_type=row.get("pot_type", "srp"),
        villain_range=row.get("villain"),
        mode=row.get("mode", "hint"),
    )


def test_fixture_has_at_least_40_spots() -> None:
    count = (
        len(FIXTURE["river"])
        + len(FIXTURE["turn"])
        + len(FIXTURE["preflop"]["spots"])
        + len(FIXTURE["preflop"]["none"])
        + len(FIXTURE["flop"])
    )
    assert count >= 40


@pytest.mark.parametrize("row", FIXTURE["river"] + FIXTURE["turn"], ids=lambda r: r["id"])
def test_river_and_turn_equal_the_hand_count(advisor, row) -> None:
    s = advisor.suggest(_spot(row))
    TIMES.append(s.elapsed_ms)
    assert s.equity == pytest.approx(row["equity"], abs=1e-12)
    assert s.se == 0
    assert s.action == row.get("action")
    if "size" in row:
        assert s.size_bb == row["size"]


@pytest.mark.parametrize("row", FIXTURE["preflop"]["spots"], ids=lambda r: f"{r[0]}-{r[1]}-{r[2]}")
def test_preflop_equals_the_push_fold_solution(advisor, row) -> None:
    hero, seat, bb, decision = row
    spot = Spot.parse(hero, seat=seat, effective_bb=bb, preflop=decision)
    s = advisor.suggest(spot)
    TIMES.append(s.elapsed_ms)
    solution = advisor.strategy.solution.at(depth_for(bb))
    probs = solution.push if seat == "sb" else solution.call
    p = float(probs[class_of(spot.hero)])
    assert p >= pf.PURE or p <= 1 - pf.PURE, f"{hero} at {bb} bb mixes; pick a pure spot"
    allin = "jam" if seat == "sb" else "call"
    assert s.action == (allin if p >= pf.PURE else "fold")
    assert s.evs is not None
    assert s.source.startswith(f"push/fold Nash at {depth_for(bb)} bb")


@pytest.mark.parametrize("row", FIXTURE["preflop"]["none"], ids=lambda r: f"{r[0]}-{r[2]}-{r[3]}")
def test_no_suggestion_outside_push_fold(advisor, row) -> None:
    hero, seat, bb, decision = row
    s = advisor.suggest(Spot.parse(hero, seat=seat, effective_bb=bb, preflop=decision))
    TIMES.append(s.elapsed_ms)
    assert s.action is None
    assert s.source.startswith("no suggestion")


def _flop_id(row: dict) -> str:
    return row["hero"] + row["board"].replace(" ", "")


@pytest.mark.parametrize("row", FIXTURE["flop"], ids=_flop_id)
def test_flop_monte_carlo_within_3_se_of_exact(advisor, row) -> None:
    spot = _spot(row)
    s = advisor.suggest(spot)
    TIMES.append(s.elapsed_ms)
    villain = (
        parse_range(row["villain"])
        if "villain" in row
        else advisor.default_range(spot.pot_type, spot.villain_seat)
    )
    exact = range_vs_range([spot.hero], villain, spot.board).equity
    assert abs(s.equity - exact) <= 3 * s.se
    # The action must be the one exact equity implies, and the spot must sit far
    # enough from its threshold that Monte Carlo noise cannot flip it.
    if spot.to_call_bb > 0:
        threshold = spot.to_call_bb / (spot.pot_bb + spot.to_call_bb) + CALL_MARGIN
        expected = "call" if exact >= threshold else "fold"
    elif spot.mode == "equity":
        threshold, expected = None, None
    else:
        threshold = BET_EQUITY
        expected = "bet" if exact >= threshold else "check"
    if threshold is not None:
        assert abs(exact - threshold) > 3 * s.se, "spot too close to its threshold"
    assert s.action == expected
    if expected == "bet":
        assert s.size_bb == round(spot.pot_bb * BET_FRACTION["flop"], 2)


_LATENCY_SCRIPT = r"""
import json, sys, time, tomllib
from showdown import preflop_model as pm
from showdown.live.advisor import Advisor
from showdown.live.spot import Spot
fixture = tomllib.loads(open(sys.argv[1], encoding="utf-8").read())
model_fixture = tomllib.loads(open(sys.argv[2], encoding="utf-8").read())
jam_fixture = tomllib.loads(open(sys.argv[3], encoding="utf-8").read())
# Gate G extended's and Gate J's spots are pinned to DECISIONS 34's model (DECISIONS 49).
fixed, model = Advisor.load(ranges="fixed"), Advisor.load(pm.v1_model_path())
spots = []
for row in fixture["river"] + fixture["turn"] + fixture["flop"]:
    spots.append(Spot.parse(row["hero"], row["board"], seat=row["seat"], effective_bb=50,
        pot_bb=row["pot"], to_call_bb=row["to_call"], pot_type=row.get("pot_type", "srp"),
        villain_range=row.get("villain"), mode=row.get("mode", "hint")))
for hero, seat, bb, decision in fixture["preflop"]["spots"] + fixture["preflop"]["none"]:
    spots.append(Spot.parse(hero, seat=seat, effective_bb=bb, preflop=decision))
jobs = [(fixed, spot) for spot in spots]
rows = model_fixture["spots"] + model_fixture["none"]
rows += model_fixture["range"] + model_fixture["range_flop"]
for row in rows:
    jobs.append((model, Spot.parse(row["hero"], row.get("board", ""), seat=row["seat"],
        effective_bb=row["bb"], pot_bb=row.get("pot", 1.5), to_call_bb=row.get("to_call", 0.0),
        pot_type=row.get("pot_type", "srp"), preflop=row.get("decision", "sb_first"))))
for row in jam_fixture["worked"] + jam_fixture["default"] + jam_fixture["none"]:
    jobs.append((model, Spot.parse(row["hero"], seat=row["seat"], effective_bb=row["bb"],
        pot_bb=row["pot"], to_call_bb=row["to_call"], preflop=row["decision"],
        villain_range=row.get("villain"), villain_top=row.get("villain_top"))))
times = []
for advisor, spot in jobs:
    start = time.perf_counter()
    advisor.suggest(spot)
    times.append((time.perf_counter() - start) * 1000)
print(json.dumps(times))
"""


def test_latency_without_coverage_tracing() -> None:
    """The 300 ms bar over Gate G's and Gate J's spots, timed in a separate process without
    pytest-cov's tracer (DECISIONS 32, 35, 36).

    In-suite timings are inflated by coverage tracing. Other heavy work running on the
    machine inflates them too, so a gate run needs an otherwise idle machine.
    """
    live = Path(__file__).parent / "fixtures" / "live"
    env = {k: v for k, v in os.environ.items() if not k.startswith("COV_CORE")}
    out = subprocess.run(
        [
            sys.executable,
            "-c",
            _LATENCY_SCRIPT,
            str(live / "spots.toml"),
            str(live / "model_spots.toml"),
            str(live / "jam_spots.toml"),
        ],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    ).stdout
    times = json.loads(out)
    p95 = float(np.percentile(times, 95))
    print(f"\n{len(times)} suggestions, 95th percentile {p95:.0f} ms, max {max(times):.0f} ms")
    assert len(times) >= 100
    assert p95 <= LATENCY_P95_MS


def test_every_suggestion_is_logged(advisor) -> None:
    assert len(TIMES) >= 40, "run the whole module"
    lines = advisor.log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(TIMES)
    for line in lines:
        record = json.loads(line)
        assert {"time", "spot", "suggestion"} <= set(record)


def test_spot_validation() -> None:
    with pytest.raises(SpotError, match="share"):
        Spot.parse("AsKd", "AsQh2c", seat="sb", effective_bb=10)
    with pytest.raises(SpotError, match="0, 3, 4 or 5"):
        Spot.parse("AsKd", "Qh2c", seat="sb", effective_bb=10)
    with pytest.raises(SpotError):
        Spot.parse("AsKd", seat="button", effective_bb=10)
    with pytest.raises(SpotError):
        Spot.parse("AsKd", seat="sb", effective_bb=0.5)
    with pytest.raises(SpotError, match="decision for the SB"):
        Advisor.load().suggest(Spot.parse("AsKd", seat="bb", effective_bb=10, preflop="sb_first"))


def test_advise_command(capsys, tmp_path) -> None:
    log = tmp_path / "a.jsonl"
    args = ["advise", "--hero", "AhKh", "--seat", "sb", "--stack", "50", "--board", "Qh7h2c3s"]
    args += ["--pot", "20", "--to-call", "10", "--villain", "QsQd", "--log", str(log)]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "turn: FOLD" in out
    assert "equity 15.9%" in out
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1
    assert main(["advise", "--hero", "Th5c", "--seat", "sb", "--stack", "10", "--no-log"]) == 0
    assert "preflop: FOLD" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="bad spot"):
        main(["advise", "--hero", "AsAs", "--seat", "sb", "--stack", "10", "--no-log"])
