"""Gate Z2, bar 1 (DECISIONS 64): closed forms facing an open at the fixed model (a flat
opener call share, R 0.85 for a called 3-bet in position), to 1e-9; and unopened or limped
answers unchanged by the fix."""

from dataclasses import replace

import numpy as np
import pytest
from test_gate_z import ANTES, HANDS, M, _ev, _opener

from showdown import sixmax as S
from showdown.equity.cards import class_index


@pytest.fixture(scope="module")
def silent() -> S.Profile:
    p = S.load_profiles()["tight"]
    return replace(p, by_seat={}, **dict.fromkeys(S.RATES, 0.0))


def test_the_model() -> None:
    assert S.R["threebet_ip"] == 0.85 and S.R["threebet_oop"] == 0.75
    assert not S.OPENER_SLOPE and S.opener("CO").slope == 0.0


def test_bar1_gate_z_closed_forms_at_the_new_model(silent, monkeypatch) -> None:
    monkeypatch.setattr(S, "COLD_4BET", 0.0)
    for size in S.OPEN_SIZES:
        for ante in ANTES:
            folds = S.OpenSpot("BTN", _opener("CO", "random", 0.0, 0.0), size, ante)
            call = S.OpenSpot("BB", _opener("SB", "KK", 0.0, 0.0), size, ante)
            called = S.OpenSpot("BTN", _opener("CO", "QQ", 0.0, 1.0), size, ante)
            four = S.OpenSpot("BTN", _opener("CO", "AA", 1.0, 0.0), size, ante)
            allin = 2 * (100 - ante) + 6 * ante + 1.5
            for hand in HANDS:
                ev = _ev(folds, silent, hand)
                assert all(
                    ev[n] == pytest.approx(folds.pot, abs=1e-9) for n in folds.action_names()[2:]
                )
                want = 0.85 * M(hand, "KK") * (6 * ante + 2 * size) - (size - 1)
                assert _ev(call, silent, hand)["call"] == pytest.approx(want, abs=1e-9)
                ev = _ev(called, silent, hand)
                for x in called.sizes:
                    want = 0.85 * M(hand, "QQ") * (6 * ante + 1.5 + 2 * x) - x
                    assert ev[f"3-bet to {x:g}"] == pytest.approx(want, abs=1e-9)
                ev = _ev(four, silent, hand)
                stack = M(hand, "AA") * allin - (100 - ante)
                assert ev["jam"] == pytest.approx(stack, abs=1e-9)
                for x in four.sizes:
                    want = stack if hand == "AA" else -x
                    assert ev[f"3-bet to {x:g}"] == pytest.approx(want, abs=1e-9)


def test_bar1_the_opener_calls_the_same_share_at_both_sizes() -> None:
    op = S.Opener("CO", "standard", 0.27, 0.12, 0.33, 0.0)
    spot = S.OpenSpot("BTN", op, 2.5, 0.0)
    d = S.deal(spot, S.load_profiles()["standard"], samples=4_000)
    table = S.outcome_table(d)
    shares = [o.callers.any(axis=1).mean() for o in table[0.0][1:3]]
    assert shares[0] == shares[1] > 0


def test_unopened_and_limped_answers_are_unchanged(monkeypatch) -> None:
    std = S.load_profiles()["standard"]
    spots = [S.Spot("BTN", 1, 0.5), S.Spot("CO"), S.Spot("BB", 2)]
    now = [S.answer(s, std, class_index("KJo"), samples=3_000).ev for s in spots]
    monkeypatch.setattr(S, "OPENER_SLOPE", S.GATED_OPENER_SLOPE)
    monkeypatch.setitem(S.R, "threebet_ip", S.GATED_THREEBET_IP)
    before = [S.answer(s, std, class_index("KJo"), samples=3_000).ev for s in spots]
    assert all(np.array_equal(a, b) for a, b in zip(now, before, strict=True))
