"""Matrix builder mechanics on tiny builds (the real matrix is checked in test_gate_c)."""

import numpy as np
import pytest

from showdown.equity import matrix as M
from showdown.equity.cards import class_index


def test_exact_pair_counts() -> None:
    counts = M.exact_pair_counts()
    assert counts.sum() == 1326 * 1225
    assert (counts == counts.T).all()
    assert counts[class_index("AA"), class_index("AA")] == 6
    assert counts[class_index("AKs"), class_index("AKs")] == 12
    assert counts[class_index("AA"), class_index("KK")] == 36
    assert counts[class_index("AKo"), class_index("AA")] == 36  # one ace used, 3 left


def test_tiny_build_is_symmetric_and_reproducible(tmp_path) -> None:
    a = M.build(boards_per_batch=3, batches=2, seed=11, workers=1)
    b = M.build(boards_per_batch=3, batches=2, seed=11, workers=1)
    assert np.array_equal(a.equity, b.equity)
    assert a.boards == 6
    assert np.allclose(a.equity + a.equity.T, 1.0)
    assert np.allclose(np.diag(a.equity), 0.5)

    path = tmp_path / "m.npz"
    a.save(path)
    loaded = M.PreflopMatrix.load(path)
    assert np.array_equal(loaded.equity, a.equity)
    assert loaded.cell("AA", "KK") == a.cell("AA", "KK")
    assert (loaded.boards, loaded.batches, loaded.seed) == (6, 2, 11)


def test_worker_count_does_not_change_result() -> None:
    one = M.build(boards_per_batch=2, batches=2, seed=5, workers=1)
    two = M.build(boards_per_batch=2, batches=2, seed=5, workers=2)
    # Four boards leave some class pairs unsampled (NaN); NaN must line up too.
    assert np.array_equal(one.equity, two.equity, equal_nan=True)
    assert np.array_equal(one.se, two.se, equal_nan=True)


def test_rejects_bad_sizes(tmp_path) -> None:
    with pytest.raises(ValueError):
        M.build(boards_per_batch=1, batches=1, seed=0, workers=1)
    bad = tmp_path / "bad.npz"
    np.savez(bad, class_names=np.array(["XX"] * 169))
    with pytest.raises(ValueError, match="class order"):
        M.PreflopMatrix.load(bad)
