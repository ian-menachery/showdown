"""Gate T bars 1, 2, 3 and 5 (DECISIONS 42): 200 simulated heads-up hands as table frames.

The hands come from tests/live_sim.py with seed 20261117. Ian is the SB in even hands and
the BB in odd ones. One tracker follows the whole session, so new hands are detected as
they would be live.
"""

import json
import os
import random
import re
import subprocess
import sys
import warnings
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from live_sim import full_history, play
from pokerkit import HandHistory

from showdown.hh.parse import load_phh
from showdown.live import hand
from showdown.live.advisor import Advisor
from showdown.live.table import frames_from_history
from showdown.live.tracker import Tracker

pytestmark = pytest.mark.slow

SEED = 20261117
HANDS = 200
LATENCY_P95_MS = 300.0


def session():
    rng = random.Random(SEED)
    for k in range(HANDS):
        state, _, actions = play(rng)
        yield k, "sb" if k % 2 == 0 else "bb", full_history(state).dumps(), actions


def _frames(text: str, hero: str, every_change: bool):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return list(frames_from_history(HandHistory.loads(text), hero, every_change=every_change))


def _betting(actions: list[str]) -> list[str]:
    """Betting actions and board cards; hole cards and show/muck lines are left out."""
    return [a for a in actions if not a.startswith("d dh") and " sm" not in a]


def test_bars_1_to_3_simulated_session(tmp_path) -> None:
    advisor = Advisor.load(samples=200)
    turns = Tracker(advisor, tmp_path / "turns")
    every = Tracker(advisor, tmp_path / "every")
    counts = {"hands": 0, "hero decisions": 0, "written (turns)": 0, "written (every)": 0}
    counts |= {"unseen sizes": 0, "seen only at the end": 0}
    for k, hero, text, actions in session():
        counts["hands"] += 1
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            replayed = hand.replay_history(HandHistory.loads(text), f"sim{k}")
        expected = [replace(d, taken=None) for d in replayed.decisions if d.seat == hero]
        counts["hero decisions"] += len(expected)

        # Bar 1: only Ian's turns and the end are seen.
        events = [e for f in _frames(text, hero, False) for e in turns.feed(f)]
        assert [e.decision for e in events if e.kind == "advice"] == expected, k
        written = [e.text for e in events if e.kind == "written"]
        if not expected and not written:
            counts["seen only at the end"] += 1  # e.g. the SB folds and Ian, the BB, never acts
        # Bar 3: whatever is written reconciles.
        for path in written:
            report = load_phh(path)
            assert report.parsed == 1, (k, report.failures)
            counts["written (turns)"] += 1
            counts["unseen sizes"] += turns.hand.unseen

        # Bar 2: every change is seen; the tracker's hand is the hand.
        events = [e for f in _frames(text, hero, True) for e in every.feed(f)]
        (path,) = [e.text for e in events if e.kind == "written"]
        report = load_phh(path)
        assert report.parsed == 1, (k, report.failures)
        counts["written (every)"] += 1
        text_out = Path(path).read_text(encoding="utf-8")
        got = re.search(r"^actions = (\[.*\])$", text_out, re.M)
        assert _betting(eval(got.group(1))) == _betting(actions), k
        assert every.hand.unseen == 0, k
    print(f"\n{counts}")
    assert counts["written (every)"] == HANDS


_LATENCY_SCRIPT = r"""
import json, random, sys, warnings
sys.path.insert(0, "tests")
from live_sim import full_history, play
from pokerkit import HandHistory
from showdown.live.advisor import Advisor
from showdown.live.table import frames_from_history
from showdown.live.tracker import Tracker
tracker = Tracker(Advisor.load(), None)
rng, times = random.Random(int(sys.argv[1])), []
for k in range(int(sys.argv[2])):
    state, _, _ = play(rng)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hh = HandHistory.loads(full_history(state).dumps())
        frames = list(frames_from_history(hh, "sb" if k % 2 == 0 else "bb"))
    for frame in frames:
        times += [e.elapsed_ms for e in tracker.feed(frame) if e.kind == "advice"]
print(json.dumps(times))
"""


def test_bar5_latency_without_coverage_tracing() -> None:
    """Frame to suggestion, every-change frames, the advisor's full sample count, timed in a
    separate process without pytest-cov's tracer (DECISIONS 32's method)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("COV_CORE")}
    out = subprocess.run(
        [sys.executable, "-c", _LATENCY_SCRIPT, str(SEED), "60"],
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
