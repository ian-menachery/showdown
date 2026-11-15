"""Gate J: the jam-vs-range helper (DECISIONS 36).

Bar 1: given the solution's own jam range, the helper's best response
reproduces push/fold's and the model's calls. Bar 3: the hand-worked
fixture tests/fixtures/live/jam_spots.toml. Bar 2 (exact enumeration) is in
test_gate_j_slow.py. Bar 4, the latency, is timed with Gate G's spots in
test_gate_g.py.
"""

import tomllib
from pathlib import Path

import numpy as np
import pytest

from showdown import preflop_model as pm
from showdown import pushfold as pf
from showdown.cli import main
from showdown.equity.cards import CLASS_COMBOS, CLASS_NAMES
from showdown.equity.matrix import PreflopMatrix
from showdown.live import jam
from showdown.live.advisor import Advisor
from showdown.live.spot import Spot, SpotError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = tomllib.loads(
    (ROOT / "tests" / "fixtures" / "live" / "jam_spots.toml").read_text(encoding="utf-8")
)
PURE = 0.99
INDIFFERENT_BB = 0.001


@pytest.fixture(scope="module")
def matrix() -> PreflopMatrix:
    return PreflopMatrix.load(ROOT / "data" / "preflop_169_exact.npz")


@pytest.fixture(scope="module")
def advisor() -> Advisor:
    return Advisor.load()


def _spot(row: dict) -> Spot:
    return Spot.parse(
        row["hero"],
        seat=row["seat"],
        effective_bb=row["bb"],
        pot_bb=row.get("pot", 1.5),
        to_call_bb=row.get("to_call", 0.0),
        preflop=row["decision"],
        villain_range=row.get("villain"),
        villain_top=row.get("villain_top"),
    )


# --- bar 1: the helper is the solution's best response ------------------------------------


def _best_response_matches(call_probs, weights, pot, to_call, matrix) -> tuple[int, int, list]:
    """(pure classes checked, indifferent classes, mismatches)."""
    checked = indifferent = 0
    mismatches = []
    for k in range(169):
        p = float(call_probs[k])
        if 1 - PURE < p < PURE:
            continue  # the solution mixes this class
        result = jam.answer(jam.jam_equity(CLASS_COMBOS[k][0], weights, matrix), pot, to_call)
        if abs(result.ev_call) <= INDIFFERENT_BB:
            indifferent += 1
            continue
        checked += 1
        expected = "call" if p >= PURE else "fold"
        if result.action != expected:
            mismatches.append((CLASS_NAMES[k], expected, result.action, result.ev_call))
    return checked, indifferent, mismatches


def test_bar1_reproduces_push_fold_at_every_depth(matrix) -> None:
    solution = pf.PushFoldSolution.load(ROOT / "data" / "pushfold.json")
    total = total_indifferent = 0
    for stack in range(1, 21):
        nash = solution.at(stack)
        checked, indifferent, mismatches = _best_response_matches(
            nash.call, nash.push, stack + 1, stack - 1, matrix
        )
        assert mismatches == [], (stack, mismatches)
        total += checked
        total_indifferent += indifferent
    print(f"\npush/fold: {total} pure classes agree, {total_indifferent} indifferent")
    assert total > 20 * 100


MODEL_CASES = [("j", s) for s in (25, 30)]
MODEL_CASES += [("rj", s) for s in pm.GRID]
MODEL_CASES += [("rrj", s) for s in (70, 80, 90, 100)]
PUT_IN = {"j": 1.0, "rj": 2.5, "rrj": 7.5}
"""What the hero has in when facing the jam: the pot is S + this, the call S - this."""


@pytest.mark.parametrize(("node", "stack"), MODEL_CASES, ids=lambda x: str(x))
def test_bar1_reproduces_the_model_where_it_is_reached(matrix, node, stack) -> None:
    solution = pm.PreflopModel.load(ROOT / "data" / "preflop_model.json").at(stack)
    sb, bb = solution.line_factors(node)
    villain = sb if node in ("j", "rrj") else bb  # the jammer's own line
    calls = np.array([solution.probs(node, k)["call"] for k in range(169)])
    put_in = PUT_IN[node]
    checked, indifferent, mismatches = _best_response_matches(
        calls, villain, stack + put_in, stack - put_in, matrix
    )
    assert mismatches == [], mismatches
    print(f"\n{node} at {stack} bb: {checked} pure classes agree, {indifferent} indifferent")
    assert checked >= 20  # not vacuous; at rrj the model mixes most classes


# --- bar 3: hand-worked spots ---------------------------------------------------------------


@pytest.mark.parametrize("row", FIXTURE["worked"], ids=lambda r: r["id"])
def test_bar3_hand_worked(advisor, row) -> None:
    s = advisor.suggest(_spot(row))
    assert s.equity == pytest.approx(row["equity"], abs=1e-5)
    assert s.threshold == pytest.approx(row["price"], abs=1e-12)
    assert s.action == row["action"]
    assert s.evs["call"] == pytest.approx(row["ev"], abs=1e-3)
    assert s.evs["fold"] == 0.0
    assert list(s.notes) == row["notes"]
    assert s.source == "jam vs range: exact equity; EV relative to folding"
    if "label" in row:
        assert s.villain_range == row["label"]


@pytest.mark.parametrize("row", FIXTURE["default"], ids=lambda r: r["id"])
def test_bar3_defaults(advisor, row) -> None:
    s = advisor.suggest(_spot(row))
    assert s.threshold == pytest.approx(row["price"], abs=1e-12)
    assert s.action == row["action"]
    assert s.villain_range.startswith(row["label"] + ", ")
    total = row["pot"] + row["to_call"]
    assert s.evs["call"] == pytest.approx(s.equity * total - row["to_call"], abs=1e-12)


@pytest.mark.parametrize("row", FIXTURE["none"], ids=lambda r: r["id"])
def test_bar3_no_suggestion(advisor, row) -> None:
    s = advisor.suggest(_spot(row))
    assert s.action is None
    assert row["why"] in s.source


@pytest.mark.parametrize("row", FIXTURE["error"], ids=lambda r: r["id"])
def test_bar3_errors(advisor, row) -> None:
    with pytest.raises(SpotError, match=row["match"]):
        advisor.suggest(_spot(row))


def test_fixture_size() -> None:
    assert len(FIXTURE["worked"]) >= 10
    assert sum("close" in r["notes"] for r in FIXTURE["worked"]) >= 2


# --- the module, the command and postflop use ------------------------------------------------


def test_module_edges(matrix) -> None:
    with pytest.raises(jam.RangeError, match="no villain hand"):
        jam.jam_equity(CLASS_COMBOS[0][0], np.zeros(169), matrix)
    with pytest.raises(ValueError, match="to-call"):
        jam.answer(0.5, 10, -1)
    free = jam.answer(0.3, 2, 0)  # a 1 bb jam: calling is free
    assert (free.price, free.action, free.ev_call) == (0.0, "call", 0.6)


def test_advise_command_shows_the_exploit_view(capsys) -> None:
    args = ["advise", "--hero", "Kc8d", "--seat", "bb", "--stack", "10", "--facing", "bb_vs_jam"]
    args += ["--pot", "11", "--to-call", "9", "--villain", "TT", "--no-log"]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "preflop: FOLD" in out
    assert "! push/fold Nash at 10 bb says call; against this range folding gains +3.50 bb" in out
    assert "equity 27.5% vs custom: TT" in out
    args = ["advise", "--hero", "KhKd", "--seat", "bb", "--stack", "50", "--facing", "bb_vs_jam"]
    assert main([*args, "--pot", "51", "--to-call", "49", "--villain-top", "0.5", "--no-log"]) == 0
    assert "vs top 0.5% (--villain-top)" in capsys.readouterr().out


def test_villain_top_postflop(advisor) -> None:
    spot = Spot.parse("AsKd", "Ts9s2d", seat="sb", effective_bb=50, pot_bb=5, villain_top=20)
    s = advisor.suggest(spot)
    assert s.villain_range.startswith("top 20% (--villain-top), ")
    assert s.equity is not None
