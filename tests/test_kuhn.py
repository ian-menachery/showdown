"""Kuhn rules and the compiled tree."""

import pytest

from showdown.cfr import compile_game, policy_from_dict, policy_to_dict, uniform_policy
from showdown.games import CHANCE, TERMINAL, load_game
from showdown.games.kuhn import BET, PASS, KuhnState


def play(*steps: int) -> KuhnState:
    state = KuhnState()
    for step in steps:
        state = state.child(step)
    return state


def test_tree_shape_matches_openspiel_counts() -> None:
    tree = compile_game(load_game("kuhn"))
    assert tree.num_nodes == 58  # 4 chance + 24 decision + 30 terminal
    assert tree.num_infosets == 12
    assert sorted(tree.player).count(TERMINAL) == 30
    assert tree.player.count(CHANCE) == 4


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        ((2, 0, PASS, PASS), (1.0, -1.0)),  # K vs J, check down
        ((0, 2, PASS, PASS), (-1.0, 1.0)),
        ((2, 0, BET, PASS), (1.0, -1.0)),  # player 1 folds
        ((0, 2, BET, BET), (-2.0, 2.0)),  # called, J loses 2
        ((2, 1, PASS, BET, PASS), (-1.0, 1.0)),  # player 0 folds after check-bet
        ((2, 1, PASS, BET, BET), (2.0, -2.0)),
    ],
)
def test_returns(steps: tuple[int, ...], expected: tuple[float, float]) -> None:
    state = play(*steps)
    assert state.current_player() == TERMINAL
    assert state.returns() == expected


def test_information_state_hides_opponent_card() -> None:
    assert play(2, 0).information_state() == "K:"
    assert play(2, 1).information_state() == "K:"
    assert play(0, 2, PASS).information_state() == "K:p"
    assert play(1, 2, PASS, BET).information_state() == "Q:pb"


def test_chance_deals_without_replacement() -> None:
    assert play().chance_outcomes() == [(0, 1 / 3), (1, 1 / 3), (2, 1 / 3)]
    assert play(1).chance_outcomes() == [(0, 0.5), (2, 0.5)]


def test_policy_dict_round_trip() -> None:
    tree = compile_game(load_game("kuhn"))
    policy = uniform_policy(tree)
    policy[tree.infoset_id("K:")] = [0.25, 0.75]
    table = policy_to_dict(tree, policy)
    assert table["K:"] == {"pass": 0.25, "bet": 0.75}
    assert policy_from_dict(tree, table) == policy


def test_unknown_game() -> None:
    with pytest.raises(ValueError, match="unknown game"):
        load_game("chess")
