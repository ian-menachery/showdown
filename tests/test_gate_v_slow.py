"""Gate V bars 2 to 4 (DECISIONS 47): live solves over Gate R bar 3's 500 simulated hands.

Bars 2 and 3 replay the hands and advise both players, as Gate R bar 3 does. Bar 3 checks
the first 40 solved answers against a second run of the streets bridge. Bar 4 feeds the same
hands to the tracker as every-change frames, Ian alternately the SB and the BB, timed in a
separate process without coverage (DECISIONS 32's method).
"""

import json
import os
import random
import re
import subprocess
import sys
import warnings
from collections import Counter

import numpy as np
import pytest
from pokerkit import HandHistory
from test_gate_r_slow import HANDS, SEED, simulate

from showdown.equity.cards import make_combo, parse_cards
from showdown.live import hand, solve
from showdown.live.advisor import RAISES, Advisor

pytestmark = pytest.mark.slow

BAR3_SPOTS = 40
BAR2_MIN = 100
BAR4_MIN = 30
P95_S = {"turn": 3.0, "river": 1.0}
FIXES = ("fits the legal sizes", "more than can be matched", "is not legal here", "not fold")
"""DECISIONS 41's notes when the legality rule changes an action."""


@pytest.fixture(scope="module")
def replayed():
    """(the advisor, every solved (hand, decision, spot, suggestion), fallback reasons)."""
    advisor = Advisor.load(samples=500)
    rng = random.Random(SEED)
    solved, fallbacks = [], Counter()
    for k in range(HANDS):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            replay = hand.replay_history(HandHistory.loads(simulate(rng)), f"sim{k}")
        for d in replay.decisions:
            spot = d.spot()
            s = advisor.suggest(spot)
            if d.street not in ("turn", "river"):
                continue
            if s.source.startswith(solve.SOURCE):
                solved.append((k, d, spot, s))
            else:
                fallbacks[re.sub(r"[\d.]+", "N", s.source.split("no live solve: ")[-1])] += 1
    return advisor, solved, fallbacks


def test_bar2_every_solved_suggestion_is_legal(replayed) -> None:
    _, solved, fallbacks = replayed
    counts, fixes, mapped, seconds = Counter(), 0, 0, {"turn": [], "river": []}
    for k, d, _, s in solved:
        legal, why = d.legal, (k, d.seat, d.street, d.legal, s)
        counts[(d.street, s.action)] += 1
        fixes += any(f in n for n in s.notes for f in FIXES)
        mapped += any("solved as the tree's" in n for n in s.notes)
        seconds[d.street].append(float(re.search(r"solve ([\d.]+) s", s.source).group(1)))
        if s.action in ("fold", "call"):
            assert legal.to_call_bb > 0, why
        elif s.action == "check":
            assert legal.to_call_bb == 0, why
        else:
            assert s.action in RAISES and legal.can_raise, why
            assert legal.raise_min_bb - 1e-9 <= s.size_bb <= legal.raise_max_bb + 1e-9, why
            assert s.size_bb <= legal.cap_bb + 1e-9, why
    print(f"\n{len(solved)} solved suggestions: {dict(sorted(counts.items()))}")
    print(f"legality fixes {fixes}; with an off-tree size mapped {mapped}")
    for street, xs in seconds.items():
        print(f"{street} solves: median {np.median(xs):.2f} s, max {max(xs):.2f} s ({len(xs)})")
    print(f"fallbacks on the turn and river: {dict(fallbacks.most_common())}")
    assert len(solved) >= BAR2_MIN


def _shown(action: str) -> str:
    return solve.SHOWN[re.match(r"\w+", action).group(0)]


def test_bar3_the_advice_is_the_bridges_own_strategy(replayed) -> None:
    advisor, solved, _ = replayed
    assert len(solved) >= BAR3_SPOTS
    fixed = 0
    for k, d, spot, s in solved[:BAR3_SPOTS]:
        answer = advisor.solves.answer(spot)  # the spec it sent and the node it read
        out = solve.run({**answer.spec, "report": [list(answer.path)]}, 120, d.street)
        (report,) = out["reports"]
        assert report["reached"] and report["player"] == (0 if d.seat == "bb" else 1), k
        hands = [make_combo(*parse_cards(h)) for h in report["hands"]]
        i = hands.index(spot.hero)
        n = len(hands)
        row = [report["strategy"][a * n + i] for a in range(len(report["actions"]))]
        names = [_shown(a) for a in report["actions"]]
        assert list(s.mix) == names, (k, s.mix, names)
        assert np.allclose(list(s.mix.values()), row, rtol=0, atol=1e-6), (k, s.mix, row)
        top = names[int(np.argmax(row))]
        if s.action != top:
            assert any(f in note for note in s.notes for f in FIXES), (k, s, top)
            fixed += 1
        print(f"hand {k} {d.seat} {d.street} {answer.path}: {s.action} {s.mix}")
    print(f"{BAR3_SPOTS} spots; the legality rule changed {fixed} actions")


_LATENCY_SCRIPT = r"""
import json, random, sys, warnings
sys.path.insert(0, "tests")
from live_sim import full_history, play
from pokerkit import HandHistory
from showdown.live.advisor import Advisor
from showdown.live.table import frames_from_history
from showdown.live.tracker import Tracker
tracker = Tracker(Advisor.load(), None)
rng, out = random.Random(int(sys.argv[1])), []
for k in range(int(sys.argv[2])):
    state, _, _ = play(rng)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hh = HandHistory.loads(full_history(state).dumps())
        frames = list(frames_from_history(hh, "sb" if k % 2 == 0 else "bb"))
    for frame in frames:
        for e in tracker.feed(frame):
            if e.kind == "advice" and e.live_solve:
                out.append([e.decision.street, e.since_card_ms, e.suggestion.source])
print(json.dumps(out))
"""


def test_bar4_latency_from_the_card() -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("COV_CORE")}
    out = subprocess.run(
        [sys.executable, "-c", _LATENCY_SCRIPT, str(SEED), str(HANDS)],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    ).stdout
    rows = json.loads(out)
    fallbacks = Counter(
        source.split("no live solve: ")[-1] for _, _, source in rows if "no live" in source
    )
    print(f"\n{len(rows)} decisions with a live solve started; fallbacks {dict(fallbacks)}")
    for street, bar in P95_S.items():
        times = [ms / 1000 for s, ms, _ in rows if s == street]
        assert len(times) >= BAR4_MIN, (street, len(times))
        p95 = float(np.percentile(times, 95))
        print(
            f"{street}: {len(times)}, median {np.median(times):.2f} s, "
            f"95th percentile {p95:.2f} s, max {max(times):.2f} s (bar {bar:g} s)"
        )
        assert p95 <= bar
