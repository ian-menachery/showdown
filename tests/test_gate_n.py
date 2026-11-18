"""Gate N bar 2: the stopgap range model's weights, worked by hand (DECISIONS 46).

The board is AsKsQd7c2h. The villain holds five combos, weakest first: 6c5c (ace high),
8d8h (a pair), KhKd and AhAd (sets), JhTh (the straight). With equal weights their
percentiles are 0.1, 0.3, 0.5, 0.7 and 0.9, so their bands are 1, 3, 5, 7 and 9. Each
expected weight below is the multiplier read off the test's curve table, worked by hand.
Bar 1 (Gate R's trace) is in test_gate_r.py.
"""

import pytest

from showdown.equity.cards import make_combo, parse_cards
from showdown.live.narrow import RangeModel, narrow, villain_moves

BOARD = parse_cards("AsKsQd7c2h")
COMBOS = tuple(make_combo(*parse_cards(h)) for h in ("6c5c", "8d8h", "KhKd", "AhAd", "JhTh"))
OPEN = ("preflop SB raises to 2.5", "preflop BB calls 1.5")
"""A 5 bb pot after the preflop line."""
CURVES = {
    "srp|river|oop|first": {
        "Check": {"f": None, "freq": [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]},
        "Bet": {"f": 0.5, "freq": [0.4, 0.2, 0.1, 0.05, 0.02, 0.1, 0.2, 0.4, 0.6, 0.8]},
        "AllIn": {"f": 2.0, "freq": [0.2, 0.1, 0.0, 0.0, 0.0, 0.0, 0.05, 0.1, 0.2, 0.4]},
    },
    "srp|river|ip|facing_bet": {
        "Call": {"f": 0.5, "freq": [0.0, 0.0, 0.2, 0.5, 1.0, 1.0, 0.9, 0.6, 0.5, 0.4]},
    },
    "srp|river|ip|facing_allin": {
        "Call": {"f": 2.0, "freq": [0.0, 0.0, 0.0, 0.0, 0.1, 0.3, 0.5, 0.8, 1.0, 1.0]},
    },
    "srp|river|oop|facing_bet": {
        "Raise": {"f": 0.75, "freq": [0.1, 0.05, 0.0, 0.0, 0.05, 0.1, 0.2, 0.4, 0.7, 1.0]},
        "AllIn": {"f": 2.5, "freq": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.5, 1.0]},
    },
}
MODEL = RangeModel(CURVES)


def run(history: tuple[str, ...], villain: str) -> tuple[tuple[float, ...], int, int]:
    return narrow(MODEL, COMBOS, None, BOARD, history, villain, "srp")


def check(got: tuple[float, ...], want: list[float]) -> None:
    assert got == pytest.approx(want, abs=1e-9)


def test_a_bet_at_the_bet_curves_size() -> None:
    # 2.5 into 5: f 0.5, the Bet curve alone; its shape is freq / 0.8. 8d8h's 0.0625 floors.
    weights, used, missing = run((*OPEN, "river BB bets 2.5"), "bb")
    check(weights, [0.25, 0.1, 0.125, 0.5, 1.0])
    assert (used, missing) == (1, 0)


def test_a_bet_between_the_two_sizes() -> None:
    # 6.25 into 5: f 1.25, halfway from 0.5 to 2.0. Mean of Bet's and AllIn's shapes.
    weights, _, _ = run((*OPEN, "river BB bets 6.25 (all-in)"), "bb")
    check(weights, [0.25, 0.1, 0.1, 0.375, 1.0])


def test_a_bet_above_the_all_in_size_is_clamped() -> None:
    # 15 into 5: f 3, past AllIn's 2.0, so AllIn's shape (freq / 0.4) alone.
    weights, _, _ = run((*OPEN, "river BB bets 15"), "bb")
    check(weights, [0.25, 0.1, 0.1, 0.25, 1.0])


def test_a_call_interpolates_by_the_size_faced() -> None:
    # Ian (BB) bets 5 into 5; the villain (SB) calls facing f 1.0: a third of the way from
    # the facing_bet Call curve (f 0.5) to the facing_allin one (f 2.0). 6c5c floors.
    history = (*OPEN, "river BB bets 5", "river SB calls 5")
    weights, used, _ = run(history, "sb")
    check(weights, [0.1, 2 / 3 * 0.5, 2 / 3 + 0.3 / 3, 2 / 3 * 0.6 + 0.8 / 3, 2 / 3 * 0.4 + 1 / 3])
    assert used == 1
    assert villain_moves(history, "sb")[0].f == pytest.approx(1.0)


def test_a_check_keeps_a_quarter() -> None:
    # The Check curve's bands 1-9 are 0.9, 0.7, 0.5, 0.3, 0.1; JhTh's 0.1 floors at 0.25.
    weights, _, _ = run((*OPEN, "river BB checks"), "bb")
    check(weights, [0.9, 0.7, 0.5, 0.3, 0.25])


def test_two_moves_re_rank_within_the_narrowed_range() -> None:
    # After the check the weights are 0.9, 0.7, 0.5, 0.3, 0.25 (total 2.65). Their midpoints,
    # 0.45, 1.25, 1.85, 2.25, 2.525 over 2.65, fall in bands 1, 4, 6, 8, 9. The raise to 10
    # over Ian's 2.5 into 5 is f = 7.5 / 10 = 0.75, the Raise curve alone: 0.05 and 0.05
    # floor at 0.1, then 0.2, 0.7, 1.0.
    history = (*OPEN, "river BB checks", "river SB bets 2.5", "river BB raises to 10")
    weights, used, _ = run(history, "bb")
    check(weights, [0.9 * 0.1, 0.7 * 0.1, 0.5 * 0.2, 0.3 * 0.7, 0.25 * 1.0])
    assert used == 2
    assert villain_moves(history, "bb")[1].f == pytest.approx(0.75)


def test_a_move_with_no_curve_narrows_nothing() -> None:
    # The table has no flop or turn curves: the BB's two checks are counted, not used.
    history = (*OPEN, "flop BB checks", "flop SB checks", "turn BB checks", "turn SB checks")
    weights, used, missing = run((*history, "river BB bets 2.5"), "bb")
    check(weights, [0.25, 0.1, 0.125, 0.5, 1.0])
    assert (used, missing) == (1, 2)
    nodes = [(m.street, m.node, m.action) for m in villain_moves(history, "sb")]
    assert nodes == [("flop", "after_check", "Check"), ("turn", "after_check", "Check")]
