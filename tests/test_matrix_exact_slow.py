"""The exact matrix against b-inary/poker-cfr's independent exact table (DECISIONS 20, 21).

Marked slow because it needs data/external/, which a fresh clone does not have.
Under `py gate.py --full` a missing file fails the run; it never skips.
"""

from pathlib import Path

import numpy as np
import pytest
from external_data import binary_equity_numerators

from showdown.equity.matrix import PreflopMatrix, _static

pytestmark = pytest.mark.slow

EXACT = Path(__file__).resolve().parents[1] / "data" / "preflop_169_exact.npz"
BOARDS = 1_712_304  # C(48, 5)


def test_exact_matrix_equals_b_inary_to_the_integer() -> None:
    table = binary_equity_numerators()
    s = _static()
    disjoint, starts = s["disjoint"], s["starts"]
    assert (table[~disjoint] == 0).all()
    assert ((table + table.T)[disjoint] == 2 * BOARDS).all()

    def block(a: np.ndarray) -> np.ndarray:
        return np.add.reduceat(np.add.reduceat(a, starts, axis=0), starts, axis=1)

    numerators = block(np.where(disjoint, table, 0))
    pairs = block(disjoint.astype(np.int64))
    ours = PreflopMatrix.load(EXACT)
    assert np.array_equal(pairs, ours.pair_counts)
    # Same integer denominators on both sides, so equal floats mean equal numerators.
    assert np.array_equal(ours.equity, numerators / (2 * (pairs * BOARDS)))
