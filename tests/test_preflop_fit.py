"""The R fit (DECISIONS 49): its flops, its units, its fallbacks and interpolation, one round's
bookkeeping on fakes, and the 4x tree's game. Gate Q's bars are in test_gate_q.py and
test_gate_q_slow.py.

`test_a_check_down_realizes_all_its_equity` runs the flop bridge, built by `showdown postflop
build`, on a spot with no bets; it takes about a second.
"""

import json

import numpy as np
import pytest

from showdown import preflop_fit as fit
from showdown import preflop_model as pm
from showdown.equity.cards import CLASS_NAMES
from showdown.postflop import bridge
from showdown.postflop.spot import SETTINGS

FLOPS = [
    "Ks8c6d",
    "Kh9h6s",
    "AdJh8s",
    "8c4s3h",
    "Ad6c2c",
    "Kd6h3s",
    "Qc8s7s",
    "Th7h5s",
    "Kc8c4s",
    "8d5h2d",
    "Js5c4c",
    "QhTh8s",
    "7c4h2d",
    "AdQcJs",
    "Ah3s3d",
    "9s7c4c",
    "8s8c2c",
    "Th9s8s",
    "AhTc6d",
    "AhKc6h",
]
"""The 20 fit flops, drawn once with seed 20261119 and written here before any fit run."""


def test_the_flops_are_the_seeded_draw() -> None:
    assert fit.fit_flops() == FLOPS
    assert len(set(FLOPS)) == fit.FLOPS == 20


def test_a_check_down_realizes_all_its_equity() -> None:
    """With no bets the hand is checked down, so the BB's EV is pot × equity: R = 1."""
    no_bets = {k: "" for k in ("flop_bet", "flop_raise", "turn_bet", "turn_raise")}
    no_bets |= {"river_bet": "", "river_raise": "", "river_donk": ""}
    spec = {
        "oop_range": "AA,KK,QQ,AKs,76s",
        "ip_range": "JJ-99,AQo,KQs",
        "flop": "Kc7d2h",
        "starting_pot": 50,
        "effective_stack": 1000,
        **no_bets,
        **SETTINGS,
        "locks": [],
        "report": fit.ROOT_REPORT,
    }
    result = bridge.solve(spec, timeout=120)
    (root,) = result["reports"]
    assert root["reached"] and root["player"] == 0 and root["actions"] == ["Check"]
    got = fit.measure_r(result, 50)
    print(f"\ncheck-down: EV {got['ev_bb']:.4f} chips, E_BB {got['e_bb']:.6f}, R {got['r']:.6f}")
    assert 0.5 < got["e_bb"] < 1
    assert got["r"] == pytest.approx(1.0, abs=1e-4)


def test_measure_r_needs_the_root_report() -> None:
    result = {"root_ev": [30.0, 20.0], "reports": [{"path": [], "reached": True, "player": 0}]}
    result["reports"][0] |= {"weights": [1.0, 3.0], "equity": [0.2, 0.6]}
    got = fit.measure_r(result, 50)
    assert got["e_bb"] == pytest.approx(0.5) and got["r"] == pytest.approx(30 / 25)
    for broken in ({"reports": []}, {"reports": [{"path": [], "reached": False}]}):
        with pytest.raises(fit.FitError, match="ask Ian"):
            fit.measure_r({"root_ev": [1.0, 1.0], **broken}, 50)


def test_summary_fallbacks_and_interpolation() -> None:
    mean, se = fit.summarize([1.0, 2.0, 3.0, 4.0])
    assert mean == 2.5 and se == pytest.approx(np.std([1, 2, 3, 4], ddof=1) / 2)
    measured = {"measured": True}
    cells = {
        "open": {
            25: {**measured, "r": 0.8},
            50: {**measured, "r": 0.9},
            100: {**measured, "r": 1.0},
        },
        "3x": {25: {"measured": False}, 50: {"measured": False}, 100: {**measured, "r": 1.2}},
        "4x": {25: {"measured": False}, 50: {"measured": False}, 100: {"measured": False}},
    }
    fit.fill(cells)
    assert [cells["3x"][d]["r"] for d in fit.FIT_DEPTHS] == [1.2, 1.2, 1.2]
    assert cells["3x"][25]["source"] == "fallback: the 3x pot's R at 100 bb"
    assert [cells["4x"][d]["r"] for d in fit.FIT_DEPTHS] == [0.9, 0.9, 0.9]
    near = {
        "open": {25: {"measured": False}, 50: {**measured, "r": 0.7}, 100: {**measured, "r": 1.1}}
    }
    fit.fill(near)
    assert near["open"][25]["r"] == 0.7  # 50 bb is nearer than 100
    assert fit.grid_r(cells, 25) == {"open": 0.8, "3x": 1.2, "4x": 0.9}
    assert fit.grid_r(cells, 30)["open"] == pytest.approx(0.8 + 0.1 * 5 / 25)
    assert fit.grid_r(cells, 40)["open"] == pytest.approx(0.8 + 0.1 * 15 / 25)
    assert fit.grid_r(cells, 70)["open"] == pytest.approx(0.9 + 0.1 * 20 / 50)
    assert fit.grid_r(cells, 100)["open"] == 1.0


def _fake_solution(stack: float, r: dict, three_bets: bool) -> pm.DepthSolution:
    """The BB 3-bets (to 7.5 and 10) only when `three_bets`, so the 3-bet pots go unreached."""
    actions = {
        "": ["fold", "raise", "all-in"],
        "r": ["fold", "call", "raise", "raise 4x", "all-in"],
        "rr": ["fold", "call", "all-in"],
        "r4": ["fold", "call", "all-in"],
    }
    rows = {
        "": [0.0, 1.0, 0.0],
        "r": [0.0, 0.6, 0.2, 0.2, 0.0] if three_bets else [0.0, 1.0, 0.0, 0.0, 0.0],
        "rr": [0.0, 1.0, 0.0],
        "r4": [0.0, 1.0, 0.0],
    }
    strategy = {node: {name: list(row) for name in CLASS_NAMES} for node, row in rows.items()}
    return pm.DepthSolution(stack, None, True, 1e-4, 0.0, strategy, actions, dict(r), 0.0)


def test_a_round_on_fakes(tmp_path, monkeypatch) -> None:
    """Round 1 then round 2 with fake solves: what is measured, what falls back, the file."""
    solved, flop_specs = [], []

    def fake_run(jobs, workers):
        solved.extend(jobs)
        return [_fake_solution(j[0], j[5], three_bets=j[0] == 100) for j in jobs]

    def fake_bridge(spec, cache=None):
        """R 0.8 in the open, 1.1 in the 3x pot, 1.0 in the 4x pot, at E_BB 0.5."""
        flop_specs.append(spec)
        pot = spec["starting_pot"]
        report = {"path": [], "reached": True, "player": 0, "weights": [1.0], "equity": [0.5]}
        ev = {50: 0.8, 150: 1.1, 200: 1.0}[pot] * pot * 0.5
        return {
            "root_ev": [ev, pot - ev],
            "reports": [report],
            "exploitability_pct": 1.0,
            "iterations": 100,
            "build_s": 1.0,
            "solve_s": 2.0,
        }

    monkeypatch.setattr(fit, "SOLVES", tmp_path / "solves")
    monkeypatch.setattr(pm, "_run", fake_run)
    monkeypatch.setattr(fit.bridge, "solve", fake_bridge)
    monkeypatch.setattr(fit.bridge, "binary_sha256", lambda: "b" * 64)
    path = tmp_path / "fit.json"
    lines = []
    with pytest.raises(fit.FitError, match="AC power"):
        fit.run_round(1, path=path, on_ac=lambda: False, log=lines.append)
    with pytest.raises(fit.FitError, match="round 1"):
        fit.run_round(2, path=path, on_ac=lambda: True, log=lines.append)
    data = fit.run_round(1, path=path, on_ac=lambda: True, log=lines.append)
    assert [(j[0], j[5]) for j in solved] == [
        (d, dict.fromkeys(fit.POTS, 0.9)) for d in (25, 50, 100)
    ]
    assert all(j[2] == 1000 for j in solved)
    # The open is reached at every depth; the 3-bet pots only at 100 bb.
    assert len(flop_specs) == 20 * (3 + 2)
    assert {s["flop"] for s in flop_specs} == set(FLOPS)
    spec = next(s for s in flop_specs if s["starting_pot"] == 200)
    assert spec["effective_stack"] == 900 and spec["report"] == [[]]
    cells = fit.round_cells(data, 1)
    assert cells["open"][25]["r"] == pytest.approx(0.8)
    assert cells["open"][25]["se"] == pytest.approx(0, abs=1e-12)
    assert cells["3x"][100]["r"] == pytest.approx(1.1) and cells["3x"][100]["measured"]
    assert not cells["4x"][25]["measured"] and cells["4x"][25]["r"] == pytest.approx(1.0)
    assert "fallback" in cells["4x"][50]["source"]

    solved.clear()
    data = fit.run_round(2, path=path, on_ac=lambda: True, log=lines.append)
    assert solved[0][5] == {"open": pytest.approx(0.8), "3x": pytest.approx(1.1), "4x": 1.0}
    assert len(data["rounds"]) == 2
    assert json.loads(path.read_text(encoding="utf-8"))["flops"] == FLOPS
    by_depth, stored = fit.product_r(data)
    assert sorted(by_depth) == [float(g) for g in pm.GRID]
    assert by_depth[30.0]["open"] == pytest.approx(0.8)
    assert stored["4x"]["25"]["measured"] is False
    # A second run of round 2 reuses the cached preflop solves.
    solved.clear()
    fit.run_round(2, path=path, on_ac=lambda: True, log=lines.append)
    assert solved == []
