"""Gate G, extended (DECISIONS 35): the preflop model in the advisor.

The fixture is tests/fixtures/live/model_spots.toml. Preflop expectations were
written by hand from `showdown preflop chart`. Each mix is checked against
data/preflop_model.json read directly. Model ranges are checked against
frequencies multiplied by hand, and against a separate weighted brute-force
count with phevaluator. The latency bar over old and new spots is in
test_gate_g.py.
"""

import itertools
import json
import tomllib
from pathlib import Path

import numpy as np
import pytest
from phevaluator import evaluate_cards

from showdown import preflop_model as pm
from showdown.cli import main
from showdown.equity.cards import (
    CLASS_COMBOS,
    CLASS_NAMES,
    card_str,
    class_index,
    class_of,
    make_combo,
    parse_cards,
)
from showdown.equity.exact import range_vs_range
from showdown.equity.montecarlo import monte_carlo
from showdown.live.advisor import (
    BET_EQUITY,
    BET_FRACTION,
    CALL_MARGIN,
    SHOWN,
    Advisor,
)
from showdown.live.spot import DECISIONS, Spot, SpotError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = tomllib.loads(
    (ROOT / "tests" / "fixtures" / "live" / "model_spots.toml").read_text(encoding="utf-8")
)
MODEL_JSON = json.loads((ROOT / "data" / "preflop_model.json").read_text(encoding="utf-8"))
SUGGESTED: list[float] = []


@pytest.fixture(scope="module")
def advisor(tmp_path_factory):
    log = tmp_path_factory.mktemp("live") / "advice.jsonl"
    return Advisor.load(log_path=log)


def _stored(depth: float, r: float = pm.R_PRODUCT) -> dict:
    """A solution straight from the JSON, without the model's own loader."""
    (found,) = [s for s in MODEL_JSON["solutions"] if s["stack"] == depth and s["r_oop"] == r]
    return found


def _freq(stored: dict, node: str, name: str, action: str) -> float:
    return stored["strategy"][node][name][stored["actions"][node].index(action)]


def _spot(row: dict) -> Spot:
    return Spot.parse(
        row["hero"],
        row.get("board", ""),
        seat=row["seat"],
        effective_bb=row["bb"],
        pot_bb=row.get("pot", 1.5),
        to_call_bb=row.get("to_call", 0.0),
        pot_type=row.get("pot_type", "srp"),
        preflop=row.get("decision", "sb_first"),
    )


# --- bar 1: preflop spots ------------------------------------------------------------------


def test_fixture_size() -> None:
    spots, none = FIXTURE["spots"], FIXTURE["none"]
    assert len(spots) + sum(r["bb"] > 20 for r in none) >= 30
    for decision in DECISIONS:
        assert sum(r["decision"] == decision for r in spots) >= 4, decision
    assert len(none) >= 4


@pytest.mark.parametrize(
    "row", FIXTURE["spots"], ids=lambda r: f"{r['hero']}-{r['bb']}-{r['decision']}"
)
def test_model_spot(advisor, row) -> None:
    spot = _spot(row)
    s = advisor.suggest(spot)
    SUGGESTED.append(s.elapsed_ms)
    assert s.action == row["action"]
    assert s.source.startswith(f"model chart, R 0.90, {row['depth']:g} bb (")
    assert ("depends on R" in s.notes) == row["r"]
    assert s.size_bb == row.get("size")
    size_notes = [n for n in s.notes if n.startswith("model assumes")]
    assert size_notes == ([row["note"]] if "note" in row else [])
    # The mix equals the stored strategy, read from the JSON directly.
    _, node = DECISIONS[row["decision"]]
    stored = _stored(float(row["depth"]))
    name = CLASS_NAMES[class_index_of(row["hero"])]
    want = {SHOWN[a]: _freq(stored, node, name, a) for a in stored["actions"][node]}
    assert s.mix == pytest.approx(want, abs=1e-12)
    assert sum(s.mix.values()) == pytest.approx(1.0, abs=1e-9)


def class_index_of(hero: str) -> int:
    return class_of(make_combo(*parse_cards(hero)))


@pytest.mark.parametrize(
    "row", FIXTURE["none"], ids=lambda r: f"{r['hero']}-{r['bb']}-{r['decision']}"
)
def test_no_suggestion(advisor, row) -> None:
    s = advisor.suggest(_spot(row))
    SUGGESTED.append(s.elapsed_ms)
    assert s.action is None
    assert s.source.startswith("no suggestion")
    assert row["why"] in s.source


def test_reach_rule_matches_the_decisions_table(advisor) -> None:
    """The reach figures DECISIONS 35 prints, rounded as printed (percent of deals)."""
    table = {
        (50, "rr"): 0.004,
        (60, "rr"): 0.642,
        (60, "rrj"): 0.049,
        (70, "rrj"): 0.124,
        (40, "j"): 0.001,
        (30, "j"): 1.72,
    }
    for (depth, node), percent in table.items():
        got = 100 * advisor.reach(depth, node)
        assert round(got, 3 if percent < 1 else 2) == percent, (depth, node, got)


# --- bar 3: model ranges --------------------------------------------------------------------

RANGE_LINES = {
    ("srp", "sb"): [("", "raise")],
    ("srp", "bb"): [("r", "call")],
    ("3bp", "bb"): [("r", "raise")],
    ("3bp", "sb"): [("", "raise"), ("rr", "call")],
}


def _hand_weight(stored: dict, pot_type: str, villain: str, name: str) -> float:
    weight = 1.0
    for node, action in RANGE_LINES[(pot_type, villain)]:
        weight *= _freq(stored, node, name, action)
    return weight


@pytest.mark.parametrize(("pot_type", "villain"), list(RANGE_LINES))
def test_range_weights_equal_the_stored_frequencies(advisor, pot_type, villain) -> None:
    found = advisor.model_range(pot_type, villain, 100)
    weights = dict(zip(found.combos, found.weights, strict=True))
    stored = _stored(100.0)
    for name in ("AKo", "T9s", "72o"):
        want = _hand_weight(stored, pot_type, villain, name)
        for combo in CLASS_COMBOS[class_index(name)]:
            if want > 0:
                assert weights[combo] == pytest.approx(want, rel=1e-12), name
            else:
                assert combo not in weights, name


NAMES = [card_str(c) for c in range(52)]


def _brute_force(row: dict, depth: float) -> float:
    """Weighted equity by phevaluator over every villain combo and runout."""
    spot = _spot(row)
    stored = _stored(depth)
    dead = set(spot.hero) | set(spot.board)
    total = weighted = 0.0
    for k, name in enumerate(CLASS_NAMES):
        w = _hand_weight(stored, spot.pot_type, spot.villain_seat, name)
        if w <= 0:
            continue
        for v in CLASS_COMBOS[k]:
            if dead & set(v):
                continue
            deck = [c for c in range(52) if c not in dead | set(v)]
            wins = ties = n = 0
            for run in itertools.combinations(deck, 5 - len(spot.board)):
                full = [NAMES[c] for c in (*spot.board, *run)]
                a = evaluate_cards(*(NAMES[c] for c in spot.hero), *full)
                b = evaluate_cards(*(NAMES[c] for c in v), *full)  # lower is better
                wins += a < b
                ties += a == b
                n += 1
            weighted += w * (wins + ties / 2) / n
            total += w
    return weighted / total


def _expected_action(spot: Spot, equity: float) -> tuple[str, float | None]:
    if spot.to_call_bb > 0:
        threshold = spot.to_call_bb / (spot.pot_bb + spot.to_call_bb) + CALL_MARGIN
        return ("call" if equity >= threshold else "fold"), threshold
    return ("bet" if equity >= BET_EQUITY else "check"), BET_EQUITY


@pytest.mark.parametrize("row", FIXTURE["range"], ids=lambda r: r["id"])
def test_turn_and_river_equal_a_weighted_brute_force(advisor, row) -> None:
    spot = _spot(row)
    s = advisor.suggest(spot)
    SUGGESTED.append(s.elapsed_ms)
    depth = row.get("depth", pm.PreflopModel.depth_for(row["bb"]))
    assert s.villain_range.startswith("model range (assumed)")
    assert f"at {depth:g} bb" in s.villain_range
    assert s.equity == pytest.approx(_brute_force(row, float(depth)), abs=1e-12)
    action, threshold = _expected_action(spot, s.equity)
    assert s.action == action
    assert s.threshold == threshold
    if action == "bet":
        assert s.size_bb == round(spot.pot_bb * BET_FRACTION[spot.street], 2)


@pytest.mark.parametrize("row", FIXTURE["range_flop"], ids=lambda r: r["id"])
def test_flop_monte_carlo_within_3_se_of_weighted_exact(advisor, row) -> None:
    spot = _spot(row)
    s = advisor.suggest(spot)
    SUGGESTED.append(s.elapsed_ms)
    found = advisor.model_range(spot.pot_type, spot.villain_seat, spot.effective_bb)
    exact = range_vs_range([spot.hero], found.combos, spot.board, found.weights).equity
    assert abs(s.equity - exact) <= 3 * s.se
    action, threshold = _expected_action(spot, exact)
    assert abs(exact - threshold) > 3 * s.se, "spot too close to its threshold"
    assert s.action == action


def test_3bet_pot_at_50bb_uses_the_fixed_default(advisor) -> None:
    spot = Spot.parse("AsKd", "Ts9s2d", seat="sb", effective_bb=50, pot_bb=5, pot_type="3bp")
    s = advisor.suggest(spot)
    SUGGESTED.append(s.elapsed_ms)
    assert s.villain_range == (
        "default (assumed): top 15% for the BB; the model almost never reaches this pot at 50 bb"
    )
    assert advisor.model_range("3bp", "bb", 50) is None
    fixed = advisor.villain(spot)
    assert fixed.combos == advisor.default_range("3bp", "bb")
    assert fixed.weights is None


# --- weighted equity: unweighted results cannot move -----------------------------------------


def test_unit_weights_equal_the_unweighted_answer() -> None:
    from showdown.equity.ranges import parse_range

    hero = [tuple(sorted(parse_cards("AhKd")))]
    villain = parse_range("TT+,AQs+,KQo")
    board = parse_cards("Kc7s2d9h")
    plain = range_vs_range(hero, villain, board)
    ones = range_vs_range(hero, villain, board, [1.0] * len(villain))
    assert ones.equity == pytest.approx(plain.equity, abs=1e-14)
    mc_plain = monte_carlo(hero, villain, board, samples=2000, seed=3)
    mc_ones = monte_carlo(
        hero, villain, board, samples=2000, seed=3, villain_weights=[2.0] * len(villain)
    )
    assert abs(mc_ones.equity - mc_plain.equity) < 4 * (mc_plain.se + mc_ones.se)
    # A weight of 0 drops a combo, so weighting only the aces equals the aces alone.
    aces = parse_range("AA")
    only = [1.0 if v in aces else 0.0 for v in villain]
    assert range_vs_range(hero, villain, board, only).equity == pytest.approx(
        range_vs_range(hero, aces, board).equity, abs=1e-14
    )
    for bad in ([1.0], [-1.0] * len(villain)):
        with pytest.raises(ValueError, match="weight"):
            range_vs_range(hero, villain, board, bad)
        with pytest.raises(ValueError, match="weight"):
            monte_carlo(hero, villain, board, samples=10, villain_weights=bad)


# --- spot errors, options and the command ---------------------------------------------------


def test_errors_and_options(advisor) -> None:
    with pytest.raises(SpotError, match="needs the amount to call"):
        advisor.suggest(Spot.parse("AhKd", seat="bb", effective_bb=50, preflop="bb_vs_raise"))
    with pytest.raises(SpotError, match="decision for the BB"):
        advisor.suggest(Spot.parse("AhKd", seat="sb", effective_bb=50, preflop="bb_vs_jam"))
    with pytest.raises(ValueError, match="ranges"):
        Advisor(advisor.strategy, advisor.model, ranges="mine")
    with pytest.raises(ValueError, match="model ranges need"):
        Advisor(advisor.strategy)
    bare = Advisor(advisor.strategy, ranges="fixed")
    s = bare.suggest(Spot.parse("AhKd", seat="sb", effective_bb=50))
    assert s.action is None
    assert s.source == "no suggestion: no preflop model loaded above 20 bb"


def test_advise_command_prints_the_mix_and_notes(capsys) -> None:
    args = ["advise", "--hero", "Kh9h", "--seat", "bb", "--stack", "100"]
    args += ["--facing", "bb_vs_raise", "--pot", "4", "--to-call", "2", "--no-log"]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "preflop: RAISE 9 bb" in out
    assert "mix: fold 0%, call 3%, raise 97%, jam 0%" in out
    assert "! depends on R" in out
    assert "! model assumes a 2.5 bb open; you face 3 bb" in out
    assert "model chart, R 0.90, 100 bb (K9s)" in out
    args = ["advise", "--hero", "AsKd", "--seat", "sb", "--stack", "50", "--board", "Ts9s2d"]
    assert main([*args, "--pot", "5", "--ranges", "fixed", "--no-log"]) == 0
    assert "default (assumed): top 55% for the BB" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="bad spot: bb_vs_raise needs"):
        main(
            [
                "advise",
                "--hero",
                "AhKd",
                "--seat",
                "bb",
                "--stack",
                "50",
                "--facing",
                "bb_vs_raise",
                "--no-log",
            ]
        )


# --- bar 6: the log ---------------------------------------------------------------------------


def test_every_suggestion_is_logged_with_mix_and_notes(advisor) -> None:
    assert len(SUGGESTED) >= 40, "run the whole module"
    lines = [json.loads(x) for x in advisor.log_path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == len(SUGGESTED)
    charts = [x["suggestion"] for x in lines if x["suggestion"]["source"].startswith("model chart")]
    assert len(charts) == len(FIXTURE["spots"])
    for s in charts:
        assert s["mix"] and isinstance(s["notes"], list)
    assert np.isfinite([x["suggestion"]["elapsed_ms"] for x in lines]).all()
