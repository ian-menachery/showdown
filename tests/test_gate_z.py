"""Gate Z, bar 1 (DECISIONS 61): closed forms facing one open raise, worked by hand from the
matrix, to 1e-9. Plus the spot's shape and the CLI."""

from dataclasses import replace

import pytest

from showdown import sixmax as S
from showdown.cli import main
from showdown.equity.cards import class_index

HANDS = ("AA", "KK", "A5s", "72o")
ANTES = (0.0, 0.5)
SAMPLES = 2_000


@pytest.fixture(scope="module")
def silent() -> S.Profile:
    """Every rate 0: players behind fold to anything."""
    p = S.load_profiles()["tight"]
    return replace(p, by_seat={}, **dict.fromkeys(S.RATES, 0.0))


def _opener(seat: str, fixed: str, four_bet: float, call: float) -> S.Opener:
    return S.Opener(seat, "standard", 0.5, four_bet, call, 0.0, fixed=fixed)


def _ev(spot, profile, hand: str) -> dict[str, float]:
    a = S.answer(spot, profile, class_index(hand), samples=SAMPLES)
    return dict(zip(a.actions, (float(e) for e in a.ev), strict=True))


def M(a: str, b: str) -> float:
    return float(S.matrix().equity[class_index(a), class_index(b)])


def test_the_spot() -> None:
    op = S.opener("CO", "standard")
    spot = S.OpenSpot("BB", op, 3.0, 0.5)
    assert spot.pot == 3 + 1.5 + 3 and spot.dead == 3 + 0.5 and spot.sizes == (9.0, 12.0)
    assert spot.action_names() == ["fold", "call", "3-bet to 9", "3-bet to 12", "jam"]
    assert S.OpenSpot("BB", S.opener("SB"), 2.5).pot == 3.5
    assert [k for k, _ in S.OpenSpot("HJ", S.opener("UTG")).opponents()] == [
        "behind",
        "behind",
        "SB",
        "BB",
        "opener",
    ]
    for bad in (("UTG", "CO"), ("CO", "CO")):
        with pytest.raises(ValueError):
            S.OpenSpot(bad[0], S.opener(bad[1]))
    with pytest.raises(ValueError):
        S.OpenSpot("BTN", op, 2.0)
    assert S.kind("call") == "call" and S.kind("jam") == "raise" and S.kind("check") == "limp"
    nit, std = S.opener("CO", "nit"), S.opener("CO")
    assert nit.width < std.width == 0.27 and std.four_bet == 0.12 and std.call == 0.33


def test_bar1_everyone_folds(silent, monkeypatch) -> None:
    monkeypatch.setattr(S, "COLD_4BET", 0.0)
    for hero, seat in (("BTN", "CO"), ("BB", "SB")):
        for size in S.OPEN_SIZES:
            for ante in ANTES:
                spot = S.OpenSpot(hero, _opener(seat, "random", 0.0, 0.0), size, ante)
                for hand in HANDS:
                    ev = _ev(spot, silent, hand)
                    for name in spot.action_names()[2:]:
                        assert ev[name] == pytest.approx(spot.pot, abs=1e-9), (spot, hand, name)


def test_bar1_a_call_heads_up(silent) -> None:
    for size in S.OPEN_SIZES:
        for ante in ANTES:
            spot = S.OpenSpot("BB", _opener("SB", "KK", 0.0, 0.0), size, ante)
            for hand in HANDS:
                want = 0.85 * M(hand, "KK") * (6 * ante + 2 * size) - (size - 1)
                assert _ev(spot, silent, hand)["call"] == pytest.approx(want, abs=1e-9)


def test_bar1_a_3bet_called(silent, monkeypatch) -> None:
    monkeypatch.setattr(S, "COLD_4BET", 0.0)
    for size in S.OPEN_SIZES:
        for ante in ANTES:
            spot = S.OpenSpot("BTN", _opener("CO", "QQ", 0.0, 1.0), size, ante)
            for hand in HANDS:
                ev = _ev(spot, silent, hand)
                for x in spot.sizes:
                    want = 1.00 * M(hand, "QQ") * (6 * ante + 1.5 + 2 * x) - x
                    assert ev[f"3-bet to {x:g}"] == pytest.approx(want, abs=1e-9)


def test_bar1_a_4bet_and_the_jam_called(silent, monkeypatch) -> None:
    monkeypatch.setattr(S, "COLD_4BET", 0.0)
    for size in S.OPEN_SIZES:
        for ante in ANTES:
            spot = S.OpenSpot("BTN", _opener("CO", "AA", 1.0, 0.0), size, ante)
            allin = 2 * (100 - ante) + 6 * ante + 1.5
            for hand in HANDS:
                ev = _ev(spot, silent, hand)
                called = M(hand, "AA") * allin - (100 - ante)
                assert ev["jam"] == pytest.approx(called, abs=1e-9)
                for x in spot.sizes:
                    want = called if hand == "AA" else -x
                    assert ev[f"3-bet to {x:g}"] == pytest.approx(want, abs=1e-9), (hand, x)


def test_the_command(capsys) -> None:
    args = ["sixmax", "BB", "A5s", "--opener", "CO", "--opener-type", "nit", "--samples", "1500"]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "CO opens to 2.5 bb" in out and "Opener: Nit (" in out and "3-bet to 7.5" in out
    with pytest.raises(SystemExit, match="after the opener"):
        main(["sixmax", "UTG", "AA", "--opener", "CO"])
