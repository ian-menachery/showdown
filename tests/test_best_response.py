"""Best response properties that hold without any oracle."""

import random

import pytest

from showdown.cfr import (
    best_response,
    cfr_plus,
    compile_game,
    exploitability,
    nash_conv,
    policy_value,
    uniform_policy,
)
from showdown.games import load_game


@pytest.fixture(scope="module")
def tree():
    return compile_game(load_game("kuhn"))


def test_uniform_kuhn_known_value(tree) -> None:
    # 11/24: the uniform policy's exploitability in Kuhn (OpenSpiel agrees, see oracle test).
    assert exploitability(tree, uniform_policy(tree)) == pytest.approx(11 / 24, abs=1e-12)
    assert policy_value(tree, uniform_policy(tree)) == pytest.approx(1 / 8, abs=1e-12)


def test_best_response_is_pure_and_achieves_its_value(tree) -> None:
    policy = uniform_policy(tree)
    for responder in (0, 1):
        value, br_policy = best_response(tree, policy, responder)
        for info, owner in enumerate(tree.infoset_player):
            if owner == responder:
                assert sorted(br_policy[info]) == [0.0, 1.0]
            else:
                assert br_policy[info] == policy[info]
        sign = 1 if responder == 0 else -1
        assert sign * policy_value(tree, br_policy) == pytest.approx(value, abs=1e-12)


def test_nash_conv_non_negative_and_near_zero_at_equilibrium(tree) -> None:
    rng = random.Random(7)
    for _ in range(20):
        policy = []
        for actions in tree.infoset_actions:
            w = [rng.random() for _ in actions]
            policy.append([x / sum(w) for x in w])
        assert nash_conv(tree, policy) >= -1e-12
    solver = cfr_plus(tree)
    solver.iterate(2000)
    assert nash_conv(tree, solver.average_policy()) < 1e-4
