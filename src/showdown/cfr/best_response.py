"""Exact best response, policy value and exploitability on a compiled tree.

Exploitability follows OpenSpiel's convention: NashConv / 2, where NashConv is
the sum over both players of what a best response gains against the other's
policy (DECISIONS 7). In a zero-sum game the on-policy values cancel, so
NashConv = BR0 + BR1.

The best responder sees only its own information sets. At each one it picks the
action that maximises the sum, over the infoset's nodes, of (opponent and chance
reach) times (the action's value under best play further down). The values
further down depend on choices at deeper infosets, so both are memoised and
resolved on demand.
"""

from __future__ import annotations

import sys

from showdown.cfr.tree import Policy, Tree
from showdown.games.base import CHANCE, TERMINAL


def policy_value(tree: Tree, policy: Policy) -> float:
    """Expected payoff to player 0 when both players follow `policy`."""
    player, children, probs, infoset = tree.player, tree.children, tree.chance_probs, tree.infoset
    value = list(tree.utility)
    for node in reversed(range(tree.num_nodes)):
        kind = player[node]
        if kind == TERMINAL:
            continue
        weights = probs[node] if kind == CHANCE else policy[infoset[node]]
        v = 0.0
        for child, w in zip(children[node], weights, strict=True):
            v += w * value[child]
        value[node] = v
    return value[0]


def _reach_excluding(tree: Tree, policy: Policy, responder: int) -> list[float]:
    """Reach of each node through chance and the opponent of `responder` only."""
    player, children, probs, infoset = tree.player, tree.children, tree.chance_probs, tree.infoset
    reach = [0.0] * tree.num_nodes
    reach[0] = 1.0
    for node in range(tree.num_nodes):
        kind = player[node]
        if kind == TERMINAL:
            continue
        r = reach[node]
        if kind == responder:
            for child in children[node]:
                reach[child] = r
        else:
            weights = probs[node] if kind == CHANCE else policy[infoset[node]]
            for child, w in zip(children[node], weights, strict=True):
                reach[child] = r * w
    return reach


def best_response(tree: Tree, policy: Policy, responder: int) -> tuple[float, Policy]:
    """The responder's best-response value against `policy`, and a pure BR policy.

    The returned policy equals `policy` at the opponent's infosets and is pure
    (one action with probability 1) at the responder's.
    """
    player, children, probs, infoset = tree.player, tree.children, tree.chance_probs, tree.infoset
    sign = 1.0 if responder == 0 else -1.0
    reach = _reach_excluding(tree, policy, responder)
    value: list[float | None] = [None] * tree.num_nodes
    choice: dict[int, int] = {}

    def node_value(node: int) -> float:
        cached = value[node]
        if cached is not None:
            return cached
        kind = player[node]
        if kind == TERMINAL:
            v = sign * tree.utility[node]
        elif kind == responder:
            v = node_value(children[node][best_action(infoset[node])])
        else:
            weights = probs[node] if kind == CHANCE else policy[infoset[node]]
            v = 0.0
            for child, w in zip(children[node], weights, strict=True):
                v += w * node_value(child)
        value[node] = v
        return v

    def best_action(info: int) -> int:
        cached = choice.get(info)
        if cached is not None:
            return cached
        q = [0.0] * len(tree.infoset_actions[info])
        for node in tree.infoset_nodes[info]:
            w = reach[node]
            if w == 0:
                continue
            for k, child in enumerate(children[node]):
                q[k] += w * node_value(child)
        best = max(range(len(q)), key=q.__getitem__)
        choice[info] = best
        return best

    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, 10_000))
    try:
        root_value = node_value(0)
        br_policy = [list(p) for p in policy]
        for info, owner in enumerate(tree.infoset_player):
            if owner == responder:
                a = best_action(info)
                br_policy[info] = [1.0 if k == a else 0.0 for k in range(len(br_policy[info]))]
    finally:
        sys.setrecursionlimit(limit)
    return root_value, br_policy


def nash_conv(tree: Tree, policy: Policy) -> float:
    on_policy = policy_value(tree, policy)
    br0, _ = best_response(tree, policy, 0)
    br1, _ = best_response(tree, policy, 1)
    return (br0 - on_policy) + (br1 + on_policy)


def exploitability(tree: Tree, policy: Policy) -> float:
    """NashConv / 2, in the game's payoff units per hand (DECISIONS 7)."""
    return nash_conv(tree, policy) / 2
