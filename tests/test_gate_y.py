"""Gate Y (DECISIONS 60), fast checks: the grade's branches, the composition of player types,
and bar 4, push/fold with types against the compiled tree."""

from pathlib import Path

import numpy as np
import pytest

from showdown import pushfold as pf
from showdown import sixmax as S
from showdown.cfr import best_response, compile_game, policy_value
from showdown.cli import main
from showdown.equity.cards import class_index
from showdown.equity.matrix import PreflopMatrix
from showdown.exploit import type_exploit, type_width, typed_spot
from showdown.games.pushfold import PushFoldGame

ROOT = Path(__file__).resolve().parents[1]


def _answer(flips, ev=(0.0, 0.2, 1.0, 0.8)) -> S.Answer:
    return S.Answer(
        hand="AA",
        actions=["fold", "limp", "open to 2.5", "open to 3"],
        ev=np.array(ev),
        se=np.zeros(4),
        best="open to 2.5",
        runner_up="open to 3",
        gap_se=5.0,
        tier="close" if flips else "clear",
        flips=flips,
        no_stackoff_best="open to 2.5",
    )


def test_grade_branches_and_cut_offs() -> None:
    ev = {"fold": 0.0, "limp": 25.0, "raise": 50.0}
    cases = {
        0.0: "Best",
        1e-10: "Best",
        1.0: "Correct",
        3.0: "Correct",
        3.0001: "Inaccuracy",
        10.0: "Inaccuracy",
        10.0001: "Wrong",
        25.0: "Wrong",
        25.0001: "Blunder",
    }
    for lost, label in cases.items():
        g = S.grade_ev(ev | {"limp": 50.0 - lost}, "raise", "limp", 100.0)
        assert g.label == label, (lost, g)
        assert g.lost == pytest.approx(lost) and g.pct == pytest.approx(lost)
    # The band floor: a band winner is Correct however much it loses at the base point.
    assert S.grade_ev(ev, "raise", "fold", 1.0, band_winners={"fold"}).label == "Correct"
    assert S.grade_ev(ev, "raise", "fold", 1.0).label == "Blunder"
    # Only the size is close: any size of the best kind is Best.
    a = _answer([(0.1, 0.0, "open to 3")])
    assert S.grade(a, "open to 3", 1.5).label == "Best"
    assert S.grade(a, "limp", 1.5).label == "Blunder"
    # Close on kind: the other size is not automatically Best.
    a = _answer([(0.1, 0.0, "limp")])
    g = S.grade(a, "open to 3", 1.5)
    assert g.label == "Wrong" and g.pct == pytest.approx(100 * 0.2 / 1.5)
    assert S.grade(a, "limp", 1.5).label == "Correct"
    assert S.grade(_answer([]), "open to 3", 10.0).label == "Correct"
    assert S.LABELS == ("Best", "Correct", "Inaccuracy", "Wrong", "Blunder")


def test_standard_and_standard_is_the_standard_profile() -> None:
    profiles = S.load_profiles()
    assert S.compose("standard", "standard", profiles=profiles) is profiles["standard"]


def test_compose_scales_the_table_and_takes_the_limpers() -> None:
    profiles, types = S.load_profiles(), S.load_types()
    std = profiles["standard"]
    assert list(types) == list(S.TYPE_KEYS)
    for lt in S.TYPE_KEYS:
        for tt in S.TYPE_KEYS:
            p = S.compose(lt, tt, profiles=profiles, types=types)
            for r in S.LIMPER_RATES:
                want = getattr(std, r) if lt == "standard" else types[lt].rates[r]
                assert getattr(p, r) == want
            ratio = types[tt].ratio
            for seat, rates in std.by_seat.items():
                q = p.for_seat(seat)
                for t, c in S.CAPS:
                    if t not in rates:
                        continue
                    want_t = min(1.0, rates[t] * ratio.get(t, 1.0))
                    assert getattr(q, t) == pytest.approx(want_t)
                    assert getattr(q, c) == pytest.approx(
                        min(1.0 - want_t, rates[c] * ratio.get(c, 1.0))
                    )
                    assert getattr(q, t) + getattr(q, c) <= 1.0 + 1e-12
            for t, c in S.CAPS:
                assert getattr(p, t) + getattr(p, c) <= 1.0 + 1e-12
            if (lt, tt) != ("standard", "standard"):
                assert p.deal_name == ("standard" if lt == "standard" else f"{lt} limpers")


def test_a_composed_deal_depends_on_the_limper_type_only() -> None:
    profiles, types = S.load_profiles(), S.load_types()
    spot = S.Spot("BTN", 2, 0.5)
    std = S.deal(spot, profiles["standard"], samples=300)
    for tt in ("nit", "station"):
        d = S.deal(spot, S.compose("standard", tt, profiles=profiles, types=types), samples=300)
        assert np.array_equal(d.combos, std.combos) and np.array_equal(d.q, std.q)
    a = S.deal(spot, S.compose("nit", "lag", profiles=profiles, types=types), samples=300)
    b = S.deal(spot, S.compose("nit", "maniac", profiles=profiles, types=types), samples=300)
    assert np.array_equal(a.combos, b.combos) and not np.array_equal(a.combos, std.combos)


def test_trait_cards_and_why() -> None:
    types = S.load_types()
    assert S.type_card(types["standard"]).startswith("Standard:")
    card = S.type_card(types["nit"])
    assert card.startswith("Nit (") and "VPIP" in card and "BB defends" in card
    p = S.compose("station", "nit", types=types)
    spot = S.Spot("BTN", 1, 0.0)
    d = S.deal(spot, p, samples=2_000)
    table = S.outcome_table(d)
    a = S.evaluate(d, class_index("KJo"), table)
    state = d.rng.bit_generator.state
    lines = S.why(d, table, class_index("KJo"), a, "fold")
    assert d.rng.bit_generator.state == state  # the why uses its own random stream
    assert lines[0].startswith(a.best) and lines[-1].startswith("fold +0.00 bb")
    assert any("everyone folds" in x for x in lines) or a.best == "overlimp"


@pytest.fixture(scope="module")
def matrix() -> PreflopMatrix:
    return PreflopMatrix.load(ROOT / "data" / "preflop_169_exact.npz")


@pytest.fixture(scope="module")
def solution() -> pf.PushFoldSolution:
    return pf.PushFoldSolution.load(ROOT / "data" / "pushfold.json")


@pytest.mark.parametrize("stack", [5, 10, 15, 20])
def test_bar4_pushfold_types_equal_the_compiled_tree(matrix, solution, stack) -> None:
    tree = compile_game(PushFoldGame(stack, matrix))
    nash = solution.at(stack)
    for kind in S.load_types().values():
        for hero, seat in (("sb", 0), ("bb", 1)):
            e = type_exploit(solution, matrix, stack, hero, kind)
            if hero == "sb":
                policy = pf.policy_from_vectors(tree, nash.push, e.read)
                assert e.nash_ev == pytest.approx(policy_value(tree, policy), abs=1e-9)
            else:
                policy = pf.policy_from_vectors(tree, e.read, nash.call)
                assert e.nash_ev == pytest.approx(-policy_value(tree, policy), abs=1e-9)
            value, br = best_response(tree, policy, seat)
            assert e.best_ev == pytest.approx(value, abs=1e-9)
            push, call = pf.strategy_vectors(tree, br)
            tree_br = push if hero == "sb" else call
            values = (pf.sb_action_values if hero == "sb" else pf.bb_action_values)(
                e.read, e.depth, matrix
            )
            clear = np.abs(values[1] - values[0]) > 1e-12
            assert np.array_equal(e.best_response[clear], tree_br[clear])


def test_typed_pushfold_spots(matrix, solution) -> None:
    types = S.load_types()
    nash = solution.at(10)
    assert type_width(types["standard"], "sb", nash) == pytest.approx(100 * nash.push_share())
    s = typed_spot(solution, matrix, 10, "sb", types["nit"], class_index("72o"))
    assert s.pot == 1.5 and set(s.ev) == {"fold", "all-in"} and s.ev["fold"] == -0.5
    assert s.grade(s.best).label == "Best"
    b = typed_spot(solution, matrix, 10, "bb", types["maniac"], class_index("A9o"))
    assert b.pot == 11.0 and set(b.ev) == {"fold", "call"} and b.nash in b.ev
    for action in b.ev:
        g = b.grade(action)
        if action in b.band_winners:
            assert g.label in ("Best", "Correct")


def test_the_commands(capsys) -> None:
    assert (
        main(
            [
                "sixmax",
                "BTN",
                "KJo",
                "--limpers",
                "1",
                "--limpers-type",
                "station",
                "--table-type",
                "nit",
                "--samples",
                "1500",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "Calling station limpers, Nit table" in out and "Limpers: Calling station (" in out
    assert main(["pushfold", "exploit", "10", "--villain-type", "lag", "--hero", "bb"]) == 0
    out = capsys.readouterr().out
    assert "no ICM" in out and "Villain: LAG (" in out and "you are the BB" in out
