"""OpenSpiel as a reference answer for tests only (DECISIONS 6).

Nothing in src/ imports this. Importing it skips the calling test module when
OpenSpiel is not installed. Skips are printed by `py gate.py`, and they never
count toward a gate pass.
"""

from __future__ import annotations

import math

import pytest

pyspiel = pytest.importorskip("pyspiel")

from open_spiel.python import policy as os_policy  # noqa: E402
from open_spiel.python.algorithms import cfr as os_cfr  # noqa: E402
from open_spiel.python.algorithms import exploitability as os_exploitability  # noqa: E402

from showdown.cfr.tree import Policy, Tree  # noqa: E402
from showdown.games.base import CHANCE, TERMINAL, Game  # noqa: E402

__all__ = [
    "lockstep",
    "load",
    "os_cfr",
    "os_exploitability",
    "solver_from_openspiel",
    "to_openspiel_policy",
    "from_openspiel_policy",
]


def load(name: str):
    return pyspiel.load_game(name)


def lockstep(game: Game, os_game) -> dict[str, str]:
    """Walk our game and OpenSpiel's together and assert they are the same game.

    At every node: same node type, same acting player, same legal actions, same
    chance outcomes and probabilities, and same terminal returns. Returns the map
    from our infoset keys to OpenSpiel's info-state strings, and asserts that it
    is one-to-one: the two games partition histories into the same infosets.
    """
    ours_to_theirs: dict[str, str] = {}
    theirs_to_ours: dict[str, str] = {}

    def walk(ours, theirs, path: tuple[int, ...]) -> None:
        kind = ours.current_player()
        if theirs.is_terminal():
            assert kind == TERMINAL, path
            for mine, other in zip(ours.returns(), theirs.returns(), strict=True):
                assert math.isclose(mine, other, abs_tol=1e-12), (path, ours.returns())
            return
        if theirs.is_chance_node():
            assert kind == CHANCE, path
            mine = list(ours.chance_outcomes())
            other = list(theirs.chance_outcomes())
            assert [o for o, _ in mine] == [o for o, _ in other], path
            for (_, p), (_, q) in zip(mine, other, strict=True):
                assert math.isclose(p, q, abs_tol=1e-12), path
            for outcome, _ in mine:
                walk(ours.child(outcome), theirs.child(outcome), path + (outcome,))
            return
        assert kind == theirs.current_player(), path
        assert tuple(ours.legal_actions()) == tuple(theirs.legal_actions()), path
        key = ours.information_state()
        other_key = theirs.information_state_string(kind)
        assert ours_to_theirs.setdefault(key, other_key) == other_key, (path, key)
        assert theirs_to_ours.setdefault(other_key, key) == key, (path, other_key)
        for action in ours.legal_actions():
            walk(ours.child(action), theirs.child(action), path + (action,))

    walk(game.initial_state(), os_game.new_initial_state(), ())
    return ours_to_theirs


def to_openspiel_policy(tree: Tree, policy: Policy, mapping: dict[str, str], os_game):
    table = os_policy.TabularPolicy(os_game)
    for info, key in enumerate(tree.infoset_key):
        row = table.policy_for_key(mapping[key])
        row[:] = 0.0
        for action, prob in zip(tree.infoset_actions[info], policy[info], strict=True):
            row[action] = prob
    return table


def from_openspiel_policy(tree: Tree, table, mapping: dict[str, str]) -> Policy:
    out = []
    for info, key in enumerate(tree.infoset_key):
        row = table.policy_for_key(mapping[key])
        out.append([float(row[a]) for a in tree.infoset_actions[info]])
    return out


def solver_from_openspiel(os_game, *, alternating: bool, linear: bool, plus: bool):
    return os_cfr._CFRSolver(
        os_game,
        alternating_updates=alternating,
        linear_averaging=linear,
        regret_matching_plus=plus,
    )
