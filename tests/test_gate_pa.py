"""Gate PA, push/fold with a 10% ante: the fast bars (DECISIONS 48).

Bar 3 (HoldemResources' "Ante 10%" chart) and the 10 bb re-solves are in
test_gate_pa_slow.py. Bar 2's full 20-depth ante-0 re-solve is recorded in GATES.md.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from showdown import pushfold as pf
from showdown.cfr import compile_game, exploitability, policy_value
from showdown.cli import main
from showdown.equity.cards import class_index
from showdown.equity.matrix import PreflopMatrix
from showdown.games.pushfold import BB_FOLD, SB_FOLD, PushFoldGame, fold_payoffs

ROOT = Path(__file__).resolve().parents[1]
ANTE_SOLUTION = ROOT / "data" / "pushfold_ante10.json"


@pytest.fixture(scope="module")
def matrix() -> PreflopMatrix:
    return PreflopMatrix.load(ROOT / pf.DEFAULT_MATRIX)


def test_fold_payoffs() -> None:
    for stack in range(1, 21):
        assert fold_payoffs(stack) == (SB_FOLD, BB_FOLD)  # no ante: exactly as before
    assert fold_payoffs(10, 0.1) == pytest.approx((-0.6, 1.1), abs=1e-15)
    assert fold_payoffs(1, 0.1) == pytest.approx((-0.6, 1.0), abs=1e-15)  # capped at S


def test_terminal_payoffs_with_the_ante(matrix) -> None:
    deal = PushFoldGame(5.0, matrix, 0.1).initial_state().child(169 * class_index("AA"))
    assert deal.child(0).returns() == pytest.approx((-0.6, 0.6))
    assert deal.child(1).child(0).returns() == pytest.approx((1.1, -1.1))
    short = PushFoldGame(1.0, matrix, 0.1).initial_state().child(0).child(1).child(0)
    assert short.returns() == (1.0, -1.0)


@pytest.mark.parametrize("stack", [1.0, 6.0])
def test_bar4_tree_and_closed_forms_agree_with_the_ante(matrix, stack) -> None:
    tree = compile_game(PushFoldGame(stack, matrix, 0.1))
    rng = np.random.default_rng(48)
    cases = [(rng.random(169), rng.random(169)) for _ in range(2)]
    cases.append((rng.integers(0, 2, 169).astype(float), rng.integers(0, 2, 169).astype(float)))
    for push, call in cases:
        policy = pf.policy_from_vectors(tree, push, call)
        assert policy_value(tree, policy) == pytest.approx(
            pf.sb_value(push, call, stack, matrix, 0.1), abs=1e-12
        )
        assert exploitability(tree, policy) == pytest.approx(
            pf.closed_form_exploitability(push, call, stack, matrix, 0.1), abs=1e-12
        )
    sb_fold, _ = pf.sb_action_values(cases[0][1], 10, matrix, ante=0.1)
    bb_fold, _ = pf.bb_action_values(cases[0][0], 10, matrix, ante=0.1)
    assert np.allclose(sb_fold, -0.6) and np.allclose(bb_fold, -1.1)


def test_ante_round_trips_and_stays_out_of_no_ante_files(tmp_path) -> None:
    rng = np.random.default_rng(5)
    depth = pf.DepthResult(2.0, rng.random(169), rng.random(169), 1e-6, 0.01)
    with_ante = pf.PushFoldSolution(1000, pf.DEFAULT_MATRIX, "0" * 64, [depth], 0.1)
    with_ante.save(tmp_path / "a.json")
    assert pf.PushFoldSolution.load(tmp_path / "a.json").ante == 0.1
    pf.PushFoldSolution(1000, pf.DEFAULT_MATRIX, "0" * 64, [depth]).save(tmp_path / "b.json")
    assert "ante" not in json.loads((tmp_path / "b.json").read_text(encoding="utf-8"))
    assert pf.PushFoldSolution.load(ROOT / pf.DEFAULT_SOLUTION).ante == 0.0


def test_build_command_passes_the_ante(tmp_path, capsys, monkeypatch) -> None:
    seen = {}

    def fake(*args, **kwargs):
        seen.update(kwargs)
        return pf.PushFoldSolution(1, pf.DEFAULT_MATRIX, "0" * 64, [], kwargs["ante"])

    monkeypatch.setattr(pf, "solve_all", fake)
    assert main(["pushfold", "build", "--ante", "0.1", "--out", str(tmp_path / "x.json")]) == 0
    assert seen["ante"] == 0.1 and "ante 0.1" in capsys.readouterr().out


def test_bars_1_and_5_the_stored_ante_solution(matrix) -> None:
    solution = pf.PushFoldSolution.load(ANTE_SOLUTION)
    assert (solution.ante, solution.iterations) == (0.1, 1000)
    assert [d.stack for d in solution.depths] == [float(s) for s in pf.DEPTHS]
    assert solution.matrix_path == pf.DEFAULT_MATRIX
    worst = max(d.exploitability for d in solution.depths)
    assert worst <= 1e-5, worst
    for stack in (1.0, 10.0, 20.0):  # the stored numbers are the tree's own
        d = solution.at(stack)
        tree = compile_game(PushFoldGame(stack, matrix, 0.1))
        policy = pf.policy_from_vectors(tree, d.push, d.call)
        assert exploitability(tree, policy) == pytest.approx(d.exploitability, abs=1e-12)
        assert policy_value(tree, policy) == pytest.approx(d.value_sb, abs=1e-12)
