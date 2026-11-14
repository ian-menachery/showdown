"""Exact and Monte Carlo equity, fast cases (preflop exact is in the slow suite)."""

import pytest

from showdown.equity.cards import parse_cards
from showdown.equity.exact import (
    MAX_EXACT_EVALUATIONS,
    canonical_pair,
    hand_vs_hand,
    range_vs_range,
)
from showdown.equity.montecarlo import monte_carlo
from showdown.equity.ranges import parse_range


def combo(text: str):
    (c,) = parse_range(text)
    return c


def test_river_is_deterministic() -> None:
    # AsKs has ace high (four spades, no straight); QhQd has a pair of queens.
    eq = hand_vs_hand(combo("AsKs"), combo("QhQd"), parse_cards("Ts9s2dJc3h"))
    assert (eq.win, eq.tie, eq.outcomes) == (0.0, 0.0, 1)


def test_turn_outs_counted_by_hand() -> None:
    # 44 rivers. AsKs wins on the 9 spades left (flush), Qc (broadway beats trip
    # queens) and the 3 aces left (aces beat queens): 13 in all. The 3 kings
    # lose: a king gives QhQd the straight K-Q-J-T-9.
    eq = hand_vs_hand(combo("AsKs"), combo("QhQd"), parse_cards("Ts9s2dJc"))
    assert eq.outcomes == 44
    assert eq.win == 13 / 44
    assert eq.tie == 0.0
    assert eq.lose == pytest.approx(31 / 44)


def test_symmetry_and_split() -> None:
    board = parse_cards("Ts9s2d")
    a = range_vs_range(parse_range("AsKs"), parse_range("QhQd"), board)
    b = range_vs_range(parse_range("QhQd"), parse_range("AsKs"), board)
    assert a.win == pytest.approx(b.lose, abs=1e-15)
    assert a.tie == pytest.approx(b.tie, abs=1e-15)
    # Both hold broadway, and no river can give either a flush: always a chop.
    chop = hand_vs_hand(combo("AsKd"), combo("AhKc"), parse_cards("QsJdTc2h"))
    assert (chop.win, chop.tie) == (0.0, 1.0)


def test_range_vs_range_equals_average_of_pairs() -> None:
    board = parse_cards("Ts9s2d")
    hero, villain = parse_range("AsKs,AhKh"), parse_range("QQ")
    whole = range_vs_range(hero, villain, board)
    pairs = [hand_vs_hand(h, v, board) for h in hero for v in villain if not set(h) & set(v)]
    assert whole.win == pytest.approx(sum(p.win for p in pairs) / len(pairs), abs=1e-12)
    assert whole.tie == pytest.approx(sum(p.tie for p in pairs) / len(pairs), abs=1e-12)


def test_card_conflicts_are_rejected_or_dropped() -> None:
    with pytest.raises(ValueError, match="share a card"):
        hand_vs_hand(combo("AsKs"), combo("AsQd"))
    with pytest.raises(ValueError, match="no combo pair"):
        range_vs_range(parse_range("AsKs"), parse_range("AsQs"), parse_cards("2c3c4c"))
    # Combos that hit the board are dropped, not counted.
    eq = range_vs_range(parse_range("AA"), parse_range("KK"), parse_cards("As2c3d"))
    assert eq.equity > 0.5
    with pytest.raises(ValueError, match="at most 5"):
        hand_vs_hand(combo("AsKs"), combo("QhQd"), parse_cards("2c3c4c5c6c7c"))


def test_exact_guard() -> None:
    with pytest.raises(ValueError, match="use Monte Carlo"):
        range_vs_range(parse_range("random"), parse_range("random"))
    assert MAX_EXACT_EVALUATIONS > 1_000_000


def test_canonical_pair_is_suit_invariant() -> None:
    a = canonical_pair(combo("AsAh"), combo("KdKc"))
    b = canonical_pair(combo("AdAc"), combo("KhKs"))
    c = canonical_pair(combo("AsAh"), combo("KsKd"))
    assert a == b != c


def test_monte_carlo_close_to_exact_on_flop() -> None:
    board = parse_cards("Ts9s2d")
    hero, villain = parse_range("TT+,AK"), parse_range("22-99,AT-AQ")
    exact = range_vs_range(hero, villain, board)
    estimate = monte_carlo(hero, villain, board, samples=40_000, seed=3)
    assert abs(estimate.equity - exact.equity) < 4 * estimate.se
    assert monte_carlo(hero, villain, board, samples=500, seed=9) == monte_carlo(
        hero, villain, board, samples=500, seed=9
    )


def test_monte_carlo_input_errors() -> None:
    with pytest.raises(ValueError):
        monte_carlo(parse_range("AA"), parse_range("KK"), samples=1)
    with pytest.raises(ValueError):
        monte_carlo(parse_range("AA"), parse_range("KK"), parse_cards("2c2c"))
    with pytest.raises(ValueError):
        monte_carlo(parse_range("AsAh"), parse_range("AsAd"))
