"""The pokerkit adapter, the bots, grading and play sessions (DECISIONS 24)."""

import random

import numpy as np
import pytest

from showdown import pushfold as pf
from showdown.bot.policy import LeducStrategy, PushFoldStrategy, act
from showdown.bot.sessions import LeducSession, PlayError, PushFoldSession
from showdown.engine.pokerkit_adapter import BB_SEAT, SB_SEAT, PushFoldHand, deal_cards
from showdown.equity.cards import class_index, parse_cards


@pytest.fixture(scope="module")
def strategy() -> PushFoldStrategy:
    return PushFoldStrategy.load()


@pytest.fixture(scope="module")
def leduc() -> LeducStrategy:
    return LeducStrategy.load()


def _hand(stack: int, sb: str, bb: str, board: str = "2c7d9hJc3s") -> PushFoldHand:
    return PushFoldHand(stack, [*parse_cards(sb), *parse_cards(bb), *parse_cards(board)])


def test_seats_follow_pokerkit_heads_up_order() -> None:
    hand = _hand(10, "AsAh", "KsKd")
    assert (BB_SEAT, SB_SEAT) == (0, 1)
    assert list(hand.state.bets) == [2, 1]  # the BB posts 2 chips, the SB 1
    assert hand.to_act == "sb"
    assert hand.sb_class == class_index("AA")
    assert hand.bb_class == class_index("KK")


@pytest.mark.parametrize(
    ("sb_jam", "bb_call", "net", "board_cards"),
    [(False, None, -0.5, 0), (True, False, 1.0, 0), (True, True, 10.0, 5)],
)
def test_payoffs_match_the_model(sb_jam, bb_call, net, board_cards) -> None:
    hand = _hand(10, "AsAh", "KsKd")
    hand.sb_act(sb_jam)
    if bb_call is not None:
        assert hand.to_act == "bb"
        hand.bb_act(bb_call)
    result = hand.finish()
    assert result.sb_net == net
    assert len(result.board) == board_cards


def test_one_bb_jam_leaves_the_bb_no_decision() -> None:
    hand = _hand(1, "KsKd", "AsAh")
    hand.sb_act(True)
    assert hand.to_act is None
    result = hand.finish()
    assert result.sb_net == -1.0
    assert result.bb_called is None


def test_split_pot_and_misuse() -> None:
    hand = _hand(5, "AsKd", "AhKs", "2c7d9hQcJc")
    with pytest.raises(ValueError, match="turn"):
        hand.bb_act(True)
    with pytest.raises(ValueError, match="decision"):
        hand.finish()
    hand.sb_act(True)
    hand.bb_act(True)
    assert hand.finish().sb_net == 0.0
    with pytest.raises(ValueError):
        PushFoldHand(10, [0, 1, 2])
    assert len(set(deal_cards(random.Random(3)))) == 9


def test_grading_reproduces_the_closed_form_best_responses(strategy) -> None:
    depth = 10
    d = strategy.solution.at(depth)
    m = strategy.matrix
    w = m.pair_counts / m.pair_counts.sum()
    sb_fold, sb_jam = pf.sb_action_values(d.call, depth, m)
    bb_fold, bb_call = pf.bb_action_values(d.push, depth, m)
    sb_best = (w.sum(axis=1) * np.maximum(sb_fold, sb_jam)).sum()
    jam_weight = (w * d.push[:, None]).sum(axis=0)
    bb_best = ((w * (1 - d.push)[:, None]).sum(axis=0) * 0.5).sum() + (
        jam_weight * np.maximum(bb_fold, bb_call)
    ).sum()
    expected = pf.closed_form_exploitability(d.push, d.call, depth, m)
    assert (sb_best + bb_best) / 2 == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("depth", [2, 10, 20])
def test_nash_actions_lose_almost_nothing(strategy, depth) -> None:
    d = strategy.solution.at(depth)
    for cls in range(169):
        for seat, prob in (("sb", d.push[cls]), ("bb", d.call[cls])):
            if prob >= pf.PURE:
                assert strategy.grade(depth, seat, cls, True).loss < 1e-3
            elif prob <= 1 - pf.PURE:
                assert strategy.grade(depth, seat, cls, False).loss < 1e-3
    bad = strategy.grade(10, "bb", class_index("72o"), True)
    assert bad.mistake
    assert bad.loss > 0.5
    with pytest.raises(ValueError):
        strategy.grade(10, "button", 0, True)


def test_bots_sample_their_strategies(leduc) -> None:
    rng = random.Random(5)
    assert all(act(1.0, rng) for _ in range(100))
    assert not any(act(0.0, rng) for _ in range(100))
    key = next(iter(leduc.table))
    counts = {}
    for _ in range(4000):
        a = leduc.choose(key, {1: "call", 2: "raise"}, rng)
        counts[a] = counts.get(a, 0) + 1
    share = counts.get(2, 0) / 4000
    p = leduc.table[key]["raise"]
    assert abs(share - p) < 4 * (p * (1 - p) / 4000) ** 0.5 + 1e-9


def test_pushfold_session_rules(strategy) -> None:
    with pytest.raises(PlayError):
        PushFoldSession(strategy, seat="button")
    with pytest.raises(PlayError):
        PushFoldSession(strategy, depth_mode="sometimes")
    with pytest.raises(PlayError):
        PushFoldSession(strategy, depth=25)
    session = PushFoldSession(strategy, seat="sb", depth=10, rng=random.Random(1))
    assert "hand" not in session.view()
    with pytest.raises(PlayError, match="turn"):
        session.act("fold")
    view = session.new_hand()
    assert view["your_turn"]
    with pytest.raises(PlayError, match="finish"):
        session.new_hand()
    with pytest.raises(PlayError, match="fold or all-in"):
        session.act("raise")
    view = session.act("fold")
    assert view["result"]["net_bb"] == -0.5
    assert view["summary"]["decisions"] == 1


def test_random_depth_and_reproducibility(strategy) -> None:
    def play(seed):
        session = PushFoldSession(
            strategy, seat="alternate", depth_mode="random", rng=random.Random(seed)
        )
        depths = []
        for _ in range(12):
            view = session.new_hand()
            depths.append(view["depth"])
            if view["your_turn"]:
                session.act("all-in")
        return depths, session.summary()

    depths, summary = play(9)
    assert all(2 <= d <= 20 for d in depths)
    assert len(set(depths)) > 3
    assert play(9) == (depths, summary)


def test_leduc_session_rules(leduc) -> None:
    with pytest.raises(PlayError):
        LeducSession(leduc, seat="dealer")
    session = LeducSession(leduc, seat="first", rng=random.Random(4))
    assert "hand" not in session.view()
    view = session.new_hand()
    assert view["seat"] == "first"
    assert view["your_turn"]
    assert "result" not in view
    with pytest.raises(PlayError, match="legal"):
        session.act("fold")  # nothing to fold to at the first decision
    with pytest.raises(PlayError, match="finish"):
        session.new_hand()
    while view["your_turn"]:
        view = session.act("call")
    assert "bot_card" in view["result"]
    with pytest.raises(PlayError, match="turn"):
        session.act("call")
