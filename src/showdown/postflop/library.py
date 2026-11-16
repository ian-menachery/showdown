"""The overnight flop library (DECISIONS 40 and its 2026-11-16 amendment).

Each spot's library is `data/library/<SPOT>/`: one `<flop>.json.gz` per solved flop, and a
`manifest.jsonl` line per flop once its file is written. A run resumes from the manifest.
"""

from __future__ import annotations

import ctypes
import datetime as dt
import gzip
import json
import random
import statistics
import sys
from collections.abc import Callable

from showdown.equity.cards import cards_str, combo_str, make_combo, parse_cards
from showdown.postflop import bridge
from showdown.postflop.flops import flop_weights, suit_distinct_flops
from showdown.postflop.spot import FlopSpot

LIBRARY = bridge.ROOT / "data" / "library"
SPOTS = {"3BP100": ("3bp", 100), "SRP25": ("srp", 25), "SRP50": ("srp", 50), "SRP100": ("srp", 100)}
NODES = ([], ["Check"], ["Bet"], ["Check", "Bet"])
"""The OOP first to act, the IP after a check, the IP facing a bet, the OOP facing a bet."""
SEED = 20261116
TOTAL_FLOPS = 22100


def coverage_order() -> list[tuple[int, ...]]:
    """Every suit-distinct flop, most-dealt first; ties in a seeded shuffle."""
    flops = list(suit_distinct_flops())
    random.Random(SEED).shuffle(flops)
    weights = flop_weights()
    return sorted(flops, key=lambda f: -weights[f])  # stable: the shuffle orders ties


def hand_key(text: str) -> str:
    """The bridge's hand string as showdown writes it, high card first."""
    return combo_str(make_combo(*parse_cards(text)))


def node_key(path: list[str]) -> str:
    return " ".join(path)


def entry(spot_name: str, flop: tuple[int, ...], result: dict, binary: str) -> dict:
    """One flop's file: whole-percent frequencies per hand at the four nodes."""
    nodes = {}
    for report in result["reports"]:
        if not report["reached"]:
            nodes[node_key(report["path"])] = {"reached": False}
            continue
        hands, s = report["hands"], report["strategy"]
        n = len(hands)
        nodes[node_key(report["path"])] = {
            "reached": True,
            "player": report["player"],
            "actions": report["actions"],
            "hands": {
                hand_key(h): [round(100 * s[a * n + i]) for a in range(len(report["actions"]))]
                for i, h in enumerate(hands)
            },
        }
    return {
        "spot": spot_name,
        "flop": cards_str(flop),
        "weight": flop_weights()[flop],
        "binary": binary,
        **{k: result[k] for k in ("exploitability_pct", "iterations", "build_s", "solve_s")},
        "nodes": nodes,
    }


def manifest(spot_name: str) -> dict[str, dict]:
    """The flops already solved, by flop string. A torn last line is ignored."""
    path = LIBRARY / spot_name / "manifest.jsonl"
    done = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            done[row["flop"]] = row
    return done


class _PowerStatus(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


def on_ac_power() -> bool:
    """True only when Windows reports AC power; unknown counts as not."""
    if sys.platform != "win32":
        return False
    status = _PowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return False
    return status.ACLineStatus == 1


def _keep_awake(on: bool) -> None:
    """Ask Windows not to sleep while the run lasts (ES_CONTINUOUS | ES_SYSTEM_REQUIRED)."""
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | (0x1 if on else 0))


def deadline(until: str, now: dt.datetime) -> dt.datetime:
    """The next local `HH:MM` after `now`."""
    t = dt.datetime.strptime(until, "%H:%M").time()
    d = dt.datetime.combine(now.date(), t)
    return d if d > now else d + dt.timedelta(days=1)


class LibraryError(RuntimeError):
    """The run cannot start or continue."""


def build(
    spot_name: str,
    *,
    until: dt.datetime | None = None,
    max_flops: int | None = None,
    now: Callable[[], dt.datetime] = dt.datetime.now,
    log: Callable[[str], None] = print,
) -> int:
    """Solve unsolved flops in coverage order until done, `until`, or off AC. Returns the count."""
    pot_type, stack = SPOTS[spot_name]
    folder = LIBRARY / spot_name
    binary = bridge.binary_sha256()
    done = manifest(spot_name)
    others = {row["binary"] for row in done.values()} - {binary}
    if others:
        raise LibraryError(
            f"{spot_name}'s library was built with another bridge binary ({others.pop()[:12]}); "
            f"this one is {binary[:12]}. Move the old library aside to start again."
        )
    todo = [f for f in coverage_order() if cards_str(f) not in done]
    folder.mkdir(parents=True, exist_ok=True)
    rows = folder / "manifest.jsonl"
    if rows.exists() and not rows.read_bytes().endswith(b"\n"):  # a torn last line
        with rows.open("a", encoding="utf-8") as f:
            f.write("\n")
    solved = failed = 0
    _keep_awake(True)
    try:
        for flop in todo:
            if max_flops is not None and solved + failed >= max_flops:
                break
            if until is not None and now() >= until:
                log(f"stopping: it is past {until:%H:%M}")
                break
            if not on_ac_power():
                if solved + failed == 0:
                    raise LibraryError("not on AC power: plug in before a library run")
                log("stopping: the laptop went on battery")
                break
            name = cards_str(flop)
            spot = FlopSpot.make(pot_type, stack, name)
            try:
                result = bridge.solve(spot.spec(report=NODES))
            except bridge.BridgeError as error:
                failed += 1
                log(f"{name}: FAILED, will retry next run: {str(error).splitlines()[0]}")
                continue
            data = entry(spot_name, flop, result, binary)
            tmp = folder / f"{name}.json.gz.tmp"
            with gzip.open(tmp, "wt", encoding="utf-8") as f:
                json.dump(data, f, separators=(",", ":"))
            tmp.replace(folder / f"{name}.json.gz")
            row = {k: v for k, v in data.items() if k != "nodes"}
            with rows.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            done[name] = row
            solved += 1
            log(
                f"{spot_name} {name}: {row['exploitability_pct']:.2f}% of pot, "
                f"{row['build_s'] + row['solve_s']:.0f} s; {len(done)} of "
                f"{len(suit_distinct_flops())} flops, coverage {coverage(done):.1%}"
            )
    finally:
        _keep_awake(False)
    log(f"{spot_name}: solved {solved} this run, {failed} failed; {status_line(spot_name)}")
    return solved


def coverage(done: dict[str, dict]) -> float:
    """The share of the 22,100 dealt flops that the solved flops stand for."""
    return sum(row["weight"] for row in done.values()) / TOTAL_FLOPS


def status_line(spot_name: str) -> str:
    done = manifest(spot_name)
    if not done:
        return f"{spot_name}: nothing solved yet"
    rows = list(done.values())
    seconds = [r["build_s"] + r["solve_s"] for r in rows]
    return (
        f"{spot_name}: {len(rows)} of {len(suit_distinct_flops())} flops, coverage "
        f"{coverage(done):.1%}; worst {max(r['exploitability_pct'] for r in rows):.2f}% of pot; "
        f"median {statistics.median(seconds):.0f} s, max {max(seconds):.0f} s, "
        f"total {sum(seconds) / 3600:.1f} h"
    )


def load(spot_name: str, flop: str) -> dict:
    """One solved flop's file (`flop` in canonical form, as the manifest writes it)."""
    with gzip.open(LIBRARY / spot_name / f"{flop}.json.gz", "rt", encoding="utf-8") as f:
        return json.load(f)
