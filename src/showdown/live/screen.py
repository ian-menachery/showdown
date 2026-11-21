"""`showdown live --screen`: the Poker Now window, read every 250 ms, into the tracker
(DECISIONS 52).

The reader is S1's, `read(png) -> TableState | ReadError`. This loop decides which reads
reach the tracker, saves the session log and the images of Ian's decisions, and feeds the
overlay. It reads one locked window, only while it is in front; it never clicks.
"""

from __future__ import annotations

import json
import time
import traceback
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import TextIO

import numpy as np

from showdown.live import capture
from showdown.live.table import ReadError, TableState
from showdown.live.tracker import Event, Tracker

PERIOD = 0.25
SESSIONS_DIR = Path("data/live/sessions")
SHOTS_DIR = Path("data/live/decisions")
OVERLAY_WIDTH, BROWSER_BARS = 420, 120
"""The overlay's nominal width, and how far below a window's top its corner sits when it
goes inside the window (under Chrome's tab strip and address bar). Ian can drag it."""

Reader = Callable[[bytes], TableState | ReadError]
Poll = Callable[[], bytes | None]


class ScreenLoop:
    """Feed it each capture; it passes the tracker only frames read the same twice."""

    def __init__(
        self,
        reader: Reader,
        tracker: Tracker,
        show: Callable[[Event], None],
        log: TextIO | None = None,
        shots: Path | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.reader, self.tracker, self.show = reader, tracker, show
        self.log, self.shots, self.clock = log, shots, clock
        self.png: bytes | None = None
        self.result: TableState | ReadError | None = None
        """The last capture's read, and when the first capture of that read was taken."""
        self.first_at = 0.0
        self.settled: TableState | ReadError | None = None
        self.fed: TableState | None = None
        self.hand_no, self.saved = 0, 0
        self.card_first: float | None = None
        """When the first capture of the frame that showed the latest card was taken."""
        self.read_ms: list[float] = []

    def tick(self, png: bytes, grabbed: float) -> list[Event]:
        """One capture, taken at `grabbed` on `clock`. An exception is logged as a crash
        line, so the loop goes on."""
        try:
            return self._tick(png, grabbed)
        except Exception:
            self._line(kind="crash", text=traceback.format_exc())
            event = Event("error", "crash: see the session log")
            self.show(event)
            return [event]

    def _tick(self, png: bytes, grabbed: float) -> list[Event]:
        if png != self.png:  # an unchanged image counts as the same read
            start = self.clock()
            result = self.reader(png)
            self.read_ms.append((self.clock() - start) * 1000)
            self.png = png
        else:
            result = self.result
        if result != self.result:
            self.result, self.first_at = result, grabbed
            return []  # read once: it may be an animation
        if result == self.settled:
            return []
        self.settled = result
        if isinstance(result, ReadError):
            event = Event("no suggestion", f"no suggestion: reading error: {result.reason}")
            self.show(event)
            self._line(kind="read error", text=result.reason, png=self._save(png, "error"))
            return [event]
        if result == self.fed:
            return []
        return self._feed(result, png)

    def _feed(self, frame: TableState, png: bytes) -> list[Event]:
        first_at = self.first_at
        decision_png = None
        if frame.to_act == frame.hero and not frame.ended:
            decision_png = self._save(png, "decision")
        before, board = self.tracker.hand, len(self.fed.board) if self.fed else 0
        self.fed = frame
        try:
            events = self.tracker.feed(frame)  # shows "solving…" itself (on_solving)
        except Exception:
            if self.tracker.hand is not None:  # its state may be half-updated
                self.tracker.hand.ignored = "crash: see the session log"
            raise
        finally:
            if self.tracker.hand is not before:
                self.hand_no += 1
                self.card_first, board = None, 0
        if len(frame.board) > board:
            self.card_first = first_at
        captured = datetime.now() - timedelta(seconds=self.clock() - first_at)
        self._line(
            kind="frame",
            captured=captured.isoformat(timespec="milliseconds"),
            frame=json.loads(frame.to_json()),
        )
        for event in events:
            if event.kind != "solving":
                self.show(event)
            shown = self.clock()
            line = {"kind": event.kind, "text": event.text}
            if event.decision is not None:
                d = event.decision
                line["decision"] = {
                    "street": d.street,
                    "seat": d.seat,
                    "pot_bb": d.pot_bb,
                    "to_call_bb": d.to_call_bb,
                    "stacks_bb": d.stacks_bb,
                    "history": [str(m) for m in d.history],
                }
                line["actions_before"] = len(d.history)
                line["png"] = decision_png
            if event.suggestion is not None:
                line["suggestion"] = event.suggestion.as_dict()
                line["latency_ms"] = (shown - first_at) * 1000
                line["since_card_ms"] = event.since_card_ms
                line["live_solve"] = event.live_solve
                if event.since_card_ms is not None and self.card_first is not None:
                    line["card_capture_ms"] = (shown - self.card_first) * 1000
            self._line(**line)
        return events

    def _save(self, png: bytes, what: str) -> str | None:
        if self.shots is None:
            return None
        self.shots.mkdir(parents=True, exist_ok=True)
        self.saved += 1
        path = self.shots / f"{self.hand_no:04d}-{self.saved:05d}-{what}.png"
        path.write_bytes(png)
        return str(path)

    def _line(self, **fields) -> None:
        if self.log is None:
            return
        line = {"t": datetime.now().isoformat(timespec="milliseconds"), "hand": self.hand_no}
        self.log.write(json.dumps({**line, **fields}) + "\n")
        self.log.flush()

    def close(self) -> None:
        """The read times, for Gate H's report."""
        ms = self.read_ms
        self._line(
            kind="stopped",
            reads=len(ms),
            read_ms_median=float(np.median(ms)) if ms else None,
            read_ms_p95=float(np.percentile(ms, 95)) if ms else None,
        )


def locked_window(
    hwnd: int,
    front: Callable[[], int],
    window: Callable[[int], tuple[str, capture.Rect]],
    grab: Callable[[capture.Rect], bytes],
) -> Poll:
    """A capture of the locked window, or None when it isn't in front or isn't showing
    Poker Now (another tab, or minimised)."""

    def poll() -> bytes | None:
        if front() != hwnd:
            return None
        title, rect = window(hwnd)
        if not capture.is_poker_now(title) or rect[2] <= 0 or rect[3] <= 0:
            return None
        return grab(rect)

    return poll


def wait_for_poker_now(
    front: Callable[[], int],
    window: Callable[[int], tuple[str, capture.Rect]],
    wait: Callable[[float], None],
) -> tuple[int, capture.Rect]:
    """The handle and frame of the first Poker Now window seen in front."""
    while True:
        hwnd = front()
        title, rect = window(hwnd)
        if capture.is_poker_now(title) and rect[2] > 0 and rect[3] > 0:
            return hwnd, rect
        wait(PERIOD)


def overlay_xy(window: capture.Rect, screen_width: int) -> tuple[int, int]:
    """Beside the table: right of the window if the screen has room, else inside its
    top-right corner."""
    left, top, width, _ = window
    if left + width + OVERLAY_WIDTH <= screen_width:
        return left + width, top
    return left + width - OVERLAY_WIDTH, top + BROWSER_BARS


def run(
    loop: ScreenLoop,
    poll: Poll,
    wait: Callable[[float], None],
    clock: Callable[[], float] = time.perf_counter,
) -> None:
    """Capture every PERIOD seconds until Ctrl+C. A capture that overruns (a slow read, a
    live solve) moves the next one to now."""
    next_at = clock()
    while True:
        grabbed = clock()
        png = poll()
        if png is not None:
            loop.tick(png, grabbed)
        now = clock()
        next_at = max(next_at + PERIOD, now)
        wait(next_at - now)
