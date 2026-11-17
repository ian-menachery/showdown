"""Gate R bar 3, with bar 2 on the same hands (DECISIONS 41): legality over 500 simulated hands.

pokerkit plays 500 seeded heads-up hands with random legal actions, at stacks of 10 to 100
bb each. Cards come from a seeded shuffle and sizes are drawn between pokerkit's minimum and
maximum. Each hand is written as PHH, replayed, and every decision is advised for the
player to act. The flop's Monte Carlo uses 500 samples, which cannot change legality.
"""

import random
import time
import warnings

import pytest
from live_sim import phh_text, play
from pokerkit import HandHistory
from test_gate_r import check_reconciles

from showdown.live import hand
from showdown.live.advisor import RAISES, Advisor
from showdown.live.spot import SpotError

pytestmark = pytest.mark.slow

SEED = 20261116
HANDS = 500


def simulate(rng: random.Random) -> str:
    """One random heads-up hand as PHH text (tests/live_sim.py)."""
    _, stacks, actions = play(rng)
    return phh_text(stacks, actions)


def test_bar3_every_suggestion_is_legal() -> None:
    advisor = Advisor.load(samples=500)
    rng = random.Random(SEED)
    counts = {"decisions": 0, "no suggestion": 0}
    start = time.perf_counter()
    for k in range(HANDS):
        with warnings.catch_warnings():  # pokerkit warns that our seeded cards aren't its deck's
            warnings.simplefilter("ignore")
            text = simulate(rng)
            replayed = hand.replay_history(HandHistory.loads(text), f"sim{k}")
        check_reconciles(replayed, text)
        for d in replayed.decisions:
            try:
                s = advisor.suggest(d.spot())
            except SpotError as error:
                pytest.fail(f"hand {k}, {d.seat} {d.street}: {error}")
            counts["decisions"] += 1
            legal, why = d.legal, (k, d.seat, d.street, d.legal)
            if s.action is None:
                counts["no suggestion"] += 1
                continue
            counts[s.action] = counts.get(s.action, 0) + 1
            facing = legal.to_call_bb > 0
            if s.action in ("fold", "call"):
                assert facing, (s, why)
            elif s.action == "check":
                assert not facing, (s, why)
            else:
                assert s.action in RAISES and legal.can_raise, (s, why)
                assert legal.raise_min_bb - 1e-9 <= s.size_bb <= legal.raise_max_bb + 1e-9, (s, why)
                assert s.size_bb <= legal.cap_bb + 1e-9, (s, why)
    print(f"\n{HANDS} hands in {time.perf_counter() - start:.0f} s: {counts}")
    assert counts["decisions"] >= 2 * HANDS
