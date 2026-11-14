"""Gate B, Leduc: the slow bullets (SCOPE). Run with `py gate.py --full`.

OpenSpiel's Python CFR+ needs about 100 s for 200 Leduc iterations, which is why
this module is marked slow. The fast bullet (exploitability matches on three
policies) is in test_cfr_leduc_oracle.py.
"""

import time

import pytest
from openspiel_oracle import load, os_cfr, os_exploitability

from showdown.cfr import cfr_plus, compile_game, exploitability
from showdown.games import load_game

ITERATIONS = 200
RATIO_BAR = 1.10

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def runs():
    tree = compile_game(load_game("leduc"))
    start = time.perf_counter()
    ours = cfr_plus(tree)
    ours.iterate(ITERATIONS)
    ours_seconds = time.perf_counter() - start
    ours_expl = exploitability(tree, ours.average_policy())

    os_game = load("leduc_poker")
    start = time.perf_counter()
    theirs = os_cfr.CFRPlusSolver(os_game)
    for _ in range(ITERATIONS):
        theirs.evaluate_and_update_policy()
    theirs_seconds = time.perf_counter() - start
    theirs_expl = os_exploitability.exploitability(os_game, theirs.average_policy())
    print(
        f"\nGate B: ours {ours_expl:.6e} in {ours_seconds:.2f} s; "
        f"OpenSpiel {theirs_expl:.6e} in {theirs_seconds:.2f} s"
    )
    return ours_expl, ours_seconds, theirs_expl, theirs_seconds


def test_exploitability_within_ratio_of_openspiel(runs) -> None:
    ours_expl, _, theirs_expl, _ = runs
    assert ours_expl <= RATIO_BAR * theirs_expl


def test_no_slower_than_openspiel(runs) -> None:
    _, ours_seconds, _, theirs_seconds = runs
    assert ours_seconds <= theirs_seconds


def test_same_semantics_same_answer(runs) -> None:
    """Not a gate bullet: identical semantics give a bit-identical number (DECISIONS 15)."""
    ours_expl, _, theirs_expl, _ = runs
    assert ours_expl == theirs_expl
