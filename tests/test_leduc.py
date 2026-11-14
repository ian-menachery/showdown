"""Leduc rules, checked by hand without OpenSpiel."""

import pytest

from showdown.cfr import compile_game, exploitability, uniform_policy
from showdown.games import CHANCE, TERMINAL, load_game
from showdown.games.leduc import CALL, FOLD, RAISE, LeducState, card_name


def deal(p0: int, p1: int, *steps: int) -> LeducState:
    state = LeducState().child(p0).child(p1)
    for step in steps:
        state = state.child(step)
    return state


def test_tree_counts() -> None:
    tree = compile_game(load_game("leduc"))
    assert tree.player.count(CHANCE) == 157
    assert tree.player.count(TERMINAL) == 5520
    assert sum(1 for p in tree.player if p in (0, 1)) == 3780
    assert tree.num_infosets == 936


def test_uniform_exploitability() -> None:
    tree = compile_game(load_game("leduc"))
    assert exploitability(tree, uniform_policy(tree)) == pytest.approx(2.3736111111, abs=1e-9)


def test_legal_actions() -> None:
    assert deal(4, 1).legal_actions() == (CALL, RAISE)  # nothing to fold to
    assert deal(4, 1, RAISE).legal_actions() == (FOLD, CALL, RAISE)
    assert deal(4, 1, RAISE, RAISE).legal_actions() == (FOLD, CALL)  # two raises max


def test_round_flow() -> None:
    assert deal(4, 1, CALL).current_player() == 1
    assert deal(4, 1, CALL, CALL).current_player() == CHANCE
    assert deal(4, 1, RAISE, CALL).current_player() == CHANCE
    assert deal(4, 1, CALL, RAISE, CALL).current_player() == CHANCE
    assert deal(4, 1, CALL, CALL, 3).current_player() == 0  # player 0 opens round 2
    assert deal(4, 1, CALL, CALL).chance_outcomes() == [(c, 0.25) for c in (0, 2, 3, 5)]


@pytest.mark.parametrize(
    ("p0", "p1", "steps", "expected"),
    [
        (4, 1, (RAISE, FOLD), (1.0, -1.0)),
        (4, 1, (RAISE, RAISE, FOLD), (-3.0, 3.0)),  # 1 ante + 2 raise
        (4, 1, (CALL, CALL, 3, RAISE, RAISE, CALL), (9.0, -9.0)),  # 1 + 4 + 4, K high
        (4, 1, (CALL, CALL, 3, RAISE, RAISE, FOLD), (-5.0, 5.0)),
        (0, 1, (CALL, CALL, 4, CALL, CALL), (0.0, 0.0)),  # J vs J split
        (0, 4, (CALL, CALL, 1, CALL, CALL), (1.0, -1.0)),  # pair of J beats K
        (4, 2, (RAISE, CALL, 0, RAISE, CALL), (7.0, -7.0)),  # 3 + 4 each; K beats Q, J board
    ],
)
def test_returns(p0, p1, steps, expected) -> None:
    state = deal(p0, p1, *steps)
    assert state.current_player() == TERMINAL
    assert state.returns() == expected


def test_information_state() -> None:
    assert deal(4, 1).information_state() == "Ks:"
    assert deal(4, 1, CALL).information_state() == "Jh:c"
    assert deal(4, 1, CALL, RAISE).information_state() == "Ks:cr"
    assert deal(4, 1, CALL, CALL, 3, RAISE).information_state() == "JhQh:cc/r"
    assert card_name(5) == "Kh"
