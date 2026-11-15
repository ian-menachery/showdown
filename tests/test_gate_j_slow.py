"""Gate J, bar 2 (DECISIONS 36): the matrix equity of a specific hand against a
whole-class range equals exact board enumeration over every villain combo.
"""

from pathlib import Path

import numpy as np
import pytest

from showdown.equity.cards import make_combo, parse_cards
from showdown.equity.exact import hand_vs_hand
from showdown.equity.matrix import PreflopMatrix
from showdown.equity.ranges import parse_range
from showdown.live import jam

pytestmark = pytest.mark.slow

MATRIX = Path(__file__).resolve().parents[1] / "data" / "preflop_169_exact.npz"
SPOTS = [
    ("AhKd", "QQ"),
    ("7c7d", "AKs"),
    ("AsQs", "KK"),
    ("AhKd", "AA,AKs"),  # the hero blocks some of both classes
    ("5h4h", "JJ,AKo"),
    ("KcKd", "AA"),
]


@pytest.mark.parametrize(("hero", "villain"), SPOTS)
def test_bar2_matrix_equity_equals_enumeration(hero, villain) -> None:
    matrix = PreflopMatrix.load(MATRIX)
    h = make_combo(*parse_cards(hero))
    combos = parse_range(villain)
    live = [v for v in combos if not set(v) & set(h)]
    exact = float(np.mean([hand_vs_hand(h, v).equity for v in live]))
    ours = jam.jam_equity(h, jam.class_weights(combos), matrix)
    assert ours == pytest.approx(exact, abs=1e-9), (hero, villain, ours, exact)
