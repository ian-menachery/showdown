"""compile_game rejects games the solvers cannot handle."""

from dataclasses import dataclass

import pytest

from showdown.cfr import compile_game
from showdown.games.base import CHANCE, TERMINAL


@dataclass(frozen=True)
class _Toy:
    """One chance flip, then player 0 picks 0 or 1. Knobs break one property each."""

    depth: int = 0
    flip: int = -1
    payoff_sum: float = 0.0
    probs: tuple[float, float] = (0.5, 0.5)
    leak_flip: bool = False
    vary_actions: bool = False

    def current_player(self) -> int:
        return (CHANCE, 0, TERMINAL)[self.depth]

    def legal_actions(self):
        return (0, 1, 2) if (self.vary_actions and self.flip == 1) else (0, 1)

    def chance_outcomes(self):
        return list(enumerate(self.probs))

    def child(self, action: int):
        flip = action if self.depth == 0 else self.flip
        return _Toy(
            self.depth + 1,
            flip,
            self.payoff_sum,
            self.probs,
            self.leak_flip,
            self.vary_actions,
        )

    def returns(self):
        return (1.0, self.payoff_sum - 1.0)

    def information_state(self) -> str:
        return f"flip{self.flip}" if self.leak_flip else "blind"


@dataclass
class _ToyGame:
    root: _Toy
    name: str = "toy"

    def initial_state(self):
        return self.root

    def action_name(self, action: int) -> str:
        return str(action)


def test_toy_compiles() -> None:
    tree = compile_game(_ToyGame(_Toy(leak_flip=True)))
    assert tree.num_infosets == 2
    assert tree.num_nodes == 1 + 2 + 4
    assert all(child > node for node, kids in enumerate(tree.children) for child in kids)


def test_rejects_non_zero_sum() -> None:
    with pytest.raises(ValueError, match="not zero-sum"):
        compile_game(_ToyGame(_Toy(payoff_sum=0.5)))


def test_rejects_bad_chance() -> None:
    with pytest.raises(ValueError, match="bad chance"):
        compile_game(_ToyGame(_Toy(probs=(0.5, 0.4))))


def test_rejects_inconsistent_infoset() -> None:
    with pytest.raises(ValueError, match="inconsistent"):
        compile_game(_ToyGame(_Toy(vary_actions=True)))
