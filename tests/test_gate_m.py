"""Gate M, bar 1: the six-max engine against hand-worked closed forms (DECISIONS 53).

Each expected value is worked from the exact matrix and the spot's chips, not through
the engine. The first four spots must match to 1e-9; the 3-way pot is within 4 combined
standard errors of `multiway.pot_shares`.
"""

import math

import pytest

from showdown import sixmax as S
from showdown.equity.cards import class_index, parse_cards
from showdown.equity.multiway import pot_shares

HANDS = ("AA", "KK", "A5s", "72o")
SAMPLES = 2_000


def profile(**rates) -> S.Profile:
    """Every rate 0 unless given: nobody calls, raises or re-raises."""
    base = dict.fromkeys(S.RATES, 0.0)
    limp_range = rates.pop("limp_range", "random")
    return S.Profile(name="test", limp_range=limp_range, **(base | rates))


def m(hero: str, villain: str) -> float:
    return float(S.matrix().equity[class_index(hero), class_index(villain)])


def ev(spot: S.Spot, p: S.Profile, hand, action: str, samples: int = SAMPLES) -> S.Answer:
    a = S.answer(spot, p, hand, samples=samples)
    return a, float(a.ev[a.actions.index(action)])


@pytest.mark.parametrize("ante", [0.0, 0.5])
def test_everyone_folds_wins_the_pot(ante) -> None:
    p = profile(iso_fold=1.0)
    for seat, most in S.MAX_LIMPERS.items():
        for k in range(1 if seat == "BB" else 0, most + 1):
            spot = S.Spot(seat, k, ante)
            for hand in HANDS:
                a = S.answer(spot, p, S.parse_hand(hand), samples=500)
                raises = [i for i, n in enumerate(a.actions) if " to " in n]
                assert len(raises) == 3
                for i in raises:
                    assert abs(a.ev[i] - spot.pot) < 1e-9, (seat, k, hand, a.actions[i])
                assert spot.pot == 6 * ante + 1.5 + k


@pytest.mark.parametrize("ante", [0.0, 0.5])
@pytest.mark.parametrize("hand", HANDS)
def test_one_caller_with_a_fixed_range(ante, hand) -> None:
    spot = S.Spot("BTN", 1, ante)
    p = profile(limp_range="KK", iso_fold=0.0)
    a = S.answer(spot, p, class_index(hand), samples=SAMPLES)
    for x in spot.sizes:
        pot = 6 * ante + 0.5 + 1.0 + 2 * x
        expected = 1.00 * m(hand, "KK") * pot - x
        assert abs(a.ev[a.actions.index(f"iso to {x:g}")] - expected) < 1e-9


@pytest.mark.parametrize("ante", [0.0, 0.5])
@pytest.mark.parametrize("hand", HANDS)
def test_limped_pot_with_the_bb(ante, hand) -> None:
    spot = S.Spot("BB", 1, ante)
    p = profile(limp_range="QQ")
    _, got = ev(spot, p, class_index(hand), "check")
    assert abs(got - 0.75 * m(hand, "QQ") * (2.5 + 6 * ante)) < 1e-9


@pytest.mark.parametrize("ante", [0.0, 0.5])
def test_stack_off_against_a_limp_reraise(ante) -> None:
    spot = S.Spot("BTN", 1, ante)
    p = profile(limp_range="AA", iso_reraise=1.0)
    kk = S.answer(spot, p, class_index("KK"), samples=SAMPLES)
    aa = S.answer(spot, p, class_index("AA"), samples=SAMPLES)
    allin_pot = 2 * (100 - ante) + 6 * ante + 1.5
    for x in spot.sizes:
        name = f"iso to {x:g}"
        assert abs(kk.ev[kk.actions.index(name)] - (-x)) < 1e-9
        assert abs(aa.ev[aa.actions.index(name)] - (0.5 * allin_pot - (100 - ante))) < 1e-9


def test_three_way_pot_matches_multiway() -> None:
    spot = S.Spot("BTN", 2, 0.5)
    p = profile(limp_range="KhKd, QcQs", iso_fold=0.0)
    hero = S.parse_hand("AsAh")
    a = S.answer(spot, p, hero, samples=40_000)
    hands = {0: parse_cards("AsAh"), 1: parse_cards("KhKd"), 2: parse_cards("QcQs")}
    shares = pot_shares(hands, (), [(1.0, (0, 1, 2))], samples=200_000, seed=0)
    assert shares.method == "monte-carlo"
    for x in spot.sizes:
        pot = 6 * 0.5 + 1.5 + 3 * x
        expected = 1.00 * shares.expected[0] * pot - x
        i = a.actions.index(f"iso to {x:g}")
        se = math.hypot(a.se[i], pot * shares.se[0])
        assert abs(a.ev[i] - expected) <= 4 * se, (x, a.ev[i], expected, se)
