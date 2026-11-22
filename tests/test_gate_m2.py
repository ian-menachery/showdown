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
    fitted = {"UTG": 0.2004, "HJ": 0.2554, "CO": 0.3254, "BTN": 0.4054, "SB": 0.4154}
    for seat, (flat, three_bet) in S.BB_CHART.items():
        p = std.for_seat(seat)
        assert p.bb_call == pytest.approx(flat - regular.behind_slope * 0.5)
        assert p.bb_call == pytest.approx(fitted[seat], abs=1e-4)
        assert p.bb_3bet == three_bet
        (sb_call, sb_3bet), others = S.ASSUMED_DEFENCE[seat]
        assert (p.sb_call, p.sb_3bet, (p.behind_call, p.behind_3bet)) == (sb_call, sb_3bet, others)
        for rate in S.RATES:
            if rate not in S.DEFENCE_RATES:
                assert getattr(p, rate) == getattr(regular, rate)
    assert [std.source[r] for r in S.DEFENCE_RATES] == ["fitted"] * 2 + ["assumed"] * 4
    assert std.for_seat("BB") == std
