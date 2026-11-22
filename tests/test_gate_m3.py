"""Gate M3, bar 1: R 0.75 for an out-of-position raiser, against a closed form (DECISIONS 56).

Gate M bar 1 (`test_gate_m.py`) and Gate M2 bar 1 (`test_gate_m2.py`) must still pass
unchanged; this adds the new R.
"""

import pytest
from test_gate_m import HANDS, m, profile

from showdown import sixmax as S
from showdown.equity.cards import class_index


def test_the_new_r() -> None:
    assert S.R == {"raise_ip": 1.00, "raise_oop": 0.75, "limp_ip": 0.85, "limp_oop": 0.75}


@pytest.mark.parametrize("ante", [0.0, 0.5])
@pytest.mark.parametrize("hand", HANDS)
def test_the_bb_raises_a_limper_who_always_calls(ante, hand) -> None:
    spot = S.Spot("BB", 1, ante)
    p = profile(limp_range="KK", iso_fold=0.0)
    a = S.answer(spot, p, class_index(hand), samples=2_000)
    for x in spot.sizes:
        pot = 0.5 + 6 * ante + 2 * x
        expected = 0.75 * m(hand, "KK") * pot - (x - 1)
        assert abs(a.ev[a.actions.index(f"raise to {x:g}")] - expected) < 1e-9
