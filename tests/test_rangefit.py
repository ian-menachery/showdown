"""The range model's fit (DECISIONS 46): its board draw and its per-band bookkeeping."""

import json

import pytest

from showdown.equity.cards import cards_str, parse_cards
from showdown.live.narrow import RangeModel
from showdown.postflop import rangefit


def test_the_fit_reuses_s2bs_flops() -> None:
    flops = [cards_str(f) for _, _, _, f in rangefit.spike_flops(20261117)]
    assert flops[:3] == ["Jc7d6d", "9c8d2h", "QcTc8d"]  # S2b's first three 3BP100 boards
    assert flops[10:12] == ["KcQc4c", "Qc8c2d"]  # and SRP50's


def test_curves_pool_frequencies_by_band_and_record_sizes(tmp_path) -> None:
    # Five hands on AsKsQd7c2h, weakest first, one per band (1, 3, 5, 7, 9) at equal weight.
    report = {
        "path": [],
        "reached": True,
        "player": 0,
        "actions": ["Check", "Bet(25)"],
        "hands": ["6c5c", "8d8h", "KhKd", "AhAd", "JhTh"],
        "weights": [1.0] * 5,
        "strategy": [1.0, 0.8, 0.6, 0.4, 0.2] + [0.0, 0.2, 0.4, 0.6, 0.8],
    }
    curves = rangefit.Curves()
    rangefit._add_solve(
        curves, "srp", "river", {"reports": [report]}, parse_cards("AsKsQd7c2h"), 50
    )
    out = curves.as_dict()["srp|river|oop|first"]
    assert out["nodes"] == 1
    assert out["actions"]["Bet"]["f"] == pytest.approx(0.5)
    assert out["actions"]["Check"]["f"] is None
    bet = out["actions"]["Bet"]["freq"]
    assert [bet[b] for b in (1, 3, 5, 7, 9)] == pytest.approx([0.0, 0.2, 0.4, 0.6, 0.8])
    assert [bet[b] for b in (0, 2, 4, 6, 8)] == [0.0] * 5  # no hands there

    # The model reads what the fit writes.
    path = tmp_path / "range_model.json"
    path.write_text(json.dumps({"curves": curves.as_dict()}), encoding="utf-8")
    f, shape = RangeModel.load(path).curve("srp", "river", "oop", "first", "Bet")
    assert f == pytest.approx(0.5) and max(shape) == 1.0
