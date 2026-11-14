"""Phase 0 dependency spike, 2026-11-14. Evidence for DECISIONS 5, 6 and 10.

Run from the repo root once the dev extras are installed:

    .venv\\Scripts\\python spikes\\2026-11-14-deps.py

Not part of the package and not linted by the gate. It is kept as the record of
what the dependency choices were checked against.

Output on Ian's Windows laptop (Python 3.12.10, pokerkit 0.7.7, eval7 0.1.11,
open_spiel 2.0.2, phevaluator 0.6.0):

    kuhn_poker: uniform expl=0.4583  CFR+ 200 it expl=0.00029  (0.3s)
    leduc_poker: uniform expl=2.3736  CFR+ 200 it expl=0.00496  (101.0s)
    exact AsAh vs KdKc, eval7:       win=0.81065 tie=0.00382 equity=0.81255 (4.9s)
    exact AsAh vs KdKc, phevaluator: win=0.81065 tie=0.00382 equity=0.81255 (26.3s)
    eval7 MC AsAh vs KK, 400k, four separate runs: 0.8264 0.8569 0.8319 0.8083
    eval7 MC AsAh vs KK, 200k: 0.7847
    pokerkit MC AsAh vs KK, 20k: 0.8185 (26.4s)

Reading: the two evaluators agree exactly, so eval7.evaluate is sound. eval7's
Monte Carlo spreads over ~0.07 when its sampling error is ~0.0006, so it is
broken, not noisy. OpenSpiel's Windows wheel loads and solves both games.
"""

import itertools
import time

import eval7
import pyspiel
from open_spiel.python import policy as osp
from open_spiel.python.algorithms import cfr, exploitability
from phevaluator import evaluate_cards
from pokerkit import Deck, StandardHighHand, calculate_equities, parse_range


def openspiel_reference() -> None:
    for name in ("kuhn_poker", "leduc_poker"):
        game = pyspiel.load_game(name)
        start = time.perf_counter()
        uniform = exploitability.exploitability(game, osp.UniformRandomPolicy(game))
        solver = cfr.CFRPlusSolver(game)
        for _ in range(200):
            solver.evaluate_and_update_policy()
        expl = exploitability.exploitability(game, solver.average_policy())
        took = time.perf_counter() - start
        print(f"{name}: uniform expl={uniform:.4f}  CFR+ 200 it expl={expl:.5f}  ({took:.1f}s)")


def exact_equity(hero: list[str], villain: list[str], better) -> tuple[float, float]:
    """Exhaustive enumeration over every 5-card board. `better(a, b)` is +1/0/-1."""
    deck = [r + s for r in "23456789TJQKA" for s in "shdc" if r + s not in hero + villain]
    win = tie = n = 0
    for board in itertools.combinations(deck, 5):
        n += 1
        result = better(hero, villain, list(board))
        win += result > 0
        tie += result == 0
    return win / n, tie / n


def eval7_better(h: list[str], v: list[str], b: list[str]) -> int:
    a = eval7.evaluate([eval7.Card(c) for c in h + b])
    k = eval7.evaluate([eval7.Card(c) for c in v + b])
    return (a > k) - (a < k)  # eval7: higher is better


def phe_better(h: list[str], v: list[str], b: list[str]) -> int:
    a, k = evaluate_cards(*h, *b), evaluate_cards(*v, *b)
    return (a < k) - (a > k)  # phevaluator: lower is better


def main() -> None:
    openspiel_reference()

    for label, fn in (("eval7", eval7_better), ("phevaluator", phe_better)):
        start = time.perf_counter()
        win, tie = exact_equity(["As", "Ah"], ["Kd", "Kc"], fn)
        took = time.perf_counter() - start
        print(
            f"exact AsAh vs KdKc, {label}: win={win:.5f} tie={tie:.5f} "
            f"equity={win + tie / 2:.5f} ({took:.1f}s)"
        )

    aces = [eval7.Card("As"), eval7.Card("Ah")]
    runs = [
        eval7.py_hand_vs_range_monte_carlo(aces, eval7.HandRange("KK"), [], 400_000)
        for _ in range(4)
    ]
    print("eval7 MC AsAh vs KK, 400k, four runs:", " ".join(f"{r:.4f}" for r in runs))

    start = time.perf_counter()
    eq = calculate_equities(
        (parse_range("AsAh"), parse_range("KK")),
        (),
        2,
        5,
        Deck.STANDARD,
        (StandardHighHand,),
        sample_count=20_000,
    )
    print(f"pokerkit MC AsAh vs KK, 20k: {eq[0]:.4f} ({time.perf_counter() - start:.1f}s)")


if __name__ == "__main__":
    main()
