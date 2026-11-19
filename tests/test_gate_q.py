"""Gate Q's machinery (DECISIONS 49), before any solve: the 4x tree, the closed-form payoffs on
a sample of deals, and the switch on a small fake re-solved model.

The bars themselves need the fit and the product solve, so they are in test_gate_q_slow.py,
where they skip until those exist. The fit's own tests are in test_preflop_fit.py.
"""

import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from showdown import preflop_fit
from showdown import preflop_model as pm
from showdown.bot.policy import PushFoldStrategy
from showdown.cfr import compile_game
from showdown.cli import main
from showdown.equity.cards import CLASS_NAMES, class_index, make_combo, parse_cards
from showdown.equity.matrix import PreflopMatrix
from showdown.games.base import CHANCE, TERMINAL
from showdown.games.preflop import (
    ACTION_NAMES,
    ACTIONS_4X,
    CALL,
    CODE,
    FOLD,
    JAM,
    NODES_4X,
    RAISE,
    RAISE_4X,
    PreflopGame,
)
from showdown.live import hand, solve
from showdown.live.advisor import Advisor
from showdown.live.spot import Spot
from showdown.postflop.spot import FlopSpot

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "data" / "preflop_169_exact.npz"
TERMINALS_PER_DEAL = 15
"""f, rf, rc, rrf, rrc, rrjf, rrjc, r4f, r4c, r4jf, r4jc, rjf, rjc, jf, jc."""
NODES_PER_DEAL = 23


@pytest.fixture(scope="module")
def matrix() -> PreflopMatrix:
    return PreflopMatrix.load(MATRIX)


def closed_form(history: str, e: float, stack: float, r: dict[str, float]) -> float:
    """The SB's net in bb at a terminal, written from DECISIONS 49's payoff rules alone.

    It tracks each player's contribution. A fold loses the folder's contribution. A call of
    an all-in pays S(2E − 1). A call of a raise or 3-bet, with c in from each, pays
    c(2·share − 1), with share = 1 − R(1 − E) and R the pot's: c = 2.5 is the open, 7.5 the
    3x 3-bet, 10 the 4x 3-bet.
    """
    put_in = [0.5, 1.0]  # SB, BB
    facing_allin = False
    for k, action in enumerate(history):
        me, other = k % 2, 1 - k % 2
        if action == "f":
            return -put_in[0] if me == 0 else put_in[1]
        if action == "r":
            put_in[me] = 2.5 if k == 0 else 7.5
        elif action == "4":
            put_in[me] = 10.0
        elif action == "j":
            put_in[me] = stack
            facing_allin = True
        elif action == "c":
            put_in[me] = put_in[other]
            if facing_allin:
                return stack * (2 * e - 1)
            pot = {2.5: "open", 7.5: "3x", 10.0: "4x"}[put_in[0]]
            share = 1 - r[pot] * (1 - e)
            return put_in[0] * (2 * share - 1)
    raise AssertionError(f"{history!r} is not terminal")


def check_terminals(tree, matrix: PreflopMatrix, stack: float, r: dict, deals=None) -> int:
    """Every terminal of the listed deals (all of them by default) against the closed form."""
    checked = 0
    for deal, child in zip(tree.labels[0], tree.children[0], strict=True):
        if deals is not None and deal not in deals:
            continue
        i, j = divmod(deal, 169)
        e = float(matrix.equity[i, j])
        todo = [(child, "")]
        while todo:
            node, history = todo.pop()
            if tree.player[node] == TERMINAL:
                want = closed_form(history, e, stack, r)
                assert tree.utility[node] == pytest.approx(want, abs=1e-12), (deal, history)
                checked += 1
                continue
            for action, nxt in zip(tree.labels[node], tree.children[node], strict=True):
                todo.append((nxt, history + CODE[action]))
    return checked


def test_the_4x_tree(matrix) -> None:
    r = {"open": 0.85, "3x": 1.2, "4x": 0.95}
    game = PreflopGame(25, matrix, r=r)
    assert game.r == r and game.r_oop is None
    tree = compile_game(game)
    assert tree.player[0] == CHANCE
    assert tree.num_nodes == 1 + 169 * 169 * NODES_PER_DEAL
    assert tree.num_infosets == len(NODES_4X) * 169 == 1352
    assert {key.split(":")[2] for key in tree.infoset_key} == set(NODES_4X)
    assert ACTIONS_4X[(RAISE,)] == (FOLD, CALL, RAISE, RAISE_4X, JAM)
    assert [ACTION_NAMES[a] for a in ACTIONS_4X[(RAISE,)]] == [
        "fold",
        "call",
        "raise",
        "raise 4x",
        "all-in",
    ]
    # Bar 2's closed form on a sample of deals; the bar runs every deal in the slow suite.
    deals = set(range(0, 169 * 169, 997))
    assert check_terminals(tree, matrix, 25, r, deals) == len(deals) * TERMINALS_PER_DEAL


def test_a_short_solve_of_the_4x_tree_reads_every_node() -> None:
    r = {"open": 0.9, "3x": 1.05, "4x": 1.0}
    s = pm.solve_depth(25, None, iterations=2, matrix_path=MATRIX, r=r, shift=0.05)
    assert (s.r, s.shift, s.r_oop) == (r, 0.05, None)
    assert set(s.strategy) == set(NODES_4X)
    assert s.actions["r"] == ["fold", "call", "raise", "raise 4x", "all-in"]
    for node, rows in s.strategy.items():
        assert len(rows) == 169
        assert all(np.isclose(sum(p), 1.0) for p in rows.values()), node
    assert s.exploitability > 0
    assert pm.decode_solution(pm.encode_solution(s)) == s


def test_r_is_per_pot_and_any_value_in_0_to_2(matrix) -> None:
    PreflopGame(25, matrix, r={"open": 1.5, "3x": 1.99, "4x": 0.01})
    for bad in (
        {"open": 2.0, "3x": 1.0, "4x": 1.0},
        {"open": 0.0, "3x": 1.0, "4x": 1.0},
        {"open": 1.0, "3x": 1.0},
    ):
        with pytest.raises(ValueError):
            PreflopGame(25, matrix, r=bad)
    with pytest.raises(ValueError, match="3-bet to 10"):
        PreflopGame(10, matrix, r={"open": 0.9, "3x": 0.9, "4x": 0.9})
    with pytest.raises(ValueError, match="r_oop"):  # DECISIONS 34's tree keeps its check
        PreflopGame(25, matrix, r_oop=1.2)


# --- the switch, on a fake re-solved model ------------------------------------------------


def _history(code: str) -> tuple[int, ...]:
    return tuple(CODE.index(c) for c in code)


def _row(node: str, depth: float, shift: float, name: str) -> list[float]:
    """Hand-made frequencies. At 25 bb the BB never 3-bets 4x; at 100 bb it 4x 3-bets more
    often than 3x. AA 4x 3-bets except at −0.05, where it calls (so it depends on R)."""
    if node == "":
        return [0.0, 1.0, 0.0]
    if node == "r":
        if name == "AA":
            calls = shift < 0 or depth == 25
            return [0.0, 1.0, 0.0, 0.0, 0.0] if calls else [0.0, 0.0, 0.0, 1.0, 0.0]
        if name == "KK":
            return [0.0, 0.0, 1.0, 0.0, 0.0]
        three, four = {25: (0.25, 0.0), 100: (0.05, 0.2)}.get(depth, (0.15, 0.1))
        return [0.4, 0.55 - three - four, three, four, 0.05]
    if node in ("rr", "r4"):
        if name == "AA":
            return [0.0, 1.0, 0.0] if node == "rr" else [0.0, 0.0, 1.0]
        return [0.2, 0.5, 0.3]
    if name == "AA" and node in ("rrj", "r4j"):
        return [1.0, 0.0] if node == "rrj" else [0.0, 1.0]
    return [0.5, 0.5]


def fake_model() -> pm.PreflopModel:
    actions = {n: [ACTION_NAMES[a] for a in ACTIONS_4X[_history(n)]] for n in NODES_4X}
    solutions = []
    for shift in pm.SHIFTS:
        for depth in pm.GRID:
            strategy = {
                n: {name: _row(n, depth, shift, name) for name in CLASS_NAMES} for n in NODES_4X
            }
            r = pm.shifted({"open": 0.9, "3x": 1.0, "4x": 1.1}, shift)
            solutions.append(
                pm.DepthSolution(float(depth), None, True, 1e-4, 0.0, strategy, actions, r, shift)
            )
    return pm.PreflopModel(1000, pm.DEFAULT_MATRIX, "0" * 64, solutions, [], 2, {})


@pytest.fixture(scope="module")
def advisor() -> Advisor:
    return Advisor(PushFoldStrategy.load(), fake_model())


def _pre(hero: str, seat: str, bb: float, decision: str, pot: float, to_call: float, **kw):
    return Spot.parse(
        hero, seat=seat, effective_bb=bb, preflop=decision, pot_bb=pot, to_call_bb=to_call, **kw
    )


def test_the_bb_has_five_actions_and_two_3bet_sizes(advisor) -> None:
    aa = advisor.suggest(_pre("AhAd", "bb", 50, "bb_vs_raise", 3.5, 1.5))
    assert (aa.action, aa.size_bb) == ("raise", 10.0)  # 4x the 2.5 bb open
    assert list(aa.mix) == ["fold", "call", "raise 3x", "raise 4x", "jam"]
    assert aa.mix["raise 4x"] == 1.0
    assert aa.notes == ("depends on R",)  # it calls at −0.05
    assert aa.source == "model chart, fitted R, 50 bb (AA)"
    kk = advisor.suggest(_pre("KhKd", "bb", 50, "bb_vs_raise", 3.5, 1.5))
    assert (kk.action, kk.size_bb, kk.notes) == ("raise", 7.5, ())
    bigger = advisor.suggest(_pre("AhAd", "bb", 50, "bb_vs_raise", 4.0, 2.0))
    assert (bigger.action, bigger.size_bb) == ("raise", 12.0)  # 4x the 3 bb open faced
    assert bigger.notes == ("depends on R", "model assumes a 2.5 bb open; you face 3 bb")
    fold = advisor.suggest(_pre("7c2d", "bb", 50, "bb_vs_raise", 3.5, 1.5))
    assert fold.action == "fold" and fold.mix == pytest.approx(
        {"fold": 0.4, "call": 0.3, "raise 3x": 0.15, "raise 4x": 0.1, "jam": 0.05}
    )
    first = advisor.suggest(_pre("AhAd", "sb", 50, "sb_first", 1.5, 0.5))
    assert (first.action, first.size_bb) == ("raise", 2.5)
    assert list(first.mix) == ["fold", "raise", "jam"]


def test_a_faced_3bet_maps_to_3x_or_4x_by_its_ratio(advisor) -> None:
    cases = [
        # (pot, to call, open as typed, the 3x or 4x node's answer for AA, the note)
        (10.0, 5.0, None, "call", None),  # 7.5 into a 2.5 open: 3x
        (12.5, 7.5, None, "jam", None),  # 10: 4x
        (11.25, 6.25, None, "call", "model assumes a 7.5 bb 3-bet; you face 8.75 bb"),  # 3.5x
        (11.5, 6.5, None, "jam", "model assumes a 10 bb 3-bet; you face 9 bb"),  # 3.6x
        (13.5, 7.5, 3.0, "call", "model assumes a 7.5 bb 3-bet; you face 10.5 bb"),  # 3.5x of 3
        (15.0, 9.0, 3.0, "jam", "model assumes a 10 bb 3-bet; you face 12 bb"),  # 4x of 3
    ]
    for pot, to_call, open_bb, action, note in cases:
        s = advisor.suggest(_pre("AhAd", "sb", 50, "sb_vs_3bet", pot, to_call, open_bb=open_bb))
        assert s.action == action, (pot, to_call, open_bb, s)
        assert s.notes == ((note,) if note else ()), (pot, to_call, s.notes)
        assert list(s.mix) == ["fold", "call", "jam"]
    # At 25 bb the fake BB never 3-bets 4x, so that decision is not answered.
    s = advisor.suggest(_pre("AhAd", "sb", 25, "sb_vs_3bet", 12.5, 7.5))
    assert s.action is None and "almost never reaches" in s.source


def test_the_4bet_jam_is_placed_by_the_bbs_own_3bet(advisor) -> None:
    # The BB's 3-bet is the effective stack less the call: 50 − 40 = 10 (4x), 50 − 42.5 = 7.5.
    four = advisor.suggest(_pre("AhAd", "bb", 50, "bb_vs_4bet_jam", 60.0, 40.0))
    three = advisor.suggest(_pre("AhAd", "bb", 50, "bb_vs_4bet_jam", 57.5, 42.5))
    assert (four.action, three.action) == ("call", "fold")
    assert four.notes == three.notes == ()


def test_3bet_pot_ranges_follow_the_ratio_or_the_more_common_size(advisor) -> None:
    deep = advisor.model_range("3bp", "bb", 100)
    assert deep.label.startswith("model range (assumed): the BB's 3bp (4x) line at 100 bb")
    assert ", fitted R, " in deep.label
    told = advisor.model_range("3bp", "bb", 100, "3x")
    assert "3bp (3x) line" in told.label and told.weights != deep.weights
    assert "3bp (3x) line at 50 bb" in advisor.model_range("3bp", "sb", 50).label
    assert advisor.model_range("3bp", "bb", 25, "4x") is None  # unreached
    assert "the SB's srp line at 50 bb, fitted R" in advisor.model_range("srp", "sb", 50).label
    spot = Spot.parse("AsKd", "Ts9s2d", seat="sb", effective_bb=100, pot_bb=15, pot_type="3bp")
    assert "3bp (4x)" in advisor.villain(spot).label
    typed = Spot.parse(
        "AsKd", "Ts9s2d", seat="sb", effective_bb=100, pot_bb=15, pot_type="3bp", threebet_bb=7.5
    )
    assert advisor.threebet_line(typed) == "3x" and "3bp (3x)" in advisor.villain(typed).label


def test_live_solves_pick_the_line_from_the_history(advisor) -> None:
    moves = (
        hand.Move("preflop", "sb", "raise", 2.5, 2.0, False),
        hand.Move("preflop", "bb", "raise", 10.0, 9.0, False),
        hand.Move("preflop", "sb", "call", 10.0, 7.5, False),
        hand.Move("flop", "bb", "check", 0.0, 0.0, False),
        hand.Move("flop", "sb", "check", 0.0, 0.0, False),
    )
    assert hand.preflop_raises(moves) == (2.5, 10.0)
    assert hand.preflop_raises(moves[:1]) == (2.5, None)
    spot = Spot(
        hero=make_combo(*parse_cards("AsKd")),
        seat="sb",
        effective_bb=100,
        board=parse_cards("Ts9s2d4h"),
        pot_bb=20,
        history=tuple(str(m) for m in moves),
    )
    assert advisor.solves.context(spot).size == "4x"
    three = (
        moves[0],
        hand.Move("preflop", "bb", "raise", 8.75, 7.75, False),
        hand.Move("preflop", "sb", "call", 8.75, 6.25, False),
        *moves[3:],
    )
    spot = replace(spot, history=tuple(str(m) for m in three))
    assert advisor.solves.context(spot).size == "3x"
    old = Advisor.load(pm.v1_model_path())
    assert old.solves.context(spot).size is None  # DECISIONS 34's model has one 3-bet pot


def test_the_flop_spot_takes_the_more_common_3bet(tmp_path) -> None:
    path = tmp_path / "model.json"
    fake_model().save(path)
    deep = FlopSpot.make("3bp", 100, "Kc7d6c", path)
    assert (deep.put_in, deep.pot_chips, deep.stack_chips) == (10.0, 200, 900)
    mid = FlopSpot.make("3bp", 50, "Kc7d6c", path)
    assert (mid.put_in, mid.pot_chips, mid.stack_chips) == (7.5, 150, 425)
    srp = FlopSpot.make("srp", 50, "Kc7d6c", path)
    assert (srp.pot_chips, srp.stack_chips) == (50, 475)
    assert deep.spec()["oop_range"] != mid.spec()["oop_range"]


def test_the_model_file_round_trips_and_charts(tmp_path, capsys) -> None:
    path = tmp_path / "model.json"
    model = fake_model()
    model.save(path)
    assert path.read_text(encoding="utf-8").startswith('{"version": 2')
    loaded = pm.PreflopModel.load(path)
    assert loaded.version == 2 and loaded.r_label == "fitted R"
    assert loaded.at(50).r == {"open": 0.9, "3x": 1.0, "4x": 1.1}
    assert loaded.at(50, shift=0.05).r == pytest.approx({"open": 0.95, "3x": 1.05, "4x": 1.15})
    assert loaded.depends_on_r(50, "r", class_index("AA"))
    assert not loaded.depends_on_r(50, "r", class_index("KK"))
    with pytest.raises(KeyError, match="shift"):
        loaded.at(55)
    assert main(["preflop", "chart", "50", "--node", "r", "--file", str(path)]) == 0
    out = capsys.readouterr().out
    assert "model chart, fitted R, 50 bb, node 'r'" in out
    assert "R open 0.900, 3x 1.000, 4x 1.100; reached 100.000%" in out
    assert "Q*" in out  # AA 4x 3-bets, and depends on R


def test_the_product_build_moves_the_old_model(tmp_path, monkeypatch, capsys) -> None:
    from showdown.postflop import library

    out = tmp_path / "preflop_model.json"
    old = pm.PreflopModel(1000, pm.DEFAULT_MATRIX, "0" * 64, [], [])
    old.save(out)
    before = out.read_bytes()

    def no_fit():
        raise preflop_fit.FitError("round 2 of the R fit has not run")

    monkeypatch.setattr(preflop_fit, "load", no_fit)
    with pytest.raises(SystemExit, match="round 2"):
        main(["preflop", "build", "--out", str(out)])
    monkeypatch.setattr(preflop_fit, "load", lambda: {})
    monkeypatch.setattr(preflop_fit, "product_r", lambda data: ({50.0: {}}, {"open": {}}))
    monkeypatch.setattr(library, "on_ac_power", lambda: False)
    with pytest.raises(SystemExit, match="AC power"):
        main(["preflop", "build", "--out", str(out)])
    built = []
    monkeypatch.setattr(library, "on_ac_power", lambda: True)
    monkeypatch.setattr(library, "_keep_awake", lambda on: None)
    monkeypatch.setattr(
        pm, "build_fitted", lambda r, fit, **kw: built.append((r, fit, kw)) or fake_model()
    )
    assert main(["preflop", "build", "--out", str(out), "--workers", "3"]) == 0
    assert built == [({50.0: {}}, {"open": {}}, {"iterations": 1000, "workers": 3})]
    moved = tmp_path / "preflop_model_v1.json"
    assert moved.read_bytes() == before  # byte for byte
    assert pm.PreflopModel.load(out).version == 2
    assert "moved the old model" in capsys.readouterr().out
    # A second build replaces the re-solved model and leaves the old one alone.
    assert main(["preflop", "build", "--out", str(out)]) == 0
    assert moved.read_bytes() == before
    assert sorted(os.listdir(tmp_path)) == ["preflop_model.json", "preflop_model_v1.json"]


def test_advise_takes_the_open_and_the_3bet(capsys) -> None:
    args = ["advise", "--hero", "AhKh", "--seat", "sb", "--stack", "100", "--board", "Ts9s2d"]
    args += ["--pot", "20", "--pot-type", "3bp", "--open", "2.5", "--threebet", "10", "--no-log"]
    assert main(args) == 0
    assert "flop:" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="above 0"):
        main([*args[:-1], "--open", "0", "--no-log"])


def test_solve_context_needs_no_size_for_single_raised_pots(advisor) -> None:
    moves = (
        hand.Move("preflop", "sb", "raise", 2.5, 2.0, False),
        hand.Move("preflop", "bb", "call", 2.5, 1.5, False),
    )
    spot = Spot(
        hero=make_combo(*parse_cards("AsKd")),
        seat="sb",
        effective_bb=50,
        board=parse_cards("Ts9s2d4h"),
        pot_bb=5,
        history=tuple(str(m) for m in moves),
    )
    ctx = advisor.solves.context(spot)
    assert (ctx.pot_type, ctx.size) == ("srp", None)
    assert ctx.key("turn")[-1] is None
    assert np.isclose(solve.street_line(spot.history, "flop").pot_bb, 5.0)
