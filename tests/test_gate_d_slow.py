"""Gate D, push/fold: the slow bullets (SCOPE, DECISIONS 20 and 22). Run with `py gate.py --full`.

The HoldemResources comparison needs data/external/ (DECISIONS 20). A missing
file fails the run; it never skips.
"""

import csv
import io
from pathlib import Path

import numpy as np
import pytest
from external_data import require

from showdown import pushfold as pf
from showdown.cfr import compile_game, exploitability
from showdown.equity.cards import CLASS_NAMES
from showdown.equity.matrix import PreflopMatrix
from showdown.games.pushfold import PushFoldGame

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]
SOLUTION = ROOT / "data" / "pushfold.json"


def load_holdemresources(seat: str) -> tuple[np.ndarray, np.ndarray]:
    """(stacks, probabilities[row, class index]) from the push or call CSV."""
    text = require(f"hrc/raw/holdemresources_hu_{seat}.csv").read_text()
    rows = [r for r in csv.reader(io.StringIO(text)) if r]
    names = [h.strip() for h in rows[0][1:]]
    data = np.array([[float(x) for x in r] for r in rows[1:]])
    order = [names.index(n) for n in CLASS_NAMES]
    return data[:, 0], data[:, 1:][:, order]


def gate_d_table(solution: pf.PushFoldSolution) -> list[tuple[str, float, pf.Comparison]]:
    rows = []
    for seat, attr in (("push", "push"), ("call", "call")):
        stacks, probs = load_holdemresources(seat)
        for depth in pf.DEPTHS:
            match = np.flatnonzero(np.isclose(stacks, depth))
            assert len(match) == 1, (seat, depth)
            ours = getattr(solution.at(depth), attr)
            rows.append((seat, float(depth), pf.compare(ours, probs[match[0]])))
    return rows


def test_gate_d_matches_holdemresources() -> None:
    solution = pf.PushFoldSolution.load(SOLUTION)
    rows = gate_d_table(solution)
    print("\nseat  stack  agree/compared  excluded  share   disagree")
    for seat, depth, c in rows:
        flag = "  FINDING: >10% excluded" if c.excluded > 0.10 * 169 else ""
        print(
            f"{seat:<4}  {depth:>5g}  {c.agree:>7}/{c.compared:<7} {c.excluded:>8}  "
            f"{c.share:6.1%}  {' '.join(c.disagree)}{flag}"
        )
    assert len(rows) == 40
    failed = [(seat, depth, c.share) for seat, depth, c in rows if not c.passed]
    assert not failed, failed


def test_exploitability_at_every_depth() -> None:
    solution = pf.PushFoldSolution.load(SOLUTION)
    matrix = PreflopMatrix.load(ROOT / solution.matrix_path)
    for d in solution.depths:
        tree = compile_game(PushFoldGame(d.stack, matrix))
        measured = exploitability(tree, pf.policy_from_vectors(tree, d.push, d.call))
        assert measured == pytest.approx(d.exploitability, abs=1e-12), d.stack
        assert measured <= 0.001, d.stack


def test_ten_bb_re_solves_to_the_committed_policy() -> None:
    solution = pf.PushFoldSolution.load(SOLUTION)
    fresh = pf.solve_depth(10.0, solution.iterations, ROOT / solution.matrix_path)
    stored = solution.at(10.0)
    assert np.array_equal(fresh.push, stored.push)
    assert np.array_equal(fresh.call, stored.call)
    assert fresh.exploitability == stored.exploitability
