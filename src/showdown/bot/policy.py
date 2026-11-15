"""The solved strategies the bots play, and push/fold decision grading (DECISIONS 24)."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from showdown import pushfold
from showdown.equity.matrix import PreflopMatrix

MISTAKE_BB = 0.001
"""A decision that loses more than this against Nash counts as a mistake."""


@dataclass(frozen=True)
class Grade:
    ev_fold: float
    ev_allin: float
    """EV in bb of the all-in action: a jam for the SB, a call for the BB."""
    chosen: str
    """"fold" or "all-in"."""
    loss: float
    """bb lost against the better action, given the opponent's Nash strategy."""
    nash_allin: float
    """The solution's probability of going all-in with this class at this depth."""

    @property
    def mistake(self) -> bool:
        return self.loss > MISTAKE_BB


class PushFoldStrategy:
    """The committed push/fold solution, with per-class action values for grading."""

    def __init__(self, solution: pushfold.PushFoldSolution, matrix: PreflopMatrix) -> None:
        self.solution = solution
        self.matrix = matrix
        self._values = lru_cache(maxsize=None)(self._compute_values)

    @classmethod
    def load(
        cls,
        solution_path: str | Path = pushfold.DEFAULT_SOLUTION,
        matrix_path: str | Path | None = None,
    ) -> PushFoldStrategy:
        solution = pushfold.PushFoldSolution.load(solution_path)
        return cls(solution, PreflopMatrix.load(matrix_path or solution.matrix_path))

    def push_prob(self, depth: int, cls: int) -> float:
        return float(self.solution.at(depth).push[cls])

    def call_prob(self, depth: int, cls: int) -> float:
        return float(self.solution.at(depth).call[cls])

    def _compute_values(self, depth: int) -> tuple[np.ndarray, ...]:
        result = self.solution.at(depth)
        sb_fold, sb_jam = pushfold.sb_action_values(result.call, depth, self.matrix)
        bb_fold, bb_call = pushfold.bb_action_values(result.push, depth, self.matrix)
        return sb_fold, sb_jam, bb_fold, bb_call

    def grade(self, depth: int, seat: str, cls: int, allin: bool) -> Grade:
        sb_fold, sb_jam, bb_fold, bb_call = self._values(depth)
        if seat == "sb":
            fold, go = float(sb_fold[cls]), float(sb_jam[cls])
            nash = self.push_prob(depth, cls)
        elif seat == "bb":
            fold, go = float(bb_fold[cls]), float(bb_call[cls])
            nash = self.call_prob(depth, cls)
        else:
            raise ValueError(f"unknown seat {seat!r}")
        chosen = go if allin else fold
        return Grade(fold, go, "all-in" if allin else "fold", max(fold, go) - chosen, nash)


def act(probability: float, rng: random.Random) -> bool:
    """Sample a binary mixed strategy: True with `probability`."""
    return rng.random() < probability


class LeducStrategy:
    """A Leduc policy keyed by infoset and action name, as `showdown solve --out` writes it."""

    def __init__(self, table: dict[str, dict[str, float]]) -> None:
        self.table = table

    @classmethod
    def load(cls, path: str | Path = "data/leduc_cfr_plus.json") -> LeducStrategy:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("game") != "leduc":
            raise ValueError(f"{path} is not a Leduc policy")
        return cls(data["policy"])

    def choose(self, key: str, actions: dict[int, str], rng: random.Random) -> int:
        """Sample an action at infoset `key`; `actions` maps action ids to names."""
        probs = self.table[key]
        r = rng.random()
        cumulative = 0.0
        for action, name in actions.items():
            cumulative += probs[name]
            if r < cumulative:
                return action
        return list(actions)[-1]  # rounding: the probabilities sum to 1 within 1e-12
