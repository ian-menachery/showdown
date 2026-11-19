"""Gate R: a saved heads-up hand replayed with advice at each decision (DECISIONS 41).

Bars 1, 2 (saved hands) and 4 run here; bar 3, with bar 2 on its simulated hands, is in
test_gate_r_slow.py. Bar 5 is the rest of the suite passing unchanged.
"""

import re
from pathlib import Path

import pytest

from showdown import preflop_model as pm
from showdown.cli import main
from showdown.hh.replay import ReplayError
from showdown.live import hand
from showdown.live.advisor import Advisor, Suggestion, _legalize
from showdown.live.spot import Legal, Spot

HANDS = Path("tests/fixtures/live/hands")
SAVED = sorted(HANDS.glob("*.phh"))


def tally(text: str) -> list[tuple[float, dict[str, float]]]:
    """The pot and both stacks after every player action, counted from the PHH text alone.

    Heads-up PHH: p1 is the BB and posts the larger blind, p2 the SB (pokerkit's order).
    """
    fields = dict(re.findall(r"^(\w+) = (.+)$", text, re.M))
    blinds = [float(x) for x in re.findall(r"[\d.]+", fields["blinds_or_straddles"])]
    stacks = [float(x) for x in re.findall(r"[\d.]+", fields["starting_stacks"])]
    big = max(blinds)
    bets = [max(blinds), min(blinds)]
    stacks = [stacks[0] - bets[0], stacks[1] - bets[1]]
    pot = sum(bets)
    out = []
    for action in re.findall(r"'([^']+)'", fields["actions"]):
        parts = action.split()
        if parts[0] == "d":
            if parts[1] == "db":
                bets = [0.0, 0.0]
            continue
        i, verb = int(parts[0][1]) - 1, parts[1]
        if verb == "sm":
            continue
        if verb == "cbr":
            added = float(parts[2]) - bets[i]
        elif verb == "cc":
            added = min(max(bets) - bets[i], stacks[i])
        else:  # a fold
            added = 0.0
        bets[i] += added
        stacks[i] -= added
        pot += added
        out.append((pot / big, {"bb": stacks[0] / big, "sb": stacks[1] / big}))
    return out


def check_reconciles(replayed: hand.HandReplay, text: str) -> None:
    expected = tally(text)
    assert len(expected) == len(replayed.steps)
    for step, (pot, stacks) in zip(replayed.steps, expected, strict=True):
        assert step.pot_bb == pytest.approx(pot, abs=1e-9), step.move
        assert step.stacks_bb["bb"] == pytest.approx(stacks["bb"], abs=1e-9), step.move
        assert step.stacks_bb["sb"] == pytest.approx(stacks["sb"], abs=1e-9), step.move
        total = step.pot_bb + sum(step.stacks_bb.values())
        assert total == pytest.approx(replayed.total_bb, abs=1e-9), step.move


@pytest.fixture(scope="module")
def advisor() -> Advisor:
    return Advisor.load()


def test_bar1_full_hand_has_advice_on_every_street(advisor) -> None:
    replayed = hand.load(HANDS / "hu_full_hand.phh")
    mine = [d for d in replayed.decisions if d.seat == "sb"]
    assert {d.street for d in mine} == set(hand.STREETS)
    for d in mine:
        s = advisor.suggest(d.spot())
        assert s.action is not None, d
        print(f"{d.street}: {s.action} {s.size_bb or ''}  (did: {d.taken})")
    assert [d.preflop_decision for d in replayed.decisions if d.street == "preflop"] == [
        "sb_first",
        "bb_vs_raise",
    ]
    assert all(d.pot_type == ("srp", None) for d in mine if d.street != "preflop")


@pytest.mark.parametrize("path", SAVED, ids=[p.stem for p in SAVED])
def test_bar2_saved_hands_reconcile(path) -> None:
    check_reconciles(hand.load(path), path.read_text(encoding="utf-8"))


def test_bar4_no_bet_beyond_the_stack(advisor) -> None:
    replayed = hand.load(HANDS / "hu_short_stack_river.phh")
    (river,) = [d for d in replayed.decisions if d.seat == "sb" and d.street == "river"]
    assert (river.pot_bb, river.stacks_bb["sb"], river.to_call_bb) == (45.0, 2.5, 0.0)
    s = advisor.suggest(river.spot())
    print(s)
    assert (s.action, s.size_bb) in {("all-in", 2.5), ("check", None)}
    for d in replayed.decisions:
        size = advisor.suggest(d.spot()).size_bb
        assert size is None or size <= d.legal.cap_bb + 1e-9


def test_the_river_lines_differ_only_in_the_bet() -> None:
    # Gate N's bar 1 reads model ranges, so it is pinned to DECISIONS 34's model (DECISIONS 49).
    advisor = Advisor.load(pm.v1_model_path())
    third = hand.load(HANDS / "hu_full_hand.phh").decisions[-1]
    shove = hand.load(HANDS / "hu_river_shove.phh").decisions[-1]
    assert third.history[:-1] == shove.history[:-1] and third.board == shove.board
    assert (third.to_call_bb, shove.to_call_bb) == (5.5, 41.8)
    a, b = third.spot(), shove.spot()
    assert a.history != b.history
    # Gate N bar 1 (DECISIONS 46): the villain's moves narrow its range, so the two lines
    # reach the equity calculation with different ranges.
    va, vb = advisor.villain(a), advisor.villain(b)
    assert va.combos == vb.combos and va.weights != vb.weights
    assert "range model (assumed, not solved)" in va.label
    for name, spot, v in (("third of the pot", a, va), ("shove", b, vb)):
        s = advisor.suggest(spot)
        print(f"{name}: weight {sum(v.weights):.4f}, equity {s.equity:.1%}, {s.action}")


def test_the_river_trace_shows_two_fingerprints(capsys) -> None:
    prints = []
    for name in ("hu_full_hand.phh", "hu_river_shove.phh"):
        main(["replay", str(HANDS / name), "--hero", "sb", "--trace"])
        prints.append(re.findall(r"fingerprint (\w+)", capsys.readouterr().out)[-1])
    assert prints[0] != prints[1], prints


def test_legalize_branches() -> None:
    def spot(**legal) -> Spot:
        return Spot.parse("AhKd", "Kc7s2d", seat="sb", effective_bb=50, legal=Legal(**legal))

    def run(action, size=None, **legal) -> Suggestion:
        return _legalize(Suggestion(street="flop", action=action, size_bb=size), spot(**legal))

    open_ = {"to_call_bb": 0.0, "raise_min_bb": 1.0, "raise_max_bb": 40.0, "cap_bb": 30.0}
    assert run("fold", **open_).action == "check"
    assert run("call", **open_).action == "check"
    assert (run("bet", 0.5, **open_).size_bb, run("bet", 99, **open_).action) == (1.0, "all-in")
    assert run("bet", 99, **open_).size_bb == 30.0
    assert run("bet", 5, **open_).size_bb == 5
    short = {"to_call_bb": 2.0, "raise_min_bb": 4.0, "raise_max_bb": 40.0, "cap_bb": 3.0}
    assert run("raise", 10, **short).action == "call"
    assert run("check", to_call_bb=2.0).action == "call"
    allin = _legalize(
        Suggestion(street="river", action="call"),
        Spot.parse(
            "AhKd",
            "Kc7s2d9h4c",
            seat="sb",
            effective_bb=50,
            stack_behind_bb=2.0,
            legal=Legal(to_call_bb=2.0),
        ),
    )
    assert "calling puts you all-in" in allin.notes
    assert _legalize(Suggestion(street="flop", action=None), spot(**open_)).action is None


def test_replay_command_and_errors(capsys, tmp_path) -> None:
    assert main(["replay", str(HANDS / "hu_full_hand.phh"), "--hero", "sb", "--trace"]) == 0
    out = capsys.readouterr().out
    assert out.count("advice:") == 4 and "preflop decision (from the action): sb_first" in out
    assert "trace: range into the equity calculation" in out
    assert main(["replay", str(HANDS / "hu_short_stack_river.phh"), "--hero", "bb"]) == 0
    assert "you did: river BB calls 2.5 (all-in)" in capsys.readouterr().out
    three = tmp_path / "three.phh"
    three.write_text(
        (HANDS / "hu_full_hand.phh")
        .read_text(encoding="utf-8")
        .replace("[5, 10]", "[5, 10, 0]")
        .replace("[0, 0]", "[0, 0, 0]")
        .replace("[500, 500]", "[500, 500, 500]"),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="heads-up only: 3 players"):
        main(["replay", str(three), "--hero", "sb"])
    with pytest.raises(ReplayError, match="heads-up only"):
        hand.load(three)
