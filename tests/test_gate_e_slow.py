"""Gate E, the slow bullet: 20,000 bot-vs-bot push/fold hands at 10 bb through
pokerkit's state machine land within 3 SE of the solver's game value (SCOPE).

Backstops from the design review (DECISIONS 24), which catch a seat swap or a
chip-unit error that the 3 SE test alone could miss:
- every hand's payoff fits the model, and the winner of every called hand
  agrees with our own evaluator;
- the overall jam and call rates match the solution (within 4 SE).
"""

import math
import random

import pytest

from showdown.bot.policy import PushFoldStrategy, act
from showdown.engine.pokerkit_adapter import PushFoldHand, deal_cards
from showdown.equity.evaluator import evaluate

pytestmark = [pytest.mark.slow, pytest.mark.filterwarnings("error::UserWarning")]

HANDS = 20_000
DEPTH = 10


def test_bot_vs_bot_matches_the_game_value() -> None:
    strategy = PushFoldStrategy.load()
    rng = random.Random(20261114)
    results, jams, calls = [], 0, 0
    for _ in range(HANDS):
        hand = PushFoldHand(DEPTH, deal_cards(rng))
        jam = act(strategy.push_prob(DEPTH, hand.sb_class), rng)
        hand.sb_act(jam)
        call = False
        if jam:
            jams += 1
            assert hand.to_act == "bb"
            call = act(strategy.call_prob(DEPTH, hand.bb_class), rng)
            hand.bb_act(call)
            calls += call
        r = hand.finish()
        if not jam:
            assert r.sb_net == -0.5
        elif not call:
            assert r.sb_net == 1.0
        else:
            ours = evaluate([*r.sb_cards, *r.board])
            theirs = evaluate([*r.bb_cards, *r.board])
            expected = DEPTH if ours > theirs else -DEPTH if ours < theirs else 0
            assert r.sb_net == expected
        results.append(r.sb_net)

    n = len(results)
    mean = sum(results) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in results) / (n - 1))
    se = sd / math.sqrt(n)
    solution = strategy.solution.at(DEPTH)
    value = solution.value_sb
    print(
        f"\nrealised SB {mean:+.5f} bb/hand, SE {se:.5f}, solver value {value:+.5f}, "
        f"z = {(mean - value) / se:+.2f}; sd {sd:.3f}"
    )
    assert abs(mean - value) <= 3 * se

    p_jam = solution.push_share()
    jam_se = math.sqrt(p_jam * (1 - p_jam) / n)
    w = strategy.matrix.pair_counts
    jam_weight = (w * solution.push[:, None]).sum(axis=0)
    p_call = float((jam_weight * solution.call).sum() / jam_weight.sum())
    call_se = math.sqrt(p_call * (1 - p_call) / jams)
    print(f"jam rate {jams / n:.4f} vs {p_jam:.4f}; call rate {calls / jams:.4f} vs {p_call:.4f}")
    assert abs(jams / n - p_jam) <= 4 * jam_se
    assert abs(calls / jams - p_call) <= 4 * call_se
