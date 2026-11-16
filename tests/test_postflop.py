"""The postflop package without the solver binary: flops, spots, locks, summaries (DECISIONS 40).

Everything that runs the bridge is in test_gate_x.py (slow).
"""

import itertools
import json

import pytest

from showdown.cli import main
from showdown.equity.cards import parse_cards
from showdown.postflop import bridge, exploit
from showdown.postflop.flops import (
    SUIT_PERMUTATIONS,
    canonical,
    flop_weights,
    relabel,
    suit_distinct_flops,
)
from showdown.postflop.spot import FlopSpot, SpotError, model_range


def test_flops_up_to_suit_symmetry() -> None:
    assert len(suit_distinct_flops()) == 1755
    assert sum(flop_weights().values()) == 22100
    flop = parse_cards("Kc7d6c")
    key, perm = canonical(flop)
    assert tuple(sorted(relabel(flop, perm), reverse=True)) == key
    for p in SUIT_PERMUTATIONS:
        assert canonical(relabel(flop, p))[0] == key
    weights = flop_weights()
    assert weights[canonical(parse_cards("AhAdAc"))[0]] == 4
    assert weights[canonical(parse_cards("Kc7d6h"))[0]] == 24
    assert weights[canonical(parse_cards("Kc7c6c"))[0]] == 4


def test_spot_sizes_and_ranges() -> None:
    spot = FlopSpot.make("srp", 50, "kc7d6c")
    assert (spot.flop, spot.depth, spot.pot_chips, spot.stack_chips) == ("Kc7d6c", 50, 50, 475)
    deep = FlopSpot.make("3bp", 100, "Kc7d6c")
    assert (deep.pot_chips, deep.stack_chips) == (150, 925)
    assert FlopSpot.make("srp", 15, "Kc7d6c").depth == 25  # stacks up to 25 bb use 25
    spec = spot.spec(locks=[{"path": ["Bet"], "rule": "call"}], report=[["Check"]])
    assert spec["starting_pot"] == 50 and spec["target_pct"] == 2.0
    assert spec["locks"][0]["rule"] == "call" and spec["report"] == [["Check"]]
    text = model_range(50, "srp", "bb")
    for part in text.split(","):
        name, _, weight = part.partition(":")
        assert name and (not weight or 0 < float(weight) < 1)
    for bad, match in (
        (("srp", 50, "Kc7d"), "three different cards"),
        (("srp", 2, "Kc7d6c"), "stack above"),
        (("3bp", 50, "Kc7d6c"), "almost never reaches"),
        (("limp", 50, "Kc7d6c"), "srp or 3bp"),
    ):
        with pytest.raises(SpotError, match=match):
            FlopSpot.make(*bad)


def test_locks_and_paths() -> None:
    assert exploit.paths("sb") == exploit.Paths(["Check"], ["Bet"], ["Check", "Bet"], [])
    assert exploit.paths("bb") == exploit.Paths([], ["Check", "Bet"], ["Bet"], ["Check"])
    expected = {
        ("never-folds", "sb"): {"path": ["Check", "Bet"], "rule": "call"},
        ("over-folds", "bb"): {"path": ["Bet"], "rule": "fold_weakest", "fraction": 0.7},
        ("never-bets", "sb"): {"path": [], "rule": "check"},
        ("always-bets", "bb"): {"path": ["Check"], "rule": "bet"},
    }
    for (read, seat), lock in expected.items():
        assert exploit.lock_for(read, seat) == lock
    for read, seat in itertools.product(exploit.READS, ("sb", "bb")):
        assert exploit.lock_for(read, seat)["path"] is not None
    with pytest.raises(ValueError, match="read must be"):
        exploit.lock_for("tilts", "sb")


def test_action_labels() -> None:
    assert exploit.action_label("Check") == "check"
    assert exploit.action_label("Bet(17)") == "bet 1.7 bb"
    assert exploit.action_label("AllIn(475)") == "all-in 47.5 bb"
    assert exploit.action_label("Raise(67)") == "raise 6.7 bb"


def _report(path, weights, equity, strategy, actions=("Check", "Bet(17)")) -> dict:
    return {
        "path": path,
        "reached": True,
        "actions": list(actions),
        "hands": [f"h{k}" for k in range(len(weights))],
        "weights": weights,
        "equity": equity,
        "strategy": strategy,
    }


def test_summary_by_thirds() -> None:
    # Three hands of equal weight; hand 2 is weakest, hand 0 strongest. Strategy is per action,
    # then per hand: checks are [0.0, 0.5, 1.0], bets [1.0, 0.5, 0.0].
    s = exploit.summarize(_report(["Check"], [1, 1, 1], [0.9, 0.5, 0.1], [0, 0.5, 1, 1, 0.5, 0]))
    assert s.reached and s.actions == ["check", "bet 1.7 bb"]
    assert s.groups["weakest third"] == {"check": 1.0, "bet 1.7 bb": 0.0}
    assert s.groups["middle third"] == {"check": 0.5, "bet 1.7 bb": 0.5}
    assert s.groups["strongest third"] == {"check": 0.0, "bet 1.7 bb": 1.0}
    assert s.overall["bet 1.7 bb"] == pytest.approx(0.5)
    assert exploit.bet_frequency(s) == pytest.approx(0.5)
    assert exploit.bet_frequency(s, "strongest third") == 1.0
    assert not exploit.summarize({"path": ["Bet"], "reached": False}).reached
    assert not exploit.summarize(_report(["x"], [0, 0], [0.1, 0.2], [1, 1, 0, 0])).reached


def test_report_text() -> None:
    spot = FlopSpot.make("srp", 25, "Kc7d6c")

    def result(bet: float) -> dict:
        first = _report(["Check"], [1, 1, 1], [0.9, 0.5, 0.1], [1 - bet] * 3 + [bet] * 3)
        facing = _report(["Bet"], [1], [0.5], [0.2, 0.8], ("Fold", "Call"))
        lock = {"path": ["Check", "Bet"], "reached": False}
        return {
            "reports": [first, facing, lock],
            "root_ev": [17.5, 32.5],
            "exploitability_pct": 1.5,
            "build_s": 1.0,
            "solve_s": 9.0,
        }

    r = exploit.ExploitResult(spot, "sb", "never-folds", {}, result(0.25), result(0.75))
    text = exploit.report_text(r)
    assert "you are the SB (in position)" in text
    assert "Read: the BB never folds to your flop bet" in text
    assert "overall          check 75% -> 25%   bet 1.7 bb 25% -> 75%" in text
    assert "Your EV: 3.25 bb without the read, 3.25 bb with it" in text
    assert "solve time 10 s and 10 s" in text


def test_bridge_errors_and_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(bridge, "EXE", tmp_path / "missing.exe")
    with pytest.raises(bridge.BridgeError, match="postflop build"):
        bridge.solve({"a": 1})
    exe = tmp_path / "bridge.exe"
    exe.write_bytes(b"not really a binary")
    monkeypatch.setattr(bridge, "EXE", exe)
    cache = tmp_path / "cache"
    spec = {"flop": "Kc7d6c"}
    text = json.dumps(spec, sort_keys=True) + bridge.binary_sha256()
    import hashlib

    key = cache / (hashlib.sha256(text.encode()).hexdigest() + ".json")
    cache.mkdir()
    key.write_text('{"cached": true}', encoding="utf-8")
    assert bridge.solve(spec, cache=cache) == {"cached": True}
    monkeypatch.setattr(bridge, "SOLVER_DIR", tmp_path / "no-solver")
    with pytest.raises(bridge.BridgeError, match="is missing"):
        bridge.build()


def test_command_rejects_bad_spots() -> None:
    with pytest.raises(SystemExit, match="bad spot"):
        main(
            [
                "postflop",
                "exploit",
                "--stack",
                "50",
                "--flop",
                "Kc7d",
                "--hero",
                "sb",
                "--read",
                "never-folds",
            ]
        )
