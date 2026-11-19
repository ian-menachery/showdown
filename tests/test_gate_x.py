"""Gate X: exploit solves between sessions (DECISIONS 40). Needs the built bridge.

SRP50 with the hero as the SB, on 10 flops drawn with seed 20261116 from the 1,755
suit-distinct flops. Each solve's bridge output is cached under data/external, keyed by
the spec and the binary's SHA-256, so a rerun with the same binary replays it; deleting
the cache, or rebuilding the bridge, solves again.

X3 failed (GATES.md, 2026-11-15) and is marked as a strict expected failure, with its bar
unchanged. The spots' ranges are pinned to DECISIONS 34's model, so the cache still replays
(DECISIONS 49).
"""

import importlib.util
import random
from pathlib import Path

import pytest

from showdown import preflop_model as pm
from showdown.cli import main
from showdown.equity.cards import cards_str
from showdown.equity.matrix import PreflopMatrix
from showdown.postflop import bridge, exploit
from showdown.postflop.flops import suit_distinct_flops
from showdown.postflop.spot import FlopSpot

pytestmark = pytest.mark.slow

FLOPS = [
    "Tc5d3c",
    "Tc6c2c",
    "KcQc2c",
    "Qc6c2c",
    "AhAdAc",
    "Jc8d8c",
    "QcJdTh",
    "KcQd3d",
    "Jc7d7c",
    "Kc9c2d",
]
CACHE = bridge.EXTERNAL / "cache" / "gate-x"
WEAK = "weakest third"


def test_the_flops_are_the_seeded_draw() -> None:
    draw = random.Random(20261116).sample(list(suit_distinct_flops()), 10)
    assert [cards_str(f) for f in draw] == FLOPS


@pytest.fixture(scope="module")
def results() -> dict[tuple[str, str], exploit.ExploitResult]:
    out = {}
    for flop in FLOPS:
        spot = FlopSpot.make("srp", 50, flop, pm.v1_model_path())
        for read in ("never-folds", "over-folds"):
            out[(flop, read)] = exploit.run(spot, "sb", read, cache=CACHE)
    return out


def test_x1_the_lock_holds(results) -> None:
    for (flop, read), r in results.items():
        (applied,) = r.locked["locks"]
        (reported,) = [x for x in r.locked["reports"] if x["path"] == applied["path"]]
        assert reported["hands"] == applied["hands"], (flop, read)
        worst = max(
            abs(a - b) for a, b in zip(reported["strategy"], applied["strategy"], strict=True)
        )
        assert worst <= 1e-6, (flop, read, worst)


def test_x2_every_solve_converges_within_10_minutes(results) -> None:
    rows = []
    for (flop, read), r in results.items():
        for which in (r.baseline, r.locked):
            seconds = which["build_s"] + which["solve_s"]
            rows.append((flop, read, which["exploitability_pct"], seconds, which["iterations"]))
            assert which["exploitability_pct"] <= 2.0, rows[-1]
            assert seconds <= 600, rows[-1]
    print("\n" + "\n".join(f"{f} {r:<12} {e:.3f}% {s:6.1f} s iter {i}" for f, r, e, s, i in rows))


def _weak_bet(r: exploit.ExploitResult, which: str) -> float:
    return exploit.bet_frequency(r.summary(which, exploit.paths("sb").hero_first), WEAK)


@pytest.mark.xfail(
    strict=True,
    reason="Gate X3 FAIL (GATES.md, 2026-11-15): with the model's ranges the weakest third's "
    "betting fell on 3 of 10 flops, not 8. The bar is unchanged; strict, so a pass shows up.",
)
def test_x3_against_never_folds_the_weakest_third_bets_less(results) -> None:
    falls = 0
    for flop in FLOPS:
        r = results[(flop, "never-folds")]
        before, after = _weak_bet(r, "baseline"), _weak_bet(r, "locked")
        falls += after < before
        print(f"never-folds {flop}: weakest third bets {before:.1%} -> {after:.1%}")
    assert falls >= 8, falls


def test_x4_against_over_folds_the_weakest_third_bets_more(results) -> None:
    rises = 0
    for flop in FLOPS:
        r = results[(flop, "over-folds")]
        before, after = _weak_bet(r, "baseline"), _weak_bet(r, "locked")
        rises += after > before
        print(f"over-folds {flop}: weakest third bets {before:.1%} -> {after:.1%}")
    assert rises >= 8, rises


def test_the_bridge_reproduces_s4s_node_lock() -> None:
    """Not a Gate X bar: evidence that X3's failure is not a bridge or summary bug.

    S4 (GATES.md) ran the same lock on SRP50 Kc7d6c with S2's top-% ranges through its own
    bridge: the SB's betting after a check rose from 53.1% to 67.2%, and its weakest third's
    fell from 53.8% to 37.1%. This bridge, with those ranges, must point the same ways.
    """
    path = Path("spikes/2026-11-15-texassolver-speed.py")
    module_spec = importlib.util.spec_from_file_location("spike_s2", path)
    s2 = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(s2)
    matrix = PreflopMatrix.load("data/preflop_169_exact.npz")
    _, _, ip_top, oop_top = s2.SPOTS["SRP50"][:4]
    spot = FlopSpot.make("srp", 50, "Kc7d6c", pm.v1_model_path())
    lock = exploit.lock_for("never-folds", "sb")
    p = exploit.paths("sb")
    out = {}
    for which, locks in (("baseline", []), ("locked", [lock])):
        spec = spot.spec(locks=locks, report=[p.hero_first, p.hero_facing_bet, lock["path"]])
        spec["ip_range"] = s2.top_range(ip_top, matrix)
        spec["oop_range"] = s2.top_range(oop_top, matrix)
        out[which] = bridge.solve(spec, cache=bridge.EXTERNAL / "cache" / "x3-crosscheck")
    r = exploit.ExploitResult(spot, "sb", "never-folds", lock, out["baseline"], out["locked"])
    before, after = r.summary("baseline", p.hero_first), r.summary("locked", p.hero_first)
    overall = (exploit.bet_frequency(before), exploit.bet_frequency(after))
    weak = (exploit.bet_frequency(before, WEAK), exploit.bet_frequency(after, WEAK))
    print(
        f"\nS4 ranges: bets {overall[0]:.1%} -> {overall[1]:.1%}, "
        f"weakest third {weak[0]:.1%} -> {weak[1]:.1%}"
    )
    assert overall[1] > overall[0] and weak[1] < weak[0]


def test_x5_the_command_prints_both_strategies_and_evs(capsys) -> None:
    args = ["postflop", "exploit", "--stack", "25", "--flop", "Kc7d6c", "--hero", "sb"]
    assert main([*args, "--read", "never-bets"]) == 0
    out = capsys.readouterr().out
    assert "Read: the BB never bets the flop when it can" in out
    assert "Your first flop decision: without the read -> with it" in out
    assert "weakest third" in out and "strongest third" in out
    assert "bb without the read," in out and "bb with it" in out
