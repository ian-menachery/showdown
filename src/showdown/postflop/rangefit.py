"""Fit the stopgap range model's curves to solver output (DECISIONS 46).

For S2b's and S2c's 40 flops (DECISIONS 44, 45), every reached node of the flop entries and
of turn and river solves gives, per strength band, how often the acting player takes each
action. `showdown postflop fit-ranges` runs this once and writes `data/range_model.json`.
The solver runs as a separate process (DECISIONS 29); the file holds frequencies only.
Its preflop ranges are DECISIONS 34's model, which the fit was run on (DECISIONS 49).
"""

from __future__ import annotations

import itertools
import json
import random
import re
import subprocess
from collections.abc import Callable

import numpy as np

from showdown import preflop_model as pm
from showdown.equity.cards import (
    CLASS_NAMES,
    cards_str,
    class_index,
    class_of,
    combo_str,
    make_combo,
    parse_cards,
)
from showdown.live import narrow
from showdown.postflop import bridge, library
from showdown.postflop.flops import canonical
from showdown.postflop.spot import SETTINGS, TREE_T1, FlopSpot, model_range

SPIKE_SEEDS = (20261117, 20261118)
"""S2b's and S2c's boards."""
FIT_SEED = 20261119
SPOTS = (("3BP100", "3bp", 100), ("SRP50", "srp", 50))
BOARDS = 10
LINES = ("check-check", "bet-call", "check-bet-call")
MIN_COMBOS = 5.0
TURNS = 2
REPORT = ([], ["Check"], ["Bet"], ["Check", "Bet"], ["AllIn"], ["Check", "AllIn"])
NODE_NAMES = {
    (): "first",
    ("Check",): "after_check",
    ("Bet",): "facing_bet",
    ("Check", "Bet"): "facing_bet",
    ("AllIn",): "facing_allin",
    ("Check", "AllIn"): "facing_allin",
}
STREETS_EXE = bridge.TARGET_DIR / "release" / "streets.exe"
CACHE = bridge.EXTERNAL / "cache" / "s2b"
"""The flop solves S2b and S2c cached (DECISIONS 45)."""
STREET_TREE = {k: v for k, v in TREE_T1.items() if not k.startswith("flop")}
SOLVER_COMBOS = [(b, a) for a, b in itertools.combinations(range(52), 2)]
"""The solver's raw range order, high card first."""
_SIZED = re.compile(r"^(\w+)\((\d+)\)$")


def spike_flops(seed: int) -> list[tuple[str, str, int, tuple[int, ...]]]:
    """(spot, pot type, stack, canonical flop), drawn as the S2b spike draws its boards."""
    rng, out = random.Random(seed), []
    for name, pot_type, stack in SPOTS:
        for _ in range(BOARDS):
            deck = list(range(52))
            rng.shuffle(deck)
            out.append((name, pot_type, stack, canonical(tuple(deck[:3]))[0]))
    return out


def flop_entry(spot_name: str, pot_type: str, stack: int, flop: tuple[int, ...]) -> dict:
    name = cards_str(flop)
    if name in library.manifest(spot_name):
        return library.load(spot_name, name)
    spot = FlopSpot.make(pot_type, stack, name, pm.v1_model_path())
    result = bridge.solve(spot.spec(report=list(library.NODES)), cache=CACHE)
    return library.entry(spot_name, flop, result, bridge.binary_sha256())


def preflop_weights(depth: float, pot_type: str, seat: str) -> np.ndarray:
    """Per combo in the solver's order, its class's weight in the flop solve's range string."""
    by_class = [0.0] * len(CLASS_NAMES)
    for part in model_range(depth, pot_type, seat, pm.v1_model_path()).split(","):
        name, _, w = part.partition(":")
        by_class[class_index(name)] = float(w) if w else 1.0
    return np.array([by_class[class_of(c)] for c in SOLVER_COMBOS])


def _amount(name: str) -> int | None:
    m = _SIZED.match(name)
    return int(m.group(2)) if m else None


def _action_class(name: str) -> str:
    m = _SIZED.match(name)
    return m.group(1) if m else name


def entry_frequency(node: dict, action: str) -> tuple[np.ndarray, int | None]:
    """Per solver combo, the stored frequency of Check, Call or the smallest Bet."""
    names = node["actions"]
    i = next(k for k, a in enumerate(names) if _action_class(a) == action)
    hands = node["hands"]
    freq = np.array([hands.get(combo_str(c), [0] * len(names))[i] / 100 for c in SOLVER_COMBOS])
    return freq, _amount(names[i])


def line_ranges(entry: dict, line: str, pre: list[np.ndarray], pot: int, stack: int):
    """(OOP weights, IP weights, pot, stack) after a flop line, as the S2b spike narrows."""
    n = entry["nodes"]
    if line == "check-check":
        oop, bet = pre[0] * entry_frequency(n[""], "Check")[0], 0
        ip = pre[1] * entry_frequency(n["Check"], "Check")[0]
    elif line == "bet-call":
        f, bet = entry_frequency(n[""], "Bet")
        oop, ip = pre[0] * f, pre[1] * entry_frequency(n["Bet"], "Call")[0]
    else:
        f, bet = entry_frequency(n["Check"], "Bet")
        oop = pre[0] * entry_frequency(n[""], "Check")[0]
        oop = oop * entry_frequency(n["Check Bet"], "Call")[0]
        ip = pre[1] * f
    return oop, ip, pot + 2 * bet, stack - bet


def live_weight(weights: np.ndarray, board: tuple[int, ...]) -> float:
    dead = set(board)
    return float(sum(w for c, w in zip(SOLVER_COMBOS, weights, strict=True) if not dead & set(c)))


class Curves:
    """Reach-weighted action frequencies per strength band, pooled by key."""

    def __init__(self) -> None:
        self.weight: dict[str, np.ndarray] = {}
        self.taken: dict[str, dict[str, np.ndarray]] = {}
        self.sizes: dict[str, dict[str, list[float]]] = {}
        self.nodes: dict[str, int] = {}

    def add(self, key: str, report: dict, board: tuple[int, ...], pot: int, faced: int) -> None:
        """One reached node. `faced` is the bet faced in chips (0 if none)."""
        combos = [make_combo(*parse_cards(h)) for h in report["hands"]]
        idx = [narrow.INDEX[c] for c in combos]
        w = np.zeros(len(narrow.INDEX))
        w[idx] = report["weights"]
        b = narrow.bands(narrow.percentiles(narrow.scores(board), w))[idx]
        weights, n = np.asarray(report["weights"], dtype=float), len(combos)
        strategy = np.asarray(report["strategy"], dtype=float).reshape(-1, n)
        ok = b >= 0
        band_weight = np.bincount(b[ok], weights=weights[ok], minlength=narrow.BANDS)
        self.weight[key] = self.weight.get(key, 0) + band_weight
        self.nodes[key] = self.nodes.get(key, 0) + 1
        taken, sizes = self.taken.setdefault(key, {}), self.sizes.setdefault(key, {})
        for a, name in enumerate(report["actions"]):
            action = _action_class(name)
            got = np.bincount(b[ok], weights=(weights * strategy[a])[ok], minlength=narrow.BANDS)
            taken[action] = taken.get(action, 0) + got
            amount = _amount(name)
            if action in ("Call", "Fold"):
                f = faced / pot
            elif action == "Raise" or (action == "AllIn" and faced):
                f = (amount - faced) / (pot + 2 * faced)
            elif amount is not None:
                f = amount / pot
            else:
                f = None
            if f is not None:
                sizes.setdefault(action, []).append(f)

    def as_dict(self) -> dict:
        out = {}
        for key, weight in sorted(self.weight.items()):
            actions = {}
            for action, taken in self.taken[key].items():
                freq = np.divide(taken, weight, out=np.zeros(narrow.BANDS), where=weight > 0)
                sizes = self.sizes[key].get(action)
                actions[action] = {
                    "f": round(float(np.mean(sizes)), 4) if sizes else None,
                    "freq": [round(float(x), 4) for x in freq],
                }
            out[key] = {"nodes": self.nodes[key], "actions": actions}
        return out


def _faced(reports: dict[tuple, dict], path: tuple[str, ...]) -> int:
    """The chips bet at the parent node that `path` follows (0 at a first decision)."""
    if not path or path[-1] == "Check":
        return 0
    parent = reports[path[:-1]]
    return next(_amount(a) for a in parent["actions"] if _action_class(a) == path[-1])


def _add_solve(curves: Curves, pot_type: str, street: str, result: dict, board, pot: int) -> None:
    reports = {tuple(r["path"]): r for r in result["reports"] if r["reached"]}
    for path, report in reports.items():
        position = "oop" if report["player"] == 0 else "ip"
        key = f"{pot_type}|{street}|{position}|{NODE_NAMES[path]}"
        curves.add(key, report, board, pot, _faced(reports, path))


def _entry_reports(entry: dict, pre: list[np.ndarray]) -> list[dict]:
    """The flop entry's four nodes as bridge reports, with reach weights."""
    out = []
    check = entry_frequency(entry["nodes"][""], "Check")[0]
    for key in ("", "Check", "Bet", "Check Bet"):
        node = entry["nodes"][key]
        if not node["reached"]:
            continue
        reach = pre[node["player"]] * (check if key == "Check Bet" else 1.0)
        keep = [i for i, c in enumerate(SOLVER_COMBOS) if combo_str(c) in node["hands"]]
        out.append(
            {
                "path": key.split(),
                "reached": True,
                "player": node["player"],
                "actions": node["actions"],
                "hands": [combo_str(SOLVER_COMBOS[i]) for i in keep],
                "weights": [float(reach[i]) for i in keep],
                "strategy": [
                    node["hands"][combo_str(SOLVER_COMBOS[i])][a] / 100
                    for a in range(len(node["actions"]))
                    for i in keep
                ],
            }
        )
    return out


def solve_streets(spec: dict, timeout: float = 120.0) -> dict:
    proc = subprocess.run(
        [str(STREETS_EXE)],
        input=json.dumps(spec),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise bridge.BridgeError("the streets bridge failed:\n" + proc.stderr[-2000:])
    return json.loads(proc.stdout)


def fit(log: Callable[[str], None] = print) -> dict:
    """Solve the fit set and return the model file's contents."""
    if not STREETS_EXE.exists():
        raise bridge.BridgeError(f"{STREETS_EXE} is missing: run `showdown postflop build`")
    curves, solves = Curves(), 0
    flops = [f for seed in SPIKE_SEEDS for f in spike_flops(seed)]
    for spot_name, pot_type, stack, flop in flops:
        spot = FlopSpot.make(pot_type, stack, cards_str(flop))
        pre = [preflop_weights(spot.depth, pot_type, seat) for seat in ("bb", "sb")]
        entry = flop_entry(spot_name, pot_type, stack, flop)
        flop_reports = {"reports": _entry_reports(entry, pre)}
        _add_solve(curves, pot_type, "flop", flop_reports, flop, spot.pot_chips)
        for line in LINES:
            oop, ip, pot, behind = line_ranges(entry, line, pre, spot.pot_chips, spot.stack_chips)
            if min(live_weight(oop, flop), live_weight(ip, flop)) < MIN_COMBOS:
                log(f"{spot_name} {cards_str(flop)} {line}: under {MIN_COMBOS:g} combos, skipped")
                continue
            deck = [c for c in range(52) if c not in flop]
            random.Random(f"{FIT_SEED}|{cards_str(flop)}|{line}").shuffle(deck)
            for k in range(TURNS):
                turn, river = deck[2 * k], deck[2 * k + 1]
                for street, board in (("turn", flop + (turn,)), ("river", flop + (turn, river))):
                    spec = {
                        "oop_range": [float(x) for x in oop],
                        "ip_range": [float(x) for x in ip],
                        "board": cards_str(board),
                        "starting_pot": pot,
                        "effective_stack": behind,
                        **STREET_TREE,
                        **SETTINGS,
                        "report": [list(p) for p in REPORT],
                    }
                    if street == "turn" and line == "check-bet-call":
                        spec["oop_turn_bet"] = ""
                    result = solve_streets(spec)
                    solves += 1
                    _add_solve(curves, pot_type, street, result, board, pot)
                    log(
                        f"{solves:>3} {spot_name} {street:<5} {cards_str(board):<10} {line:<14} "
                        f"{result['exploitability_pct']:.2f}% of pot"
                    )
    return {
        "source": f"DECISIONS 46: {solves} turn and river solves and the 40 flop entries of "
        f"S2b and S2c (seeds {SPIKE_SEEDS[0]}, {SPIKE_SEEDS[1]}; fit seed {FIT_SEED})",
        "bands": narrow.BANDS,
        "curves": curves.as_dict(),
    }


def write(data: dict) -> None:
    narrow.MODEL_PATH.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
