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
