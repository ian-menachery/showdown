"""Gate C, equity: the fast bullets (SCOPE). Slow bullets: test_gate_c_slow.py."""

import random
from pathlib import Path

import numpy as np
import pytest
from phevaluator import evaluate_cards

from showdown.equity.cards import card_str
from showdown.equity.evaluator import evaluate
from showdown.equity.exact import hand_vs_hand
from showdown.equity.matrix import PreflopMatrix
from showdown.equity.montecarlo import monte_carlo
from showdown.equity.ranges import parse_range

MATRIX = Path(__file__).resolve().parents[1] / "data" / "preflop_169.npz"
NAMES = [card_str(c) for c in range(52)]


def _sign(x: int) -> int:
    return (x > 0) - (x < 0)


def test_eval7_and_phevaluator_agree_on_100k_random_pairs() -> None:
    rng = random.Random(20261114)
    for _ in range(100_000):
        cards = rng.sample(range(52), 9)
        hero, villain, board = cards[:2], cards[2:4], cards[4:]
        ours = _sign(evaluate(hero + board) - evaluate(villain + board))  # higher is better
        theirs = _sign(
            evaluate_cards(*(NAMES[c] for c in villain + board))
            - evaluate_cards(*(NAMES[c] for c in hero + board))
        )  # phevaluator: lower is better
        assert ours == theirs, [NAMES[c] for c in cards]


def test_monte_carlo_is_calibrated() -> None:
    """200 seeded runs; the share within 2 SE of exact must be 0.90 to 0.99 (expected 0.954)."""
    hero, villain = parse_range("AsAh"), parse_range("KdKc")
    exact = hand_vs_hand(hero[0], villain[0]).equity
    inside = 0
    for seed in range(200):
        est = monte_carlo(hero, villain, samples=1_000, seed=seed)
        inside += abs(est.equity - exact) <= 2 * est.se
    share = inside / 200
    print(f"\nMC calibration: {inside}/200 within 2 SE (share {share:.3f})")
    assert 0.90 <= share <= 0.99


@pytest.fixture(scope="module")
def matrix() -> PreflopMatrix:
    return PreflopMatrix.load(MATRIX)


def test_matrix_cells_bounded_and_symmetric(matrix) -> None:
    off = ~np.eye(169, dtype=bool)
    assert ((matrix.equity >= 0) & (matrix.equity <= 1)).all()
    np.testing.assert_array_equal(np.diag(matrix.equity), 0.5)
    tolerance = 3 * np.sqrt(matrix.se**2 + matrix.se.T**2) + 1e-12
    assert (np.abs(matrix.equity + matrix.equity.T - 1)[off] <= tolerance[off]).all()


def test_matrix_standard_error_ceiling(matrix) -> None:
    off = ~np.eye(169, dtype=bool)
    assert matrix.se[off].max() <= 0.002
    assert matrix.batches >= 30  # enough batches for a batch-means SE to mean something


def test_matrix_pair_counts(matrix) -> None:
    assert int(matrix.pair_counts.sum()) == 1326 * 1225
