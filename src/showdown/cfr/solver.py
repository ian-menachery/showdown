"""Counterfactual regret minimization on a compiled tree.

One class covers vanilla CFR and CFR+. Its three flags have exactly the meaning
of OpenSpiel's `_CFRSolverBase`, and the update order is the same, so for the
same game the two produce the same average policy at every iteration, up to
float rounding (DECISIONS 15):

- alternating_updates: one pass per player per iteration. After each pass the
  regrets are (optionally) clipped and every infoset's current policy is
  recomputed.
- linear_averaging: the average-policy sum is weighted by the iteration number.
- regret_matching_plus: negative cumulative regrets are reset to 0 after each
  pass.

Regrets are weighted by counterfactual reach (the opponent's reach times
chance). Average-policy sums are weighted by the acting player's own reach.
A node where both players' reach is 0 is skipped; its value can only ever be
multiplied by zero.
"""

from __future__ import annotations

from showdown.cfr.tree import Policy, Tree, uniform_policy
from showdown.games.base import CHANCE, TERMINAL


class CFRSolver:
    def __init__(
        self,
        tree: Tree,
        *,
        alternating_updates: bool = True,
        linear_averaging: bool = False,
        regret_matching_plus: bool = False,
    ) -> None:
        self.tree = tree
        self.alternating_updates = alternating_updates
        self.linear_averaging = linear_averaging
        self.regret_matching_plus = regret_matching_plus
        self.iteration = 0
        self._regret = [[0.0] * len(a) for a in tree.infoset_actions]
        self._policy_sum = [[0.0] * len(a) for a in tree.infoset_actions]
        self._current = uniform_policy(tree)
        self._internal = tree.internal_nodes()
        self._reversed_internal = self._internal[::-1]
        self._terminals = [n for n, p in enumerate(tree.player) if p == TERMINAL]

    def iterate(self, iterations: int = 1) -> None:
        for _ in range(iterations):
            self.iteration += 1
            if self.alternating_updates:
                for player in (0, 1):
                    self._pass(player)
                    self._after_pass()
            else:
                self._pass(None)
                self._after_pass()

    def current_policy(self) -> Policy:
        return [list(p) for p in self._current]

    def average_policy(self) -> Policy:
        average = []
        for sums in self._policy_sum:
            total = sum(sums)
            if total == 0:
                average.append([1.0 / len(sums)] * len(sums))
            else:
                average.append([s / total for s in sums])
        return average

    def _after_pass(self) -> None:
        if self.regret_matching_plus:
            for regrets in self._regret:
                for k, r in enumerate(regrets):
                    if r < 0:
                        regrets[k] = 0
        for infoset, regrets in enumerate(self._regret):
            positive = sum(r for r in regrets if r > 0)
            if positive > 0:
                self._current[infoset] = [max(0.0, r) / positive for r in regrets]
            else:
                self._current[infoset] = [1.0 / len(regrets)] * len(regrets)

    def _pass(self, updating: int | None) -> None:
        """One traversal. `updating` is the player whose regrets change, or None for both."""
        t = self.tree
        player, children, probs, infoset = t.player, t.children, t.chance_probs, t.infoset
        current = self._current
        n = t.num_nodes

        reach0 = [0.0] * n
        reach1 = [0.0] * n
        reach_c = [0.0] * n
        reach0[0] = reach1[0] = reach_c[0] = 1.0
        for node in self._internal:
            p0, p1, pc = reach0[node], reach1[node], reach_c[node]
            kind = player[node]
            if kind == CHANCE:
                for child, prob in zip(children[node], probs[node], strict=True):
                    reach0[child] = p0
                    reach1[child] = p1
                    reach_c[child] = pc * prob
            elif kind == 0:
                for child, sigma in zip(children[node], current[infoset[node]], strict=True):
                    reach0[child] = p0 * sigma
                    reach1[child] = p1
                    reach_c[child] = pc
            else:
                for child, sigma in zip(children[node], current[infoset[node]], strict=True):
                    reach0[child] = p0
                    reach1[child] = p1 * sigma
                    reach_c[child] = pc

        value = [0.0] * n  # payoff to player 0
        utility = t.utility
        for node in self._terminals:
            value[node] = utility[node]

        weight = self.iteration if self.linear_averaging else None
        regret_table, sum_table = self._regret, self._policy_sum
        for node in self._reversed_internal:
            kind = player[node]
            if kind == CHANCE:
                v = 0.0
                for child, prob in zip(children[node], probs[node], strict=True):
                    v += prob * value[child]
                value[node] = v
                continue
            p0, p1 = reach0[node], reach1[node]
            if p0 == 0 and p1 == 0:
                continue  # value stays 0.0; see module docstring
            info = infoset[node]
            sigma = current[info]
            kids = children[node]
            v = 0.0
            for child, s in zip(kids, sigma, strict=True):
                v += s * value[child]
            value[node] = v
            if updating is not None and kind != updating:
                continue
            if kind == 0:
                own, cf, sign = p0, p1 * reach_c[node], 1.0
            else:
                own, cf, sign = p1, p0 * reach_c[node], -1.0
            node_value = sign * v
            regrets = regret_table[info]
            sums = sum_table[info]
            for k, (child, s) in enumerate(zip(kids, sigma, strict=True)):
                regrets[k] += cf * (sign * value[child] - node_value)
                if weight is None:
                    sums[k] += own * s
                else:
                    sums[k] += weight * own * s


def cfr(tree: Tree) -> CFRSolver:
    """Vanilla CFR with alternating updates, as OpenSpiel's `CFRSolver`."""
    return CFRSolver(tree)


def cfr_plus(tree: Tree) -> CFRSolver:
    """CFR+, as OpenSpiel's `CFRPlusSolver`."""
    return CFRSolver(tree, linear_averaging=True, regret_matching_plus=True)
