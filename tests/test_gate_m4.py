"""Gate M4, bar 1: R 0.75 for an out-of-position raiser, and the standard profile's limpers
from loose-passive (DECISIONS 57).

Gate M bar 1 (`test_gate_m.py`) and Gate M2 bar 1 (`test_gate_m2.py`) must still pass
unchanged; this adds the new R (Gate M3's check) and the new profile.
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


def test_standard_limpers_are_loose_passive() -> None:
    profiles = S.load_profiles()
    regular, loose, std = profiles["regular"], profiles["loose-passive"], profiles["standard"]
    gated = S.load_profiles(standard_limpers=S.GATED_STANDARD_LIMPERS)["standard"]
    assert std.by_seat == gated.by_seat
    for rate in S.RATES:
        want = getattr(loose if rate in S.LIMPER_RATES else regular, rate)
        assert getattr(std, rate) == want
    for seat in (*S.BB_CHART, "BB"):
        p, q = std.for_seat(seat), gated.for_seat(seat)
        for rate in S.RATES:
            want = getattr(loose if rate in S.LIMPER_RATES else q, rate)
            assert getattr(p, rate) == want
    assert [std.source[r] for r in S.LIMPER_RATES] == ["fitted, loose-passive"] * 5
    assert {r: std.source[r] for r in S.DEFENCE_RATES} == {
        r: gated.source[r] for r in S.DEFENCE_RATES
    }
