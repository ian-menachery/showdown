"""Gate D, push/fold: the fast bullets on the committed solution (SCOPE, DECISIONS 22).

The HoldemResources comparison and exploitability at all 20 depths are in
test_gate_d_slow.py.
"""

import hashlib
from pathlib import Path

import numpy as np
import pytest

from showdown import pushfold as pf
from showdown.cfr import compile_game, exploitability, policy_value
from showdown.equity.matrix import PreflopMatrix
from showdown.games.pushfold import PushFoldGame

ROOT = Path(__file__).resolve().parents[1]
SOLUTION = ROOT / "data" / "pushfold.json"


@pytest.fixture(scope="module")
def solution() -> pf.PushFoldSolution:
    return pf.PushFoldSolution.load(SOLUTION)


def test_solution_is_the_pre_registered_solve(solution) -> None:
    assert solution.iterations == 1000
    assert [d.stack for d in solution.depths] == [float(s) for s in range(1, 21)]
    assert solution.matrix_path == "data/preflop_169_exact.npz"
    digest = hashlib.sha256((ROOT / solution.matrix_path).read_bytes()).hexdigest()
    assert solution.matrix_sha256 == digest


def test_sb_jams_every_class_at_one_bb(solution) -> None:
    assert (solution.at(1).push >= pf.PURE).all()


def test_stored_exploitability_is_at_most_a_thousandth_of_a_bb(solution) -> None:
    worst = max(d.exploitability for d in solution.depths)
    assert worst <= 0.001, worst


@pytest.mark.parametrize("stack", [1.0, 10.0, 20.0])
def test_stored_numbers_match_a_fresh_best_response(solution, stack) -> None:
    matrix = PreflopMatrix.load(ROOT / solution.matrix_path)
    tree = compile_game(PushFoldGame(stack, matrix))
    d = solution.at(stack)
    policy = pf.policy_from_vectors(tree, d.push, d.call)
    assert exploitability(tree, policy) == pytest.approx(d.exploitability, abs=1e-12)
    assert policy_value(tree, policy) == pytest.approx(d.value_sb, abs=1e-12)
    assert pf.closed_form_exploitability(d.push, d.call, stack, matrix) == pytest.approx(
        d.exploitability, abs=1e-12
    )
    assert np.isfinite(d.push).all()
