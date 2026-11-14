"""The exact 169×169 matrix (DECISIONS 21): the method, and the committed file."""

import itertools
from pathlib import Path

import numpy as np
import pytest

from showdown.equity import matrix as M
from showdown.equity.cards import CLASS_COMBOS, class_index
from showdown.equity.evaluator import evaluate

DATA = Path(__file__).resolve().parents[1] / "data"
EXACT = DATA / "preflop_169_exact.npz"
MONTE_CARLO = DATA / "preflop_169.npz"


@pytest.fixture(scope="module")
def canonical() -> tuple[np.ndarray, np.ndarray]:
    return M.canonical_boards()


def test_canonical_boards_cover_every_board_once(canonical) -> None:
    boards, weights = canonical
    # Burnside's lemma: (2,598,960 + 6 × 101,608 + 8 × 2,301) / 24 = 134,459. Those are
    # the boards fixed by the identity, by the 6 transpositions and by the 8
    # three-cycles of the suits. No board is fixed by a double transposition or a
    # four-cycle.
    assert boards.shape == (134_459, 5)
    assert weights.sum() == M.ALL_BOARDS
    assert set(np.unique(weights).tolist()) == {4, 12, 24}
    assert (np.diff(boards, axis=1) > 0).all()


def test_weights_are_the_number_of_distinct_relabellings(canonical) -> None:
    boards, weights = canonical
    rng = np.random.default_rng(3)
    rows = rng.choice(len(boards), size=300, replace=False)
    rows = np.r_[rows, np.flatnonzero(weights == 4)[:20]]
    for r in rows:
        board = boards[r]
        images = {
            tuple(sorted(4 * (c // 4) + perm[c % 4] for c in board)) for perm in M.SUIT_PERMUTATIONS
        }
        assert len(images) == weights[r], board


def test_exact_sums_do_not_change_under_suit_relabelling() -> None:
    rng = np.random.default_rng(7)
    board = np.sort(rng.choice(52, size=5, replace=False))
    perm = np.array([2, 0, 3, 1])
    relabelled = np.sort(4 * (board // 4) + perm[board % 4])
    assert not np.array_equal(board, relabelled)
    a = M._run_exact((board[None, :], np.array([1])))
    b = M._run_exact((relabelled[None, :], np.array([1])))
    assert np.array_equal(a[0], b[0])
    assert np.array_equal(a[1], b[1])


def test_one_board_block_sum_matches_brute_force() -> None:
    board = np.array([0, 9, 22, 35, 50])  # 2c 4d 7h Ts Ah
    scores, counts = M._run_exact((board[None, :], np.array([1])))
    for row, col in (("KK", "QQ"), ("AKs", "T9s"), ("72o", "32o")):
        i, j = class_index(row), class_index(col)
        expected_score = expected_count = 0
        for hero, villain in itertools.product(CLASS_COMBOS[i], CLASS_COMBOS[j]):
            if set(hero) & set(villain) or set(hero + villain) & set(board.tolist()):
                continue
            ours = evaluate([*hero, *board.tolist()])
            theirs = evaluate([*villain, *board.tolist()])
            expected_score += 2 * (ours > theirs) + (ours == theirs)
            expected_count += 1
        assert (scores[i, j], counts[i, j]) == (expected_score, expected_count), (row, col)


def test_exact_sums_do_not_depend_on_workers(canonical) -> None:
    boards, weights = canonical
    one = M.exact_sums(boards[:4], weights[:4], workers=1, chunk=2)
    two = M.exact_sums(boards[:4], weights[:4], workers=2, chunk=2)
    assert all(np.array_equal(x, y) for x, y in zip(one, two, strict=True))


def test_committed_exact_matrix() -> None:
    m = M.PreflopMatrix.load(EXACT)
    assert (m.method, m.boards, m.batches, m.seed) == ("exact", M.ALL_BOARDS, 0, 0)
    assert (m.se == 0).all()
    assert np.array_equal(m.pair_counts, M.exact_pair_counts())
    assert (np.diag(m.equity) == 0.5).all()
    assert np.allclose(m.equity + m.equity.T, 1.0, rtol=0, atol=1e-15)
    # Exact class-vs-class enumerations recorded under Gate C in GATES.md.
    for row, col, value in (("AA", "KK", 0.81946), ("AKs", "QQ", 0.46049), ("T9s", "AKo", 0.40524)):
        assert m.equity[class_index(row), class_index(col)] == pytest.approx(value, abs=5e-6)


def test_monte_carlo_matrix_agrees_with_exact() -> None:
    exact = M.PreflopMatrix.load(EXACT)
    mc = M.PreflopMatrix.load(MONTE_CARLO)
    assert mc.method == "monte-carlo"
    off = ~np.eye(169, dtype=bool)
    z = (mc.equity - exact.equity)[off] / mc.se[off]
    assert np.abs(z).max() < 4.5
    assert 0.93 <= (np.abs(z) <= 2).mean() <= 0.99
