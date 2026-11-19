"""Gate V: live turn and river solves in the advice (DECISIONS 47).

Bar 1 and the rules behind the solves run here; bars 2 to 4 are in test_gate_v_slow.py.
These tests run the streets bridge, built by `showdown postflop build`.
"""

import hashlib
import re
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from showdown.cli import main
from showdown.equity.cards import ALL_COMBOS, make_combo, parse_cards
from showdown.live import hand, solve
from showdown.live.advisor import Advisor
from showdown.live.narrow import INDEX
from showdown.live.spot import Spot
from showdown.live.table import frames_from_history
from showdown.live.tracker import Tracker

HANDS = Path("tests/fixtures/live/hands")


@pytest.fixture(scope="module")
def advisor() -> Advisor:
    return Advisor.load(samples=500)


def fingerprint(v) -> str:
    weights = v.weights or (1.0,) * len(v.combos)
    return hashlib.sha256(repr((v.combos, weights)).encode()).hexdigest()[:12]


def river(name: str) -> hand.Decision:
    return hand.load(HANDS / name).decisions[-1]


def test_bar1_the_two_river_lines_reach_the_advice_with_solved_ranges(advisor, capsys) -> None:
    third, shove = river("hu_full_hand.phh"), river("hu_river_shove.phh")
    assert third.history[:-1] == shove.history[:-1] and third.seat == shove.seat == "sb"
    seen = {}
    for name, d in (("third of the pot", third), ("shove", shove)):
        spot = d.spot()
        s = advisor.suggest(spot)
        assert s.source.startswith(solve.SOURCE), s.source
        assert "river: solved" in s.villain_range
        v = advisor.advice_range(spot)
        seen[name] = fingerprint(v)
        print(f"{name}: {s.action}, mix {s.mix}, weight {sum(v.weights):.4f}, {seen[name]}")
    assert seen["third of the pot"] != seen["shove"]
    capsys.readouterr()
    traced = []
    for name in ("hu_full_hand.phh", "hu_river_shove.phh"):
        main(["replay", str(HANDS / name), "--hero", "sb", "--trace"])
        out = capsys.readouterr().out
        river_block = out.split("[4] river")[1]
        assert solve.SOURCE in river_block
        traced.append(re.findall(r"fingerprint (\w+)", river_block)[-1])
    assert traced == [seen["third of the pot"], seen["shove"]]


def test_street_line_rebuilds_the_real_pot_and_moves() -> None:
    history = tuple(str(m) for m in river("hu_full_hand.phh").history)
    turn = solve.street_line(history, "turn")
    assert (turn.pot_bb, turn.put_bb) == pytest.approx((8.4, 4.2))
    assert [(a.seat, a.kind, a.to_bb) for a in turn.acts] == [("bb", "bet", 4), ("sb", "call", 4)]
    assert turn.acts[0].f == pytest.approx(4 / 8.4)
    assert turn.acts[1].to_call_bb == 4 and turn.bets_bb == {"sb": 4, "bb": 4}
    nothing_yet = solve.street_line(history[:7], "river")  # the turn is called; no river move
    assert (nothing_yet.pot_bb, nothing_yet.acts) == (pytest.approx(16.4), ())
    raise_ = solve.Act("sb", "raise", 12, False, pot_bb=14, own_bb=0, to_call_bb=4)
    assert raise_.f == pytest.approx((12 - 4) / (14 + 4))


def test_the_report_asks_for_every_decision_node() -> None:
    paths = set(solve.REPORT)
    assert {(), ("Check",), ("Bet",), ("AllIn",), ("Check", "Bet", "Raise", "AllIn")} <= paths
    assert all(p[:-1] in paths for p in paths if p)
    assert not any("AllIn" in p[:-1] or "Check" in p[1:] for p in paths)
    assert max(len(p) for p in paths) == solve.MAX_MOVES


def node(seat, actions, combos, rows) -> solve.Node:
    index = np.array([INDEX[c] for c in combos])
    return solve.Node(seat, tuple(actions), index, np.array(rows, dtype=float))


def test_off_tree_sizes_map_to_the_nearest_tree_size() -> None:
    a, b = ALL_COMBOS[0], ALL_COMBOS[1]
    rows = [[1, 0], [0, 1], [0, 0]]
    root = node("bb", [("Check", None), ("Bet", 66), ("AllIn", 900)], [a, b], rows)
    facing = node(
        "sb", [("Fold", None), ("Call", None), ("AllIn", 900)], [a, b], rows[1::-1] + [[0, 0]]
    )
    allin = node("sb", [("Fold", None), ("Call", None)], [a, b], [[0, 1], [1, 0]])
    nodes = {(): root, ("Bet",): facing, ("AllIn",): allin}
    solved = solve.Solved("turn", {"starting_pot": 100}, nodes, {}, (), 0, 0)
    line = solve.StreetLine(
        10,
        5,
        (
            solve.Act("bb", "bet", 2.5, False, 10, 0, 0),
            solve.Act("sb", "call", 2.5, False, 12.5, 0, 2.5),
        ),
        {"sb": 2.5, "bb": 2.5},
    )
    walked = solve.walk(solved, line)
    assert walked.path == ("Bet", "Call") and walked.bets == {"sb": 66, "bb": 66}
    (note,) = walked.notes
    assert note == "BB's turn bet to 2.5 bb (25% of the pot) solved as the tree's 66% bet"
    assert walked.mult["bb"][[INDEX[a], INDEX[b]]].tolist() == [0, 1]
    assert walked.mult["sb"][[INDEX[a], INDEX[b]]].tolist() == [1, 0]
    assert walked.mult["sb"][INDEX[ALL_COMBOS[2]]] == 0  # off the range
    shove = replace(line, acts=(solve.Act("bb", "bet", 9, True, 10, 0, 0),))
    assert solve.walk(solved, shove).path == ("AllIn",)
    big = replace(line, acts=(solve.Act("bb", "bet", 70, False, 10, 0, 0),))
    assert solve.walk(solved, big).path == ("AllIn",)  # 7x the pot is nearer all-in
    raised = replace(line, acts=(line.acts[0], solve.Act("sb", "raise", 9, False, 12.5, 0, 2.5)))
    assert solve.walk(solved, raised).path == ("Bet", "AllIn")  # the nearest sized action
    reraised = replace(big, acts=(*big.acts, solve.Act("sb", "raise", 200, False, 80, 0, 70)))
    with pytest.raises(solve.NoSolve, match="left the solved tree"):
        solve.walk(solved, reraised)  # facing the tree's all-in, nothing is sized


def test_where_no_live_solve_answers_the_equity_helper_does(advisor, monkeypatch) -> None:
    d = river("hu_full_hand.phh")
    spot = d.spot()
    fixed = Advisor.load(samples=500, ranges="fixed").suggest(spot)
    assert fixed.source == "equity heuristic, not GTO; no live solve: fixed ranges"
    given = advisor.suggest(replace(spot, villain_top=30))
    assert given.source.endswith("no live solve: your range for the villain is used as given")
    limped = replace(spot, history=("preflop SB calls 0.5", "preflop BB checks", *spot.history[2:]))
    assert "not an open and a call" in advisor.suggest(limped).source
    typed = Spot.parse(
        "AhKd", "Kc7s2d9h4c", seat="sb", effective_bb=50, pot_bb=21.9, to_call_bb=5.5
    )
    assert advisor.suggest(typed).source == "equity heuristic, not GTO"  # unchanged
    flop = [x for x in hand.load(HANDS / "hu_full_hand.phh").decisions if x.street == "flop"]
    assert advisor.suggest(flop[-1].spot()).source == "equity heuristic, not GTO"
    off = Advisor.load(samples=500, live_solves=False)
    assert off.suggest(spot).source == "equity heuristic, not GTO"
    assert not off.solving(spot) and not off.solve_started(spot)
    monkeypatch.setattr(solve, "STREETS_EXE", Path("missing/streets.exe"))
    fresh = Advisor.load(samples=500)
    assert fresh.suggest(spot).source.endswith(
        "the streets bridge is not built: run `showdown postflop build`"
    )


def test_a_timed_out_turn_solve_narrows_the_turn_by_the_stopgap(monkeypatch) -> None:
    monkeypatch.setattr(solve, "TIMEOUT", {"turn": 0.001, "river": 3.0})
    fresh = Advisor.load(samples=500)
    decisions = [d for d in hand.load(HANDS / "hu_full_hand.phh").decisions if d.seat == "sb"]
    turn, last = decisions[-2], decisions[-1]
    assert fresh.suggest(turn.spot()).source.endswith(
        "no live solve: the turn solve timed out after 0.001 s"
    )
    s = fresh.suggest(last.spot())
    assert s.source.startswith(solve.SOURCE)
    assert "turn: range model (assumed; the turn solve timed out" in s.villain_range
    with pytest.raises(solve.NoSolve, match="the river solve failed"):
        solve.run({"board": "Kc"}, 10, "river")


def test_the_tracker_says_solving_before_a_solved_answer(tmp_path) -> None:
    from pokerkit import HandHistory

    shown = []
    tracker = Tracker(Advisor.load(samples=500), None, on_solving=shown.append)
    with (HANDS / "hu_full_hand.phh").open("rb") as f:
        hh = HandHistory.load(f)
    events = [
        e for fr in frames_from_history(hh, "sb", every_change=False) for e in tracker.feed(fr)
    ]
    kinds = [(e.kind, e.decision.street if e.decision else None) for e in events]
    assert kinds[:6] == [
        ("advice", "preflop"),
        ("advice", "flop"),
        ("solving", "turn"),
        ("advice", "turn"),
        ("solving", "river"),
        ("advice", "river"),
    ]
    assert [e.text for e in shown] == ["solving…", "solving…"]
    for e in events:
        if e.kind == "advice" and e.decision.street in ("turn", "river"):
            assert e.live_solve and e.since_card_ms >= e.elapsed_ms - 1e-6
            assert e.suggestion.source.startswith(solve.SOURCE)
    hero = make_combo(*parse_cards("AhKd"))
    assert solve.HAND_INDEX["AhKd"] == solve.HAND_INDEX["KdAh"] == INDEX[hero]
