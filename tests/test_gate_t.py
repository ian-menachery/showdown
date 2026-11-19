"""Gate T: the live tracker and overlay, from table frames (DECISIONS 42).

Fast checks on the saved hands, 3-handed frames, reading errors, the overlay and the
command. The 200 simulated hands (bars 1 to 3) and the latency (bar 5) are in
test_gate_t_slow.py.
"""

import warnings
from dataclasses import replace
from pathlib import Path

import pytest
from pokerkit import HandHistory

from showdown.cli import main
from showdown.hh.parse import load_phh
from showdown.live import hand
from showdown.live.advisor import Advisor
from showdown.live.overlay import Overlay, event_lines
from showdown.live.table import Seat, TableState, frames_from_history
from showdown.live.tracker import Event, Tracker

HANDS = Path("tests/fixtures/live/hands")
SAVED = sorted(HANDS.glob("*.phh"))


def frames(path: Path, hero: str, every_change: bool) -> list[TableState]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hh = HandHistory.load(path.open("rb"))
    return list(frames_from_history(hh, hero, every_change=every_change))


@pytest.fixture(scope="module")
def advisor() -> Advisor:
    return Advisor.load(samples=500)


@pytest.mark.parametrize("every_change", [True, False], ids=["every-change", "turns-only"])
@pytest.mark.parametrize("hero", ["sb", "bb"])
@pytest.mark.parametrize("path", SAVED, ids=[p.stem for p in SAVED])
def test_saved_hands_track_like_the_replay(path, hero, every_change, advisor, tmp_path) -> None:
    tracker = Tracker(advisor, tmp_path)
    events = [e for f in frames(path, hero, every_change) for e in tracker.feed(f)]
    expected = [replace(d, taken=None) for d in hand.load(path).decisions if d.seat == hero]
    advised = [e.decision for e in events if e.kind == "advice"]
    assert advised == expected
    (written,) = [e.text for e in events if e.kind == "written"]
    report = load_phh(written)
    assert report.parsed == 1, report.failures


def three_handed() -> list[TableState]:
    """20 frames from 3-handed hands, Ian at seat 2."""
    out = []
    for k in range(5):
        cards = ["AhKd", "QsQc", "7h6h", "JdTd", "9c9s"][k]

        def seat(i, bet, in_hand=True, cards=cards):
            return Seat(f"p{i}", 1000 - bet, bet, in_hand, cards if i == 2 else None)

        common = {"hero": 2, "button": 0, "big_blind": 10, "small_blind": 5}
        out += [
            TableState((seat(0, 0), seat(1, 5), seat(2, 10)), to_act=0, **common),
            TableState((seat(0, 30), seat(1, 5), seat(2, 10)), to_act=2, **common),
            TableState(
                (seat(0, 30), seat(1, 5, False), seat(2, 30)), to_act=None, board="Kc7s2d", **common
            ),
            TableState(
                (seat(0, 30), seat(1, 5, False), seat(2, 30)), to_act=None, ended=True, **common
            ),
        ]
    return out


def test_bar4_three_handed_gives_no_suggestion(advisor, tmp_path) -> None:
    tracker = Tracker(advisor, tmp_path)
    frames3 = three_handed()
    assert len(frames3) == 20
    events = [e for f in frames3 for e in tracker.feed(f)]
    assert [e.kind for e in events] == ["no suggestion"] * 5
    assert all(e.text == "no suggestion: 3 players dealt in" for e in events)
    assert not list(tmp_path.iterdir())


def test_unexplained_frames_and_mid_hand_joins(advisor) -> None:
    full = frames(HANDS / "hu_full_hand.phh", "sb", every_change=False)
    tracker = Tracker(advisor, None)
    tracker.feed(full[0])
    bad = full[1]
    seats = (replace(bad.seats[0], stack=bad.seats[0].stack + 7), bad.seats[1])
    (event,) = tracker.feed(replace(bad, seats=seats))
    assert event.kind == "error" and "no legal sequence" in event.text
    (later,) = tracker.feed(full[2])  # the rest of that hand gets no suggestion, with why
    assert later.kind == "no suggestion" and "reading error" in later.text
    late = Tracker(advisor, None)
    (event,) = late.feed(full[1])
    assert event.kind == "no suggestion" and event.text == "no suggestion: joined mid-hand"
    unfinished = Tracker(advisor, None)
    unfinished.feed(full[0])
    nxt = frames(HANDS / "hu_short_stack_river.phh", "sb", every_change=False)[0]
    assert unfinished.feed(nxt)[0].kind == "not written"


def test_frames_round_trip_as_json() -> None:
    for frame in frames(HANDS / "hu_river_shove.phh", "bb", every_change=True):
        assert TableState.from_json(frame.to_json()) == frame


def test_bar6_overlay_shows_advice_and_no_suggestion() -> None:
    # Live solves off (DECISIONS 47): this bar tests the window, so its recorded text stays.
    tracker = Tracker(Advisor.load(samples=500, live_solves=False), None)
    events = [
        e for f in frames(HANDS / "hu_short_stack_river.phh", "sb", False) for e in tracker.feed(f)
    ]
    river = [e for e in events if e.kind == "advice"][-1]
    overlay = Overlay()
    try:
        overlay.show(river)
        head, detail, state = overlay.texts()
        assert head == "ALL-IN 2.5 bb"
        assert "bet 33.75 bb is more than can be matched: all-in" in detail
        assert state.startswith("river  pot 45  to call 0  you 2.5")
        overlay.show(Event("no suggestion", "no suggestion: 3 players dealt in"))
        assert overlay.texts() == ("no suggestion: 3 players dealt in", "", "")
        assert overlay.root.attributes("-topmost") == 1
    finally:
        overlay.close()
    assert event_lines(Event("error", "reading error: x")) == ("reading error: x", [], "")


def test_live_command(capsys, tmp_path) -> None:
    hand_path = str(HANDS / "hu_full_hand.phh")
    assert main(["live", "--replay", hand_path, "--hero", "sb", "--no-window"]) == 0
    out = capsys.readouterr().out
    assert out.count("[advice]") == 4 and "RAISE 2.5 bb" in out
    recorded = tmp_path / "frames.jsonl"
    recorded.write_text(
        "\n".join(f.to_json() for f in frames(HANDS / "hu_full_hand.phh", "bb", True)),
        encoding="utf-8",
    )
    assert main(["live", "--replay", str(recorded), "--no-window", "--turns-only"]) == 0
    assert capsys.readouterr().out.count("[advice]") == 5
    with pytest.raises(SystemExit, match="needs --hero"):
        main(["live", "--replay", hand_path, "--no-window"])
