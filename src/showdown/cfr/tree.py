"""Compile a game into flat arrays that the solvers loop over.

Nodes are numbered in preorder, so every child has a larger id than its parent:
a forward loop over node ids visits parents before children, and a reverse loop
visits children before parents. CFR and best response run on these lists
without recursion or per-node objects (DECISIONS 14).

A policy is a list with one entry per information set: the probabilities of
that infoset's actions, in the order of `Tree.infoset_actions`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from showdown.games.base import CHANCE, TERMINAL, Game

Policy = list[list[float]]

_ZERO_SUM_TOLERANCE = 1e-12


@dataclass
class Tree:
    """A compiled two-player zero-sum game. Node 0 is the root."""

    game: Game
    player: list[int] = field(default_factory=list)
    """Per node: 0 or 1 at a decision, CHANCE or TERMINAL."""
    children: list[tuple[int, ...]] = field(default_factory=list)
    labels: list[tuple[int, ...]] = field(default_factory=list)
    """Per node: the action or chance outcome leading to each child."""
    chance_probs: list[tuple[float, ...]] = field(default_factory=list)
    infoset: list[int] = field(default_factory=list)
    """Per node: infoset id at a decision node, else -1."""
    utility: list[float] = field(default_factory=list)
    """Per node: payoff to player 0 at a terminal, else 0.0."""
    infoset_key: list[str] = field(default_factory=list)
    infoset_player: list[int] = field(default_factory=list)
    infoset_actions: list[tuple[int, ...]] = field(default_factory=list)
    infoset_nodes: list[list[int]] = field(default_factory=list)
    _infoset_ids: dict[str, int] = field(default_factory=dict, repr=False)

    @property
    def num_nodes(self) -> int:
        return len(self.player)

    @property
    def num_infosets(self) -> int:
        return len(self.infoset_key)

    def infoset_id(self, key: str) -> int:
        return self._infoset_ids[key]

    def internal_nodes(self) -> list[int]:
        """Chance and decision nodes, in preorder."""
        return [n for n, p in enumerate(self.player) if p != TERMINAL]


def compile_game(game: Game) -> Tree:
    """Walk the whole game once and return its compiled tree.

    Raises ValueError if the game is not zero-sum, if chance probabilities do
    not sum to 1, or if two nodes that share an infoset key disagree on the
    acting player or the legal actions.
    """
    tree = Tree(game=game)

    def visit(state) -> int:
        node = tree.num_nodes
        kind = state.current_player()
        tree.player.append(kind)
        tree.children.append(())
        tree.labels.append(())
        tree.chance_probs.append(())
        tree.infoset.append(-1)
        tree.utility.append(0.0)

        if kind == TERMINAL:
            r0, r1 = state.returns()
            if abs(r0 + r1) > _ZERO_SUM_TOLERANCE:
                raise ValueError(f"{game.name}: terminal returns {r0}, {r1} are not zero-sum")
            tree.utility[node] = float(r0)
            return node

        if kind == CHANCE:
            outcomes = list(state.chance_outcomes())
            total = math.fsum(p for _, p in outcomes)
            if abs(total - 1.0) > 1e-12 or any(p <= 0 for _, p in outcomes):
                raise ValueError(f"{game.name}: bad chance distribution {outcomes}")
            tree.labels[node] = tuple(o for o, _ in outcomes)
            tree.chance_probs[node] = tuple(float(p) for _, p in outcomes)
            tree.children[node] = tuple(visit(state.child(o)) for o, _ in outcomes)
            return node

        key = state.information_state()
        actions = tuple(state.legal_actions())
        infoset = tree._infoset_ids.get(key)
        if infoset is None:
            infoset = tree.num_infosets
            tree._infoset_ids[key] = infoset
            tree.infoset_key.append(key)
            tree.infoset_player.append(kind)
            tree.infoset_actions.append(actions)
            tree.infoset_nodes.append([])
        elif tree.infoset_player[infoset] != kind or tree.infoset_actions[infoset] != actions:
            raise ValueError(f"{game.name}: infoset {key!r} is inconsistent across nodes")
        tree.infoset[node] = infoset
        tree.infoset_nodes[infoset].append(node)
        tree.labels[node] = actions
        tree.children[node] = tuple(visit(state.child(a)) for a in actions)
        return node

    visit(game.initial_state())
    return tree


def uniform_policy(tree: Tree) -> Policy:
    return [[1.0 / len(actions)] * len(actions) for actions in tree.infoset_actions]


def policy_to_dict(tree: Tree, policy: Policy) -> dict[str, dict[str, float]]:
    """Policy keyed by infoset key and action name, for printing and saving."""
    name = tree.game.action_name
    return {
        key: {name(a): p for a, p in zip(actions, probs, strict=True)}
        for key, actions, probs in zip(tree.infoset_key, tree.infoset_actions, policy, strict=True)
    }


def policy_from_dict(tree: Tree, table: dict[str, dict[str, float]]) -> Policy:
    """Inverse of `policy_to_dict`. Every infoset must be present."""
    name = tree.game.action_name
    return [
        [float(table[key][name(a)]) for a in actions]
        for key, actions in zip(tree.infoset_key, tree.infoset_actions, strict=True)
    ]
