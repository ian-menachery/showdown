"""The push/fold game, its solve, charts and Gate D's comparison rule (DECISIONS 8, 22)."""

from pathlib import Path

import numpy as np
import pytest

from showdown import pushfold as pf
from showdown.cfr import compile_game, exploitability, policy_value
from showdown.cli import main
from showdown.equity.cards import class_index
from showdown.equity.matrix import PreflopMatrix
from showdown.games.base import CHANCE, TERMINAL
from showdown.games.pushfold import PushFoldGame

MATRIX = Path(__file__).resolve().parents[1] / "data" / "preflop_169_exact.npz"


@pytest.fixture(scope="module")
def matrix() -> PreflopMatrix:
    return PreflopMatrix.load(MATRIX)


@pytest.fixture(scope="module")
def tree5(matrix):
    return compile_game(PushFoldGame(5.0, matrix))


def test_tree_shape(tree5) -> None:
    # Root chance, then per class pair: SB node, SB-fold leaf, BB node, two BB leaves.
    assert tree5.num_nodes == 1 + 169 * 169 * 5
    assert tree5.num_infosets == 338
    seats = [key.split(":")[0] for key in tree5.infoset_key]
    assert seats.count("SB") == seats.count("BB") == 169
    assert tree5.player[0] == CHANCE


def test_chance_probabilities_are_the_pair_counts(tree5, matrix) -> None:
    assert tree5.labels[0] == tuple(range(169 * 169))
    probs = np.array(tree5.chance_probs[0]).reshape(169, 169)
    assert np.array_equal(probs, matrix.pair_counts / 1_624_350)


def test_terminal_payoffs(matrix) -> None:
    game = PushFoldGame(5.0, matrix)
    i, j = class_index("AA"), class_index("KK")
    deal = game.initial_state().child(169 * i + j)
    assert deal.current_player() == 0
    assert deal.information_state() == "SB:AA"
    assert deal.child(0).returns() == (-0.5, 0.5)
    jam = deal.child(1)
    assert jam.current_player() == 1
    assert jam.information_state() == "BB:KK"
    assert jam.child(0).returns() == (1.0, -1.0)
    called = jam.child(1)
    assert called.current_player() == TERMINAL
    showdown = 5.0 * (2 * matrix.equity[i, j] - 1)
    assert called.returns() == (showdown, -showdown)
    assert game.action_name(0) == "fold"
    assert game.action_name(1) == "all-in"
    with pytest.raises(ValueError, match="at least"):
        PushFoldGame(0.5, matrix)


def test_tree_and_closed_forms_agree(tree5, matrix) -> None:
    rng = np.random.default_rng(2)
    cases = [(rng.random(169), rng.random(169)) for _ in range(2)]
    cases.append((rng.integers(0, 2, 169).astype(float), rng.integers(0, 2, 169).astype(float)))
    for push, call in cases:
        policy = pf.policy_from_vectors(tree5, push, call)
        back = pf.strategy_vectors(tree5, policy)
        assert np.array_equal(back[0], push)
        assert np.array_equal(back[1], call)
        assert policy_value(tree5, policy) == pytest.approx(
            pf.sb_value(push, call, 5.0, matrix), abs=1e-12
        )
        assert exploitability(tree5, policy) == pytest.approx(
            pf.closed_form_exploitability(push, call, 5.0, matrix), abs=1e-12
        )


def test_one_bb_equilibrium_is_jam_and_call_everything(matrix) -> None:
    # At 1 bb the BB's whole stack is its blind, so calling costs nothing more and
    # dominates folding. Every class has more than 25% equity against a random hand,
    # so jamming (2E - 1) beats folding (-0.5) for the SB.
    ones = np.ones(169)
    assert pf.closed_form_exploitability(ones, ones, 1.0, matrix) == pytest.approx(0, abs=1e-12)


def test_short_solve(matrix) -> None:
    result = pf.solve_depth(10.0, iterations=10, matrix_path=MATRIX)
    assert result.exploitability < 0.05  # the benchmark measured 1.1e-2 after 10
    assert ((result.push >= 0) & (result.push <= 1)).all()
    assert result.value_sb == pytest.approx(
        pf.sb_value(result.push, result.call, 10.0, matrix), abs=1e-12
    )
    assert 0 < result.push_share() < 1
    assert 0 < result.call_share() < 1


def test_solve_all_does_not_depend_on_workers() -> None:
    one = pf.solve_all((1.0, 3.0), iterations=2, matrix_path=MATRIX, workers=1)
    two = pf.solve_all((1.0, 3.0), iterations=2, matrix_path=MATRIX, workers=2)
    for a, b in zip(one.depths, two.depths, strict=True):
        assert np.array_equal(a.push, b.push)
        assert np.array_equal(a.call, b.call)
        assert a.exploitability == b.exploitability


def test_classify_boundaries() -> None:
    probs = np.array([0.0, 0.01, 0.0100001, 0.5, 0.98999, 0.99, 1.0])
    assert pf.classify(probs).tolist() == [0, 0, -1, -1, -1, 1, 1]


def test_compare_counts_agreements_exclusions_and_disagreements() -> None:
    ours, ref = np.zeros(169), np.zeros(169)
    ours[class_index("AA")], ref[class_index("AA")] = 1.0, 0.995  # both play
    ours[class_index("KK")] = 0.5  # ours mixes: excluded
    ref[class_index("QQ")] = 0.3  # reference mixes: excluded
    ours[class_index("72o")] = 1.0  # pure on both sides and different
    c = pf.compare(ours, ref)
    assert (c.agree, c.compared, c.excluded) == (166, 167, 2)
    assert c.disagree == ["72o"]
    assert c.passed

    assert not pf.compare(np.ones(169), np.zeros(169)).passed
    nothing = pf.compare(np.full(169, 0.5), np.zeros(169))
    assert nothing.compared == 0
    assert not nothing.passed


def test_chart_puts_suited_above_the_diagonal() -> None:
    probs = np.zeros(169)
    probs[class_index("AKs")] = 1.0
    probs[class_index("AKo")] = 0.37
    lines = pf.chart(probs).splitlines()
    assert lines[0].split() == list("AKQJT98765432")
    row_a, row_k = lines[1].split(), lines[2].split()
    assert row_a[:3] == ["A", ".", "100"]  # AA never, AKs always
    assert row_k[:2] == ["K", "37"]  # AKo, below the diagonal


def _fake_solution() -> pf.PushFoldSolution:
    rng = np.random.default_rng(4)
    depths = [
        pf.DepthResult(s, rng.random(169), rng.random(169), 1e-5 * s, -0.01 * s) for s in (1.0, 2.0)
    ]
    return pf.PushFoldSolution(1000, "data/preflop_169_exact.npz", "0" * 64, depths)


def test_solution_round_trip_and_chart_command(tmp_path, capsys) -> None:
    solution = _fake_solution()
    path = tmp_path / "pushfold.json"
    solution.save(path)
    loaded = pf.PushFoldSolution.load(path)
    assert loaded.iterations == 1000
    assert np.array_equal(loaded.at(2).push, solution.at(2).push)
    assert np.array_equal(loaded.at(1).call, solution.at(1).call)
    with pytest.raises(KeyError):
        loaded.at(3)
    assert main(["pushfold", "chart", "2", "--file", str(path)]) == 0
    out = capsys.readouterr().out
    assert "2 bb effective" in out
    assert "SB jams" in out
    assert "BB calls a jam" in out


def test_build_command(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.setattr(pf, "solve_all", lambda *args, **kwargs: _fake_solution())
    out_file = tmp_path / "pf.json"
    assert main(["pushfold", "build", "--out", str(out_file)]) == 0
    assert out_file.exists()
    assert "wrote" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["pushfold", "build", "--iterations", "0"])
