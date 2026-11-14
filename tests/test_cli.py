"""The command line, driven in-process."""

import json

import pytest

from showdown.cli import _report_points, main


def test_solve_kuhn_prints_table_and_writes_json(tmp_path, capsys) -> None:
    out = tmp_path / "kuhn.json"
    assert main(["solve", "kuhn", "--iterations", "200", "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "kuhn: 58 nodes, 12 infosets, cfr+, 200 iterations" in text
    assert "K:pb" in text
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["iterations"] == 200
    assert payload["exploitability"] < 1e-3
    assert set(payload["policy"]["K:"]) == {"pass", "bet"}


def test_solve_vanilla_cfr_with_every(capsys) -> None:
    assert main(["solve", "kuhn", "--algo", "cfr", "--iterations", "20", "--every", "10"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert any(line.strip().startswith("10 ") for line in lines)
    assert any(line.strip().startswith("20 ") for line in lines)


def test_rejects_zero_iterations() -> None:
    with pytest.raises(SystemExit):
        main(["solve", "kuhn", "--iterations", "0"])


def test_report_points() -> None:
    assert _report_points(1000, None) == [1, 10, 100, 1000]
    assert _report_points(250, None) == [1, 10, 100, 250]
    assert _report_points(25, 10) == [10, 20, 25]


def test_solve_leduc_hides_large_policy(capsys) -> None:
    assert main(["solve", "leduc", "--iterations", "3"]) == 0
    text = capsys.readouterr().out
    assert "leduc: 9457 nodes, 936 infosets" in text
    assert "KsQs:" not in text  # 936 infosets are too many to print by default


def test_equity_exact_on_turn(capsys) -> None:
    assert main(["equity", "AsKs", "QhQd", "--board", "Ts9s2dJc"]) == 0
    out = capsys.readouterr().out
    assert "exact: equity 0.29545" in out  # 13 winning rivers of 44
    assert "44 outcomes" in out


def test_equity_monte_carlo_preflop_ranges(capsys) -> None:
    assert main(["equity", "TT+,AK", "22-99", "--samples", "2000", "--seed", "1"]) == 0
    assert "monte carlo: equity" in capsys.readouterr().out


def test_equity_forced_exact_hits_guard() -> None:
    with pytest.raises(SystemExit, match="use Monte Carlo"):
        main(["equity", "random", "random", "--method", "exact"])


def test_equity_auto_falls_back_to_monte_carlo(monkeypatch, capsys) -> None:
    monkeypatch.setattr("showdown.equity.exact.MAX_EXACT_EVALUATIONS", 10)
    assert main(["equity", "TT+", "22-55", "--board", "Ts9s2d", "--samples", "500"]) == 0
    out = capsys.readouterr().out
    assert "falling back to Monte Carlo" in out and "monte carlo: equity" in out


def test_matrix_build_and_show(tmp_path, capsys) -> None:
    out_file = tmp_path / "m.npz"
    args = ["matrix", "build", "--boards-per-batch", "2", "--batches", "2", "--workers", "1"]
    assert main([*args, "--out", str(out_file)]) == 0
    assert "wrote" in capsys.readouterr().out
    assert main(["matrix", "show", "AA", "KK", "--file", str(out_file)]) == 0
    assert "AA vs KK: equity" in capsys.readouterr().out
