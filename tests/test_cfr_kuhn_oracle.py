"""Our Kuhn, best response and CFR against OpenSpiel's (DECISIONS 6, 15)."""

import random

import pytest
from openspiel_oracle import (
    from_openspiel_policy,
    load,
    lockstep,
    os_exploitability,
    solver_from_openspiel,
    to_openspiel_policy,
)

from showdown.cfr import CFRSolver, compile_game, exploitability, uniform_policy
from showdown.games import load_game


@pytest.fixture(scope="module")
def kuhn():
    game = load_game("kuhn")
    os_game = load("kuhn_poker")
    mapping = lockstep(game, os_game)
    return compile_game(game), os_game, mapping


def random_policy(tree, seed: int):
    rng = random.Random(seed)
    policy = []
    for actions in tree.infoset_actions:
        weights = [rng.random() for _ in actions]
        policy.append([w / sum(weights) for w in weights])
    return policy


def test_same_game_and_same_infosets(kuhn) -> None:
    tree, _, mapping = kuhn
    assert len(mapping) == tree.num_infosets == 12


@pytest.mark.parametrize("seed", [None, 1, 2, 3])
def test_exploitability_matches_openspiel(kuhn, seed) -> None:
    tree, os_game, mapping = kuhn
    policy = uniform_policy(tree) if seed is None else random_policy(tree, seed)
    theirs = os_exploitability.exploitability(
        os_game, to_openspiel_policy(tree, policy, mapping, os_game)
    )
    assert exploitability(tree, policy) == pytest.approx(theirs, abs=1e-9)


@pytest.mark.parametrize(
    ("alternating", "linear", "plus"),
    [(True, False, False), (True, True, True), (False, False, False), (False, True, True)],
    ids=["cfr", "cfr+", "cfr-simultaneous", "cfr+-simultaneous"],
)
def test_cfr_trajectory_equals_openspiel(kuhn, alternating, linear, plus) -> None:
    """Same flags, same update order: bit-identical policies (DECISIONS 15)."""
    tree, os_game, mapping = kuhn
    ours = CFRSolver(
        tree, alternating_updates=alternating, linear_averaging=linear, regret_matching_plus=plus
    )
    theirs = solver_from_openspiel(os_game, alternating=alternating, linear=linear, plus=plus)
    for iteration in range(1, 61):
        ours.iterate()
        theirs.evaluate_and_update_policy()
        if iteration in (1, 2, 3, 10, 60):
            for mine, other in (
                (ours.average_policy(), theirs.average_policy()),
                (ours.current_policy(), theirs.current_policy()),
            ):
                assert mine == from_openspiel_policy(tree, other, mapping)
