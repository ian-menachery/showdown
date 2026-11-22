"""The six-max spot engine's pieces and `showdown sixmax` (DECISIONS 53)."""

import numpy as np
import pytest
from test_gate_m import profile

from showdown import sixmax as S
from showdown.cli import main
from showdown.equity.cards import class_index


def test_spot_rules() -> None:
    for bad in (("MP", 0), ("UTG", 1), ("CO", 3), ("BB", 0), ("BTN", 4)):
        with pytest.raises(ValueError):
            S.Spot(*bad)
    with pytest.raises(ValueError):
        S.Spot("BTN", 1, -0.5)
    spot = S.Spot("CO", 2, 0.5)
    assert spot.sizes == (5.0, 6.0, 7.0)
    assert spot.pot == 6.5
    assert spot.opponents() == [
        ("behind", "BTN"),
        ("SB", "SB"),
        ("BB", "BB"),
        ("limper", "UTG"),
        ("limper", "HJ"),
    ]
    assert S.Spot("UTG").action_names() == ["fold", "limp", "open to 2.5", "open to 3", "open to 4"]
    assert S.Spot("SB", 1).action_names()[:2] == ["fold", "complete"]
    assert S.Spot("BB", 3).action_names() == ["check", "raise to 6", "raise to 7", "raise to 8"]
    assert S.Spot("BB", 1, 0.5).dead == 3.5
    assert [k for k, _ in S.Spot("BB", 2).opponents()] == ["limper", "limper"]


def test_ranges_and_hands() -> None:
    w = S.class_mass(S.from_text("TT+, A2s-A5s, KTs+, AJo")) / S.CLASS_SIZES
    assert S.range_text(w) == "TT+, A2s-A5s, KTs+, AJo"
    assert S.range_text(np.zeros(169)) == "none"
    assert S.share_of_hands(S.top(S.ALL_HANDS, 0.1)) == pytest.approx(0.1)
    assert S.share_of_hands(S.band(S.ALL_HANDS, 0.2, 0.5)) == pytest.approx(0.3)
    p = profile(open_raise=0.1, limp=0.3, limp_range=None)
    assert S.share_of_hands(S.class_mass(p.limp_weights()) / S.CLASS_SIZES) == pytest.approx(0.3)
    top = S.top(S.ALL_HANDS, 0.02)
    assert top[class_index("AA")] == 1.0 and top[class_index("72o")] == 0.0
    assert S.parse_hand("a5S") == class_index("A5s")
    assert S.parse_hand("5sAs") == S.parse_hand("As5s") == (51, 15)
    for bad in ("AsK", "AsKsQs"):
        with pytest.raises(ValueError):
            S.parse_hand(bad)


def test_a_blocked_hand_is_refused() -> None:
    p = profile(limp_range="AsKs")
    with pytest.raises(ValueError, match="no deal"):
        S.answer(S.Spot("BTN", 1), p, S.parse_hand("AsKs"), samples=200)


def test_tiers_and_seeds() -> None:
    p = profile(limp_range="AA", iso_reraise=1.0)
    aa = S.answer(S.Spot("BB", 1), p, class_index("AA"), samples=1_000)
    # No one behind the BB, so every raise size stacks off for the same EV: a toss-up.
    assert aa.ev[1:].tolist() == pytest.approx([0.5 * 200.5 - 99] * 3)
    assert aa.best == "raise to 4" and aa.no_stackoff_best == "check" and not aa.flips
    assert aa.tier == "review" and aa.gap_se == 0.0
    spot = S.Spot("BTN", 1)
    loose = profile(limp_range="random", iso_fold=0.3, bb_call=0.4, sb_call=0.2)
    one = S.answer(spot, loose, class_index("A5s"), samples=3_000, seed=4)
    two = S.answer(spot, loose, class_index("A5s"), samples=3_000, seed=4)
    assert np.array_equal(one.ev, two.ev)
    assert one.tier in ("clear", "close", "review")
    junk = S.answer(spot, loose, class_index("72o"), samples=3_000)
    assert junk.best == "fold" and junk.tier == "clear"
    charted = S.chart(S.Spot("SB", 0), loose, samples=300)
    assert len(charted) == 169 and charted[0].hand == "AA"


def test_profiles_file() -> None:
    profiles = S.load_profiles()
    assert set(profiles) == {"standard", "tight", "regular", "loose-passive"}
    for p in profiles.values():
        assert set(p.source) == set(S.RATES)
        for rate in S.RATES:
            value = getattr(p, rate)
            assert (-1 < value < 1) if rate.endswith("slope") else (0 <= value <= 1)


def test_cli_prints_ranges_evs_and_a_tier(capsys) -> None:
    argv = ["sixmax", "BTN", "A5s", "--limpers", "2", "--ante", "0.5"]
    assert main([*argv, "--profile", "loose-passive", "--samples", "4000"]) == 0
    out = capsys.readouterr().out
    for text in (
        "BTN with A5s: 2 limpers ahead",
        "Each limper: limp range",
        "SB, facing a raise",
        "Facing your overlimp",
        "EV of each action",
        "iso to 6",
        "Verdict:",
    ):
        assert text in out
    assert main(["sixmax", "UTG", "AsAh", "--profile", "regular", "--samples", "2000"]) == 0
    out = capsys.readouterr().out
    assert "unopened" in out and "Each player behind" in out and "fitted to 2009" in out
    assert "Verdict: CLOSE" in out and "only the size is close" in out
    assert "the best is open to 2.5" in out  # without stack-offs
    assert main(["sixmax", "BTN", "K9o", "--samples", "2000"]) == 0
    out = capsys.readouterr().out
    assert "Opponents: standard" in out and "call 44% (assumed)" in out
    with pytest.raises(SystemExit, match="limpers ahead"):
        main(["sixmax", "UTG", "AA", "--limpers", "1"])
