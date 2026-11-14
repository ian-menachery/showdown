"""Our Leduc, best response and CFR against OpenSpiel's (Gate B fast checks)."""

import random

import pytest
from openspiel_oracle import (
    from_openspiel_policy,
    load,
    lockstep,
    os_cfr,
    os_exploitability,
    to_openspiel_policy,
)

from showdown.cfr import cfr_plus, compile_game, exploitability, uniform_policy
from showdown.games import load_game


@pytest.fixture(scope="module")
def leduc():
    game = load_game("leduc")
    os_game = load("leduc_poker")
    mapping = lockstep(game, os_game)
    return compile_game(game), os_game, mapping


def test_same_game_and_same_infosets(leduc) -> None:
    tree, _, mapping = leduc
    assert len(mapping) == tree.num_infosets == 936


def _seeded_random(tree, seed: int):
    rng = random.Random(seed)
    policy = []
    for actions in tree.infoset_actions:
        weights = [rng.random() for _ in actions]
        policy.append([w / sum(weights) for w in weights])
    return policy


def _cfr_plus_iterate(tree, iterations: int):
    solver = cfr_plus(tree)
    solver.iterate(iterations)
    return solver.average_policy()


@pytest.mark.parametrize("which", ["uniform", "seeded-random", "cfr+-iterate"])
def test_gate_b_exploitability_matches_openspiel(leduc, which) -> None:
    """Gate B, first bullet: three policies, agreement to 1e-9."""
    tree, os_game, mapping = leduc
    policy = {
        "uniform": lambda: uniform_policy(tree),
        "seeded-random": lambda: _seeded_random(tree, 2026),
        "cfr+-iterate": lambda: _cfr_plus_iterate(tree, 25),
    }[which]()
    theirs = os_exploitability.exploitability(
        os_game, to_openspiel_policy(tree, policy, mapping, os_game)
    )
    assert exploitability(tree, policy) == pytest.approx(theirs, abs=1e-9)


def test_cfr_plus_first_iterations_bit_identical_to_openspiel(leduc) -> None:
    """Leduc has 3-action infosets, where float summation order shows (DECISIONS 15)."""
    tree, os_game, mapping = leduc
    ours = cfr_plus(tree)
    theirs = os_cfr.CFRPlusSolver(os_game)
    for _ in range(5):
        ours.iterate()
        theirs.evaluate_and_update_policy()
        assert ours.average_policy() == from_openspiel_policy(
            tree, theirs.average_policy(), mapping
        )
        assert ours.current_policy() == from_openspiel_policy(
            tree, theirs.current_policy(), mapping
        )
