"""Gate A, Kuhn (SCOPE). Thresholds are pre-registered; do not loosen them.

The first bullet (uniform exploitability matches OpenSpiel to 1e-9) lives in
test_cfr_kuhn_oracle.py so that this module runs without OpenSpiel.
"""

import pytest

from showdown.cfr import cfr_plus, compile_game, exploitability, policy_value
from showdown.games import load_game

ITERATIONS = 1_000


@pytest.fixture(scope="module")
def solved():
    tree = compile_game(load_game("kuhn"))
    solver = cfr_plus(tree)
    solver.iterate(ITERATIONS)
    return tree, solver.average_policy()


def bet(tree, policy, key: str) -> float:
    """Probability of the second action (bet or call) at infoset `key`."""
    return policy[tree.infoset_id(key)][1]


def test_exploitability_below_1e_3(solved) -> None:
    tree, policy = solved
    assert exploitability(tree, policy) < 1e-3


def test_first_player_value_is_minus_one_eighteenth(solved) -> None:
    tree, policy = solved
    assert policy_value(tree, policy) == pytest.approx(-1 / 18, abs=1e-3)


def test_first_player_in_equilibrium_family(solved) -> None:
    """Bet J with alpha in [0, 1/3], bet K with 3 alpha, call with Q at alpha + 1/3."""
    tree, policy = solved
    alpha = bet(tree, policy, "J:")
    assert -0.02 <= alpha <= 1 / 3 + 0.02
    assert bet(tree, policy, "K:") == pytest.approx(3 * alpha, abs=0.02)
    assert bet(tree, policy, "Q:pb") == pytest.approx(alpha + 1 / 3, abs=0.02)
    # Implied by the same family: Q never bets first, J always folds, K always calls.
    assert bet(tree, policy, "Q:") == pytest.approx(0.0, abs=0.02)
    assert bet(tree, policy, "J:pb") == pytest.approx(0.0, abs=0.02)
    assert bet(tree, policy, "K:pb") == pytest.approx(1.0, abs=0.02)


def test_second_player_equilibrium(solved) -> None:
    """Player 2's equilibrium strategy is unique. Not a gate bullet; a cross-check."""
    tree, policy = solved
    assert bet(tree, policy, "K:b") == pytest.approx(1.0, abs=0.02)
    assert bet(tree, policy, "K:p") == pytest.approx(1.0, abs=0.02)
    assert bet(tree, policy, "Q:b") == pytest.approx(1 / 3, abs=0.02)
    assert bet(tree, policy, "Q:p") == pytest.approx(0.0, abs=0.02)
    assert bet(tree, policy, "J:b") == pytest.approx(0.0, abs=0.02)
    assert bet(tree, policy, "J:p") == pytest.approx(1 / 3, abs=0.02)
