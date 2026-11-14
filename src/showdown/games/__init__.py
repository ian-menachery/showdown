"""Games the solvers run on. Each matches the `Game` protocol in `base`."""

from showdown.games.base import CHANCE, TERMINAL, Game, State
from showdown.games.kuhn import KuhnPoker

GAMES: dict[str, type] = {"kuhn": KuhnPoker}


def load_game(name: str) -> Game:
    try:
        return GAMES[name]()
    except KeyError:
        raise ValueError(f"unknown game {name!r}; known: {', '.join(sorted(GAMES))}") from None


__all__ = ["CHANCE", "GAMES", "TERMINAL", "Game", "State", "load_game"]
