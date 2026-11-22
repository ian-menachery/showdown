"""Gate M2, bar 1: per-seat rates, against hand-worked closed forms (DECISIONS 54).

Gate M bar 1's 21 checks (`test_gate_m.py`) must still pass unchanged; this adds the seat
lookup.
"""

import pytest
from test_gate_m import profile

from showdown import sixmax as S
from showdown.equity.cards import class_index


@pytest.mark.parametrize("ante", [0.0, 0.5])
def test_seat_lookup(ante) -> None:
    p = profile(by_seat={"UTG": {"bb_3bet": 1.0}})
    utg = S.answer(S.Spot("UTG", 0, ante), p, class_index("72o"), samples=1_000)
    hj = S.answer(S.Spot("HJ", 0, ante), p, class_index("72o"), samples=1_000)
    for x in (2.5, 3.0, 4.0):
        name = f"open to {x:g}"
        assert abs(utg.ev[utg.actions.index(name)] - (-x)) < 1e-9
        assert abs(hj.ev[hj.actions.index(name)] - (6 * ante + 1.5)) < 1e-9


def test_standard_is_regular_with_seat_defence() -> None:
    profiles = S.load_profiles()
    regular, std = profiles["regular"], profiles["standard"]
    assert regular.for_seat("BTN") == regular
    for seat, (bb, sb, others) in S.STANDARD_DEFENCE.items():
        p = std.for_seat(seat)
        assert (p.bb_call, p.bb_3bet, p.sb_call, p.sb_3bet) == (*bb, *sb)
        assert (p.behind_call, p.behind_3bet) == others
        for rate in S.RATES:
            if rate not in S.DEFENCE_RATES:
                assert getattr(p, rate) == getattr(regular, rate)
    assert all(std.source[r] == "assumed" for r in S.DEFENCE_RATES)
    assert std.for_seat("BB") == std.for_seat("BB").for_seat("BB")
