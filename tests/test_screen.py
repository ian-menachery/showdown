"""`showdown live --screen`'s loop, with fake images and a fake reader (DECISIONS 52).

The reader (S1) doesn't exist yet. Each fake PNG names a frame from Gate T's saved hands,
a reading error, or a crash.
"""

import io
import json
import warnings
from pathlib import Path

import pytest
from pokerkit import HandHistory

from showdown.cli import main
from showdown.live import screen
from showdown.live.advisor import Advisor
from showdown.live.table import ReadError, TableState, frames_from_history
from showdown.live.tracker import Tracker

HAND = Path("tests/fixtures/live/hands/hu_full_hand.phh")


def hand_frames(hero: str = "sb") -> list[TableState]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hh = HandHistory.load(HAND.open("rb"))
    return list(frames_from_history(hh, hero))


FRAMES = hand_frames()


class FakeReader:
    """b"f3" reads as FRAMES[3], b"err:why" as ReadError("why"), b"boom" raises. Anything
    after a "#" changes the image but not the read."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, png: bytes):
        self.calls += 1
        text = png.decode().split("#")[0]
        if text == "boom":
            raise RuntimeError("reader bug")
        if text.startswith("err:"):
            return ReadError(text[4:])
        return FRAMES[int(text[1:])]


@pytest.fixture(scope="module")
def advisor() -> Advisor:
    return Advisor.load(samples=500, live_solves=False)


def make_loop(advisor, tmp_path, shown=None):
    log = io.StringIO()
    loop = screen.ScreenLoop(
        FakeReader(),
        Tracker(advisor, tmp_path / "hands"),
        (shown if shown is not None else []).append,
        log,
        tmp_path / "shots",
    )
    return loop, log


def feed(loop, pngs: list[bytes]) -> list:
    return [e for i, png in enumerate(pngs) for e in loop.tick(png, i * screen.PERIOD)]


def lines(log) -> list[dict]:
    return [json.loads(line) for line in log.getvalue().splitlines()]


def test_every_decision_comes_through_and_its_png_is_saved(advisor, tmp_path) -> None:
    direct = Tracker(advisor, None)
    expected = [e.decision for f in FRAMES for e in direct.feed(f) if e.kind == "advice"]
    loop, log = make_loop(advisor, tmp_path)
    pngs = [f"f{i}".encode() for i in range(len(FRAMES)) for _ in range(2)]
    events = feed(loop, pngs)
    assert loop.reader.calls == len(FRAMES)  # each second image is unchanged: not read again
    assert [e.decision for e in events if e.kind == "advice"] == expected
    assert [e.kind for e in events if e.kind == "written"] == ["written"]
    hero_turns = sum(f.to_act == f.hero and not f.ended for f in FRAMES)
    saved = sorted((tmp_path / "shots").iterdir())
    assert len(saved) == hero_turns and saved[0].read_bytes().startswith(b"f")
    logged = lines(log)
    assert [TableState.from_json(json.dumps(x["frame"])) for x in logged if "frame" in x] == FRAMES
    advice = [x for x in logged if x["kind"] == "advice"]
    assert len(advice) == len(expected) and all(Path(x["png"]).exists() for x in advice)
    assert all(x["latency_ms"] >= 0 and x["hand"] == 1 for x in advice)
    assert [x["actions_before"] for x in advice] == [len(d.history) for d in expected]


def test_a_frame_read_once_never_reaches_the_tracker(advisor, tmp_path) -> None:
    loop, log = make_loop(advisor, tmp_path)
    # FRAMES[5] seen once between FRAMES[0] and FRAMES[1]: an animation. Fed, it would be
    # a jump the tracker may still explain, so check the frames fed instead.
    feed(loop, [b"f0", b"f0", b"f5", b"f1", b"f1#again"])
    fed = [x["frame"] for x in lines(log) if x["kind"] == "frame"]
    assert fed == [json.loads(FRAMES[0].to_json()), json.loads(FRAMES[1].to_json())]
    assert loop.reader.calls == 4  # f0, f5, f1, f1#again: a changed image is read again


def test_reading_errors_are_shown_once_per_change_and_never_fed(advisor, tmp_path) -> None:
    shown = []
    loop, log = make_loop(advisor, tmp_path, shown)
    feed(loop, [b"err:x", b"err:x", b"err:x", b"f0", b"f0", b"err:x", b"err:x#2", b"err:y"])
    errors = [x for x in lines(log) if x["kind"] == "read error"]
    assert [x["text"] for x in errors] == ["x", "x"]
    assert all(Path(x["png"]).name.endswith("-error.png") for x in errors)
    assert [e.text for e in shown if "error" in e.text] == ["no suggestion: reading error: x"] * 2
    assert loop.tracker.last == FRAMES[0]


def test_a_crash_is_logged_and_the_next_capture_still_works(advisor, tmp_path) -> None:
    shown = []
    loop, log = make_loop(advisor, tmp_path, shown)
    feed(loop, [b"boom", b"f0", b"f0"])
    (crash,) = [x for x in lines(log) if x["kind"] == "crash"]
    assert "reader bug" in crash["text"] and shown[0].text == "crash: see the session log"
    assert loop.tracker.last == FRAMES[0]


def test_a_crash_in_the_tracker_abandons_the_hand(advisor, tmp_path, monkeypatch) -> None:
    loop, log = make_loop(advisor, tmp_path)
    feed(loop, [b"f0", b"f0"])

    def broken(frame):
        raise RuntimeError("tracker bug")

    monkeypatch.setattr(loop.tracker, "feed", broken)
    feed(loop, [b"f1", b"f1"])
    assert loop.tracker.hand.ignored.startswith("crash")
    assert [x["kind"] for x in lines(log)][-1] == "crash"


def test_latency_runs_from_the_first_of_the_two_captures(advisor, tmp_path) -> None:
    times = iter(range(100, 10_000))

    def clock() -> float:  # 1 ms a call, from 0.1 s
        return next(times) / 1000

    log = io.StringIO()
    loop = screen.ScreenLoop(FakeReader(), Tracker(advisor, None), lambda e: None, log, None, clock)
    turn = next(i for i, f in enumerate(FRAMES) if f.to_act == f.hero)
    for i in range(turn + 1):
        loop.tick(f"f{i}".encode(), 0.0)
        loop.tick(f"f{i}".encode(), 0.0)
    (advice,) = [x for x in lines(log) if x["kind"] == "advice"]
    assert 100 <= advice["latency_ms"] < 10_000 and advice["png"] is None
    loop.close()
    stopped = lines(log)[-1]
    assert stopped["kind"] == "stopped" and stopped["reads"] == turn + 1


def test_only_the_locked_window_is_captured_while_in_front() -> None:
    front, grabbed = [7], []
    titles = {7: ("Poker Now - Google Chrome", (0, 0, 800, 600))}
    poll = screen.locked_window(
        7, lambda: front[0], titles.get, lambda r: grabbed.append(r) or b"png"
    )
    assert poll() == b"png" and grabbed == [(0, 0, 800, 600)]
    front[0] = 8  # the opponent's window, or anything else
    assert poll() is None
    front[0] = 7
    titles[7] = ("Inbox - Gmail - Google Chrome", (0, 0, 800, 600))
    assert poll() is None
    titles[7] = ("Poker Now", (0, 0, 0, 0))  # minimised
    assert poll() is None and len(grabbed) == 1


def test_the_loop_locks_onto_the_first_poker_now_window_in_front() -> None:
    fronts = iter([3, 4, 5])
    windows = {
        3: ("Inbox", (0, 0, 9, 9)),
        4: ("Poker Now", (0, 0, 0, 0)),
        5: ("Poker Now", (1, 2, 3, 4)),
    }
    waits = []
    assert screen.wait_for_poker_now(lambda: next(fronts), windows.get, waits.append) == (
        5,
        (1, 2, 3, 4),
    )
    assert waits == [screen.PERIOD] * 2


def test_the_overlay_goes_beside_the_table() -> None:
    assert screen.overlay_xy((0, 0, 1200, 900), 1920) == (1200, 0)
    x, y = screen.overlay_xy((0, 0, 1920, 1080), 1920)
    assert x == 1920 - screen.OVERLAY_WIDTH and y == screen.BROWSER_BARS


def test_run_captures_every_250_ms_and_skips_when_nothing_is_in_front() -> None:
    now = [0.0]
    ticks, waits = [], []
    pngs = iter([b"a", None, b"b"])

    class Loop:
        def tick(self, png, grabbed):
            ticks.append((png, grabbed))
            now[0] += 0.1 if png == b"a" else 0.4  # b"b" overruns its 250 ms

    def poll():
        try:
            return next(pngs)
        except StopIteration:
            raise KeyboardInterrupt from None

    def wait(seconds):
        waits.append(round(seconds, 9))
        now[0] += seconds

    with pytest.raises(KeyboardInterrupt):
        screen.run(Loop(), poll, wait, clock=lambda: now[0])
    assert ticks == [(b"a", 0.0), (b"b", 0.5)]
    assert waits == [0.15, 0.25, 0.0]


def test_live_needs_a_source_and_the_screen_needs_the_reader(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["live"])
    with pytest.raises(SystemExit, match="screen reader"):
        main(["live", "--screen"])
