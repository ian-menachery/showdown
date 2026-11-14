"""Gate C, equity: the slow bullets (SCOPE). Run with `py gate.py --full`."""

import itertools
import math
import random
from pathlib import Path

import pytest
from phevaluator import evaluate_cards
from pokerkit import Card, Deck, StandardHighHand, calculate_equities
from pokerkit import parse_range as pokerkit_range

from showdown.equity.cards import card_str, class_index, parse_cards
from showdown.equity.exact import class_vs_class, hand_vs_hand
from showdown.equity.matrix import PreflopMatrix
from showdown.equity.ranges import parse_range

pytestmark = pytest.mark.slow

MATRIX = Path(__file__).resolve().parents[1] / "data" / "preflop_169.npz"
NAMES = [card_str(c) for c in range(52)]

# 20 matchups beyond AsAh vs KdKc: 3 preflop, 8 flop, 6 turn, 3 river.
MATCHUPS = [
    ("AhKh", "QsQc", ""),
    ("JdTd", "9c9s", ""),
    ("Ac5c", "KdQh", ""),
    ("AsKs", "QhQd", "Ts9s2d"),
    ("AhAd", "KcKs", "Kd7h2c"),
    ("8h7h", "AcAd", "9h6h2s"),
    ("QcJc", "AhKd", "Tc9c3h"),
    ("5d5c", "AsQs", "Qd5h2s"),
    ("KhQh", "KdJd", "Kc8h3d"),
    ("6s6h", "AdKd", "Ah7d2c"),
    ("TdTc", "9h8h", "Jh7c2h"),
    ("AsKs", "QhQd", "Ts9s2dJc"),
    ("8h7h", "AcAd", "9h6h2sKc"),
    ("QcJc", "AhKd", "Tc9c3h2d"),
    ("JhTh", "AsAc", "9h8c2d3s"),
    ("KdKc", "Ah5h", "Ac9h4h7s"),
    ("4c4d", "7s6s", "5s8d2hKs"),
    ("AsKs", "QhQd", "Ts9s2dJc3h"),
    ("7c7d", "AhKh", "Kd7s2c9h4s"),
    ("JdTd", "Ac2c", "9c8h7d2h3s"),
]


def _combo(text: str):
    (c,) = parse_range(text)
    return c


def _phevaluator_exact(hero, villain, board):
    dead = set(hero) | set(villain) | set(board)
    deck = [c for c in range(52) if c not in dead]
    h = [NAMES[c] for c in hero]
    v = [NAMES[c] for c in villain]
    b = [NAMES[c] for c in board]
    win = tie = n = 0
    for run in itertools.combinations(deck, 5 - len(board)):
        full = b + [NAMES[c] for c in run]
        a, k = evaluate_cards(*h, *full), evaluate_cards(*v, *full)  # lower is better
        n += 1
        win += a < k
        tie += a == k
    return win / n, tie / n, n


def test_asah_vs_kdkc_exact() -> None:
    eq = hand_vs_hand(_combo("AsAh"), _combo("KdKc"))
    assert eq.outcomes == 1_712_304
    assert eq.win == pytest.approx(0.81065, abs=1e-5)
    assert eq.tie == pytest.approx(0.00382, abs=1e-5)
    assert eq.equity == pytest.approx(0.81255, abs=1e-5)


def test_matchups_are_well_formed() -> None:
    assert len(MATCHUPS) == 20
    for hero, villain, board in MATCHUPS:
        cards = parse_cards(hero + villain + board)
        assert len(set(cards)) == len(cards)


@pytest.mark.parametrize(("hero", "villain", "board"), MATCHUPS)
def test_exact_equals_phevaluator_enumeration(hero, villain, board) -> None:
    h, v, b = _combo(hero), _combo(villain), parse_cards(board)
    ours = hand_vs_hand(h, v, b)
    assert (ours.win, ours.tie, ours.outcomes) == _phevaluator_exact(h, v, b)


@pytest.mark.parametrize(("hero", "villain", "board"), MATCHUPS)
def test_exact_within_3_se_of_pokerkit(hero, villain, board) -> None:
    samples = 4_000
    exact = hand_vs_hand(_combo(hero), _combo(villain), parse_cards(board)).equity
    random.seed(sum(map(ord, hero + villain + board)))  # pokerkit samples from `random`
    theirs = calculate_equities(
        (pokerkit_range(hero), pokerkit_range(villain)),
        tuple(Card.parse(board)) if board else (),
        2,
        5,
        Deck.STANDARD,
        (StandardHighHand,),
        sample_count=samples,
    )[0]
    se = math.sqrt(exact * (1 - exact) / samples)  # upper bound for a [0, 1] score
    assert abs(theirs - exact) <= 3 * se + 1e-12


@pytest.mark.parametrize(("row", "col"), [("AA", "KK"), ("AKs", "QQ"), ("T9s", "AKo")])
def test_matrix_cell_within_3_se_of_exact(row, col) -> None:
    """Not a gate bullet: the sampled matrix against exact class-vs-class enumeration."""
    matrix = PreflopMatrix.load(MATRIX)
    exact = class_vs_class(class_index(row), class_index(col)).equity
    value, se = matrix.cell(row, col)
    print(f"\n{row} vs {col}: matrix {value:.5f} +/- {se:.5f}, exact {exact:.5f}")
    assert abs(value - exact) <= 3 * se
