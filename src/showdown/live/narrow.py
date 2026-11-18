"""The stopgap range model (DECISIONS 46): the villain's range narrowed by its own moves.

Each postflop move by the villain multiplies every combo's weight by a curve over its
strength band. The curves were fitted to solver output (`showdown postflop fit-ranges`)
and live in `data/range_model.json`. This is a model, not a solve, and is labelled so.
"""

from __future__ import annotations

import functools
import itertools
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from showdown.equity.cards import ALL_COMBOS, Combo, cards_str
from showdown.equity.evaluator import EVAL7_CARDS, evaluate_eval7

MODEL_PATH = Path(__file__).resolve().parents[3] / "data" / "range_model.json"
BANDS = 10
FLOP_RUNOUTS = 45
FLOORS = {"Check": 0.25}
FLOOR = 0.10
POSITION = {"bb": "oop", "sb": "ip"}
INDEX = {c: i for i, c in enumerate(ALL_COMBOS)}
_MOVE = re.compile(
    r"^(preflop|flop|turn|river) (SB|BB) "
    r"(folds|checks|calls (\S+)|bets (\S+)|raises to (\S+))( \(all-in\))?$"
)
STREET_CARDS = {"flop": 3, "turn": 4, "river": 5}


# --- strength ----------------------------------------------------------------------


def _runout(full: tuple[int, ...], total: np.ndarray, count: np.ndarray) -> None:
    """Add each live combo's share of the other live combos it beats, ties half, on `full`."""
    dead = set(full)
    live = [i for i, c in enumerate(ALL_COMBOS) if not dead.intersection(c)]
    b = [EVAL7_CARDS[c] for c in full]
    ranks = np.array(
        [
            evaluate_eval7([EVAL7_CARDS[ALL_COMBOS[i][0]], EVAL7_CARDS[ALL_COMBOS[i][1]], *b])
            for i in live
        ]
    )
    ordered = np.sort(ranks)
    below = np.searchsorted(ordered, ranks, side="left")
    equal = np.searchsorted(ordered, ranks, side="right") - below - 1
    total[live] += (below + 0.5 * equal) / (len(live) - 1)
    count[live] += 1


@functools.lru_cache(maxsize=64)
def scores(board: tuple[int, ...]) -> np.ndarray:
    """Per combo in `ALL_COMBOS` order, its equity against a random hand; NaN on the board."""
    total, count = np.zeros(len(ALL_COMBOS)), np.zeros(len(ALL_COMBOS))
    deck = [c for c in range(52) if c not in board]
    if len(board) == 5:
        runouts = [()]
    elif len(board) == 4:
        runouts = [(r,) for r in deck]
    else:
        pairs = list(itertools.combinations(deck, 2))
        runouts = random.Random(cards_str(board)).sample(pairs, FLOP_RUNOUTS)
    for extra in runouts:
        _runout(tuple(board) + extra, total, count)
    with np.errstate(invalid="ignore"):
        return np.where(count > 0, total / np.maximum(count, 1), np.nan)


def percentiles(score: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Each combo's place in the weighted range: (weight below + half the weight equal) / total.

    Combos with no score (on the board) or no weight get NaN.
    """
    out = np.full(len(score), np.nan)
    keep = np.flatnonzero(~np.isnan(score) & (weights > 0))
    if len(keep) == 0:
        return out
    s, w = score[keep], weights[keep]
    order = np.argsort(s, kind="stable")
    s_sorted, cum = s[order], np.concatenate([[0.0], np.cumsum(w[order])])
    lo = np.searchsorted(s_sorted, s, side="left")
    hi = np.searchsorted(s_sorted, s, side="right")
    out[keep] = (cum[lo] + 0.5 * (cum[hi] - cum[lo])) / cum[-1]
    return out


def bands(p: np.ndarray) -> np.ndarray:
    """The decile, 0 to 9, of each percentile; -1 where there is none."""
    b = np.where(np.isnan(p), -1, np.floor(np.nan_to_num(p) * BANDS)).astype(int)
    return np.where(b >= BANDS, BANDS - 1, b)


# --- the villain's moves -------------------------------------------------------------


@dataclass(frozen=True)
class VillainMove:
    street: str
    node: str
    """first, after_check, facing_bet or facing_allin."""
    action: str
    """Check, Bet, Raise or Call."""
    f: float | None
    """A bet's or raise's size as a share of the pot; for a call, the size faced."""


def villain_moves(history: tuple[str, ...], villain_seat: str) -> list[VillainMove]:
    """The villain's postflop moves, with the pot rebuilt from the blinds (0.5 and 1 bb)."""
    put, pot_start, street = {"sb": 0.5, "bb": 1.0}, 0.0, "preflop"
    acted, allin_open, out = 0, False, []
    for text in history:
        m = _MOVE.match(text)
        if not m:
            raise ValueError(f"unreadable move {text!r}")
        if m.group(1) != street:
            pot_start, put = pot_start + sum(put.values()), {"sb": 0.0, "bb": 0.0}
            street, acted, allin_open = m.group(1), 0, False
        me = m.group(2).lower()
        other = "bb" if me == "sb" else "sb"
        pot = pot_start + put["sb"] + put["bb"]
        to_call = put[other] - put[me]
        if to_call > 1e-9:
            node = "facing_allin" if allin_open else "facing_bet"
        else:
            node = "first" if acted == 0 else "after_check"
        verb, f, action = m.group(3).split()[0], None, None
        if verb == "checks":
            action = "Check"
        elif verb == "calls":
            action, f = "Call", to_call / (pot - to_call)
            put[me] += float(m.group(4))
        elif verb in ("bets", "raises"):
            to = float(m.group(5) or m.group(6))
            action = "Bet" if to_call <= 1e-9 else "Raise"
            f = (to - put[me] - to_call) / (pot + to_call)
            put[me], allin_open = to, bool(m.group(7))
        acted += 1
        if me == villain_seat and street != "preflop" and action is not None:
            out.append(VillainMove(street, node, action, f))
    return out


# --- the curves ----------------------------------------------------------------------


@dataclass(frozen=True)
class RangeModel:
    curves: dict
    """"pot type|street|position|node" -> {action: {"f": mean size or None, "freq": [10]}}."""
    source: str = ""

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> RangeModel | None:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        curves = {key: value["actions"] for key, value in data["curves"].items()}
        return cls(curves, data.get("source", ""))

    def curve(self, pot_type: str, street: str, position: str, node: str, action: str):
        """(mean f, shape) for one action, or None. Shape = frequency / its largest band's."""
        found = self.curves.get(f"{pot_type}|{street}|{position}|{node}", {}).get(action)
        if found is None and street == "flop" and node == "facing_allin":
            return self.curve(pot_type, "turn", position, node, action)
        if found is None or max(found["freq"]) <= 0:
            return None
        peak = max(found["freq"])
        return found["f"], np.array(found["freq"], dtype=float) / peak

    def shape(self, pot_type: str, position: str, move: VillainMove) -> np.ndarray | None:
        """The band shape for one move, interpolated by size between its two anchors."""
        if move.action == "Check":
            found = self.curve(pot_type, move.street, position, move.node, "Check")
            return None if found is None else found[1]
        if move.action == "Call":
            anchors = [
                self.curve(pot_type, move.street, position, node, "Call")
                for node in ("facing_bet", "facing_allin")
            ]
        else:
            anchors = [
                self.curve(pot_type, move.street, position, move.node, action)
                for action in (move.action, "AllIn")
            ]
        anchors = sorted((a for a in anchors if a is not None), key=lambda a: a[0])
        if not anchors:
            return None
        if len(anchors) == 1 or anchors[1][0] - anchors[0][0] <= 1e-12:
            return anchors[0][1]
        (fa, sa), (fb, sb) = anchors
        t = min(max((move.f - fa) / (fb - fa), 0.0), 1.0)
        return (1 - t) * sa + t * sb


def narrow(
    model: RangeModel,
    combos: tuple[Combo, ...],
    weights: tuple[float, ...] | None,
    board: tuple[int, ...],
    history: tuple[str, ...],
    villain_seat: str,
    pot_type: str,
) -> tuple[tuple[float, ...], int, int]:
    """(new weights, villain moves used, villain moves with no curve)."""
    w = np.zeros(len(ALL_COMBOS))
    idx = [INDEX[c] for c in combos]
    w[idx] = 1.0 if weights is None else np.array(weights, dtype=float)
    used = missing = 0
    position = POSITION[villain_seat]
    for move in villain_moves(history, villain_seat):
        shape = model.shape(pot_type, position, move)
        if shape is None:
            missing += 1
            continue
        b = bands(percentiles(scores(tuple(board[: STREET_CARDS[move.street]])), w))
        floor = FLOORS.get(move.action, FLOOR)
        mult = np.where(b >= 0, np.maximum(shape[np.maximum(b, 0)], floor), 1.0)
        w = w * mult
        used += 1
    return tuple(float(x) for x in w[idx]), used, missing
