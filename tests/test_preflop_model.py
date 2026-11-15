"""The preflop model's game, lookup rule, storage and chart (DECISIONS 33, 34)."""

from pathlib import Path

import numpy as np
import pytest

from showdown import preflop_model as pm
from showdown.cfr import compile_game
from showdown.cli import main
from showdown.equity.cards import CLASS_NAMES, class_index
from showdown.equity.matrix import PreflopMatrix
from showdown.games.base import CHANCE
from showdown.games.preflop import ACTIONS, NODES, PreflopGame

MATRIX = Path(__file__).resolve().parents[1] / "data" / "preflop_169_exact.npz"


@pytest.fixture(scope="module")
def matrix() -> PreflopMatrix:
    return PreflopMatrix.load(MATRIX)


def test_tree_shape(matrix) -> None:
    tree = compile_game(PreflopGame(25, matrix, r_oop=0.9))
    assert tree.player[0] == CHANCE
    assert tree.num_nodes == 485_538  # S3's count
    assert tree.num_infosets == 1_014
    nodes = {key.split(":")[2] for key in tree.infoset_key}
    assert nodes == set(NODES)
    jam_only = compile_game(PreflopGame(20, matrix, raises=False))
    assert jam_only.num_nodes == 142_806  # the push/fold tree


def test_actions_and_bad_input(matrix) -> None:
    assert ACTIONS[()] == (0, 2, 3)
    state = PreflopGame(25, matrix).initial_state().child(0)
    assert state.legal_actions() == (0, 2, 3)
    assert state.child(2).legal_actions() == (0, 1, 2, 3)
    with pytest.raises(ValueError, match="3-bet"):
        PreflopGame(7, matrix)
    with pytest.raises(ValueError, match="r_oop"):
        PreflopGame(25, matrix, r_oop=1.2)


def test_lookup_rule() -> None:
    cases = {20: None, 20.01: 25, 27.5: 25, 27.6: 30, 35: 30, 45: 40, 95: 90, 100: 100, 250: 100}
    for stack, depth in cases.items():
        assert pm.PreflopModel.depth_for(stack) == depth, stack


def _fake_solution(stack: float, r: float, fold_aa: bool) -> pm.DepthSolution:
    actions = {
        node: [["fold", "call", "raise", "all-in"][a] for a in ACTIONS[h]]
        for node, h in (
            ("", ()),
            ("r", (2,)),
            ("rr", (2, 2)),
            ("rrj", (2, 2, 3)),
            ("rj", (2, 3)),
            ("j", (3,)),
        )
    }
    strategy = {}
    for node, acts in actions.items():
        rows = {}
        for name in CLASS_NAMES:
            probs = [0.0] * len(acts)
            probs[-1 if name != "AA" or not fold_aa else 0] = 1.0
            rows[name] = probs
        strategy[node] = rows
    return pm.DepthSolution(stack, r, True, 1e-4, 0.01, strategy, actions)


def _fake_model() -> pm.PreflopModel:
    sols = [_fake_solution(s, r, fold_aa=(r == 0.95)) for r in pm.R_VALUES for s in pm.GRID]
    return pm.PreflopModel(1000, "data/preflop_169_exact.npz", "0" * 64, sols, [])


def test_round_trip_flag_and_chart(tmp_path, capsys) -> None:
    model = _fake_model()
    path = tmp_path / "m.json"
    model.save(path)
    loaded = pm.PreflopModel.load(path)
    assert loaded.at(50).probs("", class_index("AA"))["all-in"] == 1.0
    assert loaded.depends_on_r(50, "", class_index("AA"))  # 0.95 folds it, 0.85 jams
    assert not loaded.depends_on_r(50, "", class_index("KK"))
    with pytest.raises(KeyError):
        loaded.at(55)
    assert main(["preflop", "chart", "50", "--file", str(path)]) == 0
    out = capsys.readouterr().out
    assert "model chart, R 0.90, 50 bb" in out
    assert "J*" in out
    with pytest.raises(SystemExit, match="push/fold"):
        main(["preflop", "chart", "15", "--file", str(path)])
    with pytest.raises(SystemExit, match="node"):
        main(["preflop", "chart", "50", "--node", "x", "--file", str(path)])


def test_short_solve_reads_every_node(matrix) -> None:
    s = pm.solve_depth(25, 0.9, iterations=2, matrix_path=MATRIX)
    assert set(s.strategy) == set(NODES)
    for node, rows in s.strategy.items():
        assert len(rows) == 169
        assert all(np.isclose(sum(p), 1.0) for p in rows.values()), node
    assert s.exploitability > 0
