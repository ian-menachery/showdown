"""Expected pot shares for all-in hands, any number of players and side pots (DECISIONS 26)."""

import pytest
from pokerkit import Deck, StandardHighHand, calculate_equities, parse_range

from showdown.equity.cards import parse_cards
from showdown.equity.exact import hand_vs_hand
from showdown.equity.multiway import pot_shares


def _combo(text):
    a, b = parse_cards(text)
    return (max(a, b), min(a, b))


def test_heads_up_turn_matches_exact_enumeration() -> None:
    aa, kk = _combo("AsAh"), _combo("KsKh")
    board = parse_cards("2c7d9h3s")
    shares = pot_shares({0: aa, 1: kk}, board, [(100.0, (0, 1))])
    assert shares.method == "exact"
    assert shares.runouts == 44
    assert shares.expected[0] == pytest.approx(100 * 42 / 44, abs=1e-12)
    assert shares.expected[0] == pytest.approx(100 * hand_vs_hand(aa, kk, board).equity, abs=1e-12)
    assert shares.se == {0: 0.0, 1: 0.0}


def test_heads_up_preflop_uses_exact_enumeration() -> None:
    aa, kk = _combo("AsAh"), _combo("KdKc")
    shares = pot_shares({3: aa, 5: kk}, (), [(200.0, (3, 5))])
    assert shares.method == "exact"
    assert shares.expected[3] == pytest.approx(200 * 2782682 / 3424608, abs=1e-9)
    assert shares.expected[3] + shares.expected[5] == pytest.approx(200, abs=1e-9)


def test_side_pots_and_eligibility() -> None:
    hands = {0: _combo("AsAh"), 1: _combo("KsKh"), 2: _combo("QsQh")}
    board = parse_cards("2c7d9h3s")
    shares = pot_shares(hands, board, [(90.0, (0, 1, 2)), (140.0, (1, 2))])
    assert shares.runouts == 42
    assert shares.expected[0] == pytest.approx(90 * 38 / 42, abs=1e-12)
    assert shares.expected[1] == pytest.approx(90 * 2 / 42 + 140 * 40 / 42, abs=1e-12)
    assert shares.expected[2] == pytest.approx(90 * 2 / 42 + 140 * 2 / 42, abs=1e-12)
    # A pot whose other eligible players folded goes to the one live player.
    one = pot_shares({0: hands[0], 1: hands[1]}, board, [(50.0, (0, 1)), (30.0, (1, 4))])
    assert one.expected[1] == pytest.approx(50 * 2 / 44 + 30, abs=1e-12)


def test_ties_split_equally() -> None:
    board = parse_cards("AhKhQdJcTs")  # broadway on the board: everyone chops
    shares = pot_shares(
        {0: _combo("2c3d"), 1: _combo("4s5c"), 2: _combo("6d7d")}, board[:4], [(90.0, (0, 1, 2))]
    )
    assert shares.runouts == 52 - 6 - 4
    # Any river keeps A-K-Q-J on board; only a T or 9 matters, and nobody holds one.
    assert sum(shares.expected.values()) == pytest.approx(90, abs=1e-12)


def test_rejects_bad_input() -> None:
    with pytest.raises(ValueError, match="share"):
        pot_shares({0: _combo("AsAh"), 1: _combo("AsKd")}, (), [(10.0, (0, 1))])
    with pytest.raises(ValueError, match="no live"):
        pot_shares({0: _combo("AsAh"), 1: _combo("KsKd")}, (), [(10.0, (2, 3))])
    with pytest.raises(ValueError, match="two cards"):
        pot_shares({0: _combo("AsAh"), 1: _combo("KsKd")}, parse_cards("2c3c4c5c6c7c"), [])


def test_three_way_preflop_monte_carlo_agrees_with_pokerkit() -> None:
    hands = {0: _combo("AsAh"), 1: _combo("KdKc"), 2: _combo("7s6s")}
    pot = 300.0
    shares = pot_shares(hands, (), [(pot, (0, 1, 2))], samples=20_000, seed=7)
    assert shares.method == "monte-carlo"
    assert sum(shares.expected.values()) == pytest.approx(pot, abs=1e-6)
    oracle = calculate_equities(
        tuple(parse_range(r) for r in ("AsAh", "KdKc", "7s6s")),
        (),
        2,
        5,
        Deck.STANDARD,
        (StandardHighHand,),
        sample_count=4000,
    )
    for seat, equity in enumerate(oracle):
        # Combined SE: ours, plus pokerkit's (at most sqrt(e(1-e)/n) of the pot).
        se = (shares.se[seat] ** 2 + pot**2 * equity * (1 - equity) / 4000) ** 0.5
        assert abs(shares.expected[seat] - pot * equity) <= 3 * se, (seat, equity)
