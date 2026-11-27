"""Six-max preflop spots: each action's EV against stated opponent profiles (DECISIONS 53).

A spot is the hero's seat, k limpers ahead (0 to 3), 100 bb stacks, blinds 0.5/1 and an
ante from every player. The opponents follow one profile: a limp range, and how often each
kind of player folds, calls or re-raises. This is a best response to those assumptions,
not a solver. Postflop is valued as R × equity × pot, never played.

How the EV is estimated:
- Each deal gives every opponent a hand from its range (the whole set redrawn if two share
  a card) and a board. Opponents act on their own cards only, so one deal serves every
  hero hand and every action.
- The hero's combo is drawn among those of its class that miss every dealt card, and the
  deal is weighted by how many there are. That equals dealing the hero first.
- A pot left heads-up pays the exact class equity M[hero, villain]; a 3+ way pot is scored
  on the deal's board, split equally among the best hands, as in `multiway.py`.
"""

from __future__ import annotations

import json
import re
import zlib
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path

import numpy as np

from showdown.equity.cards import (
    ALL_COMBOS,
    CLASS_COMBOS,
    CLASS_NAMES,
    RANKS,
    Combo,
    cards_str,
    class_index,
    class_of,
    make_combo,
    parse_cards,
)
from showdown.equity.evaluator import EVAL7_CARDS, evaluate_eval7
from showdown.equity.matrix import PreflopMatrix
from showdown.equity.ranges import parse_range
from showdown.live.jam import jam_equity

ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "data" / "preflop_169_exact.npz"
PROFILES_PATH = ROOT / "data" / "sixmax_profiles.json"

SEATS = ("UTG", "HJ", "CO", "BTN", "SB", "BB")
POSTFLOP = {"SB": 0, "BB": 1, "UTG": 2, "HJ": 3, "CO": 4, "BTN": 5}
MAX_LIMPERS = {"UTG": 0, "HJ": 1, "CO": 2, "BTN": 3, "SB": 3, "BB": 3}
STACK = 100.0
BLINDS = {"SB": 0.5, "BB": 1.0}
R = {"raise_ip": 1.00, "raise_oop": 0.75, "limp_ip": 0.85, "limp_oop": 0.75}
"""raise_oop was 0.90 until DECISIONS 56; Gates M, M2 and K were scored at 0.90."""
GATED_RAISE_OOP = 0.90
GATED_STANDARD_LIMPERS = "regular"
"""Gates M2 and K were scored with the standard profile's limpers from regular (DECISIONS 57)."""
R_BAND = (-0.1, 0.0, 0.1)
FOLD_BAND = (-0.10, 0.0, 0.10)
NOISE_SE = 3.0
TIE = 1e-9
"""Another action wins a band point only by more than this (float noise on exact ties)."""
SAMPLES = 40_000

COMBO_CARDS = np.array(ALL_COMBOS, dtype=np.int64)
COMBO_CLASS = np.array([class_of(c) for c in ALL_COMBOS], dtype=np.int64)
CLASS_SIZES = np.array([len(c) for c in CLASS_COMBOS], dtype=float)
_COMBO_INDEX = {c: i for i, c in enumerate(ALL_COMBOS)}


@cache
def matrix() -> PreflopMatrix:
    return PreflopMatrix.load(MATRIX_PATH)


@cache
def strength_order() -> np.ndarray:
    """Class indices from weakest to strongest by exact equity against a random hand."""
    m = matrix()
    vs_random = (m.equity * m.pair_counts).sum(axis=1) / m.pair_counts.sum(axis=1)
    return np.lexsort((np.arange(169), vs_random))


# --- ranges as combo weights --------------------------------------------------


def from_classes(class_weights: np.ndarray) -> np.ndarray:
    """Combo weights from per-class fractions."""
    return np.asarray(class_weights, dtype=float)[COMBO_CLASS]


def from_text(text: str) -> np.ndarray:
    w = np.zeros(len(ALL_COMBOS))
    w[[_COMBO_INDEX[c] for c in parse_range(text)]] = 1.0
    return w


def class_mass(w: np.ndarray) -> np.ndarray:
    """Per class, the combos in the range (weighted)."""
    return np.bincount(COMBO_CLASS, weights=w, minlength=169)


def _bounds(w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Each class's [low, high) share of the range, weakest first, as fractions of it."""
    mass = class_mass(w)
    order = strength_order()
    cum = np.cumsum(mass[order])
    low = np.empty(169)
    low[order] = cum - mass[order]
    return low / cum[-1], (low + mass) / cum[-1]


def band(w: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Per class, the fraction of the class (all its combos) whose place q lies in [lo, hi)."""
    low, high = _bounds(w)
    width = high - low
    overlap = np.clip(np.minimum(high, hi) - np.maximum(low, lo), 0.0, None)
    part = np.divide(overlap, width, out=np.zeros(169), where=width > 0)
    return part * class_mass(w) / CLASS_SIZES


def top(w: np.ndarray, x: float) -> np.ndarray:
    return band(w, 1.0 - x, 1.0 + 1e-12)


ALL_HANDS = np.ones(len(ALL_COMBOS))


# --- profiles -------------------------------------------------------------------


@dataclass(frozen=True)
class Profile:
    """One kind of opponent; every rate is a share of hands (DECISIONS 53)."""

    name: str
    open_raise: float
    limp: float
    iso_fold: float
    iso_reraise: float
    iso_slope: float
    behind_3bet: float
    behind_call: float
    sb_3bet: float
    sb_call: float
    bb_3bet: float
    bb_call: float
    behind_slope: float
    limp_raise: float
    overlimp: float
    sb_limp_raise: float
    sb_complete: float
    bb_limp_raise: float
    source: dict = field(default_factory=dict, compare=False)
    """Rate name -> "fitted" or "assumed"."""
    limp_range: str | None = None
    """A fixed limp range in place of the band below the open-raise range (tests)."""
    by_seat: dict = field(default_factory=dict, compare=False)
    """Hero seat -> rates that replace the profile's when the hero sits there (DECISIONS 54)."""
    deal_name: str = ""
    """Seeds the deals in place of the name (DECISIONS 60: composed profiles, by limper type)."""

    def limp_weights(self) -> np.ndarray:
        if self.limp_range is not None:
            return from_text(self.limp_range)
        lo = 1.0 - self.open_raise - self.limp
        return from_classes(band(ALL_HANDS, lo, 1.0 - self.open_raise))

    def for_seat(self, seat: str) -> Profile:
        return replace(self, **self.by_seat.get(seat, {}))


RATES = (
    "open_raise",
    "limp",
    "iso_fold",
    "iso_reraise",
    "iso_slope",
    "behind_3bet",
    "behind_call",
    "sb_3bet",
    "sb_call",
    "bb_3bet",
    "bb_call",
    "behind_slope",
    "limp_raise",
    "overlimp",
    "sb_limp_raise",
    "sb_complete",
    "bb_limp_raise",
)


BB_CHART = {
    # Hero seat: the midpoints of the BB's (flat, 3-bet) ranges against a 2.5x open, from
    # VIP-Grinders' "Big blind defense" (2026-06-15), fitted in DECISIONS 54's amendment.
    "UTG": (0.225, 0.05),
    "HJ": (0.28, 0.07),
    "CO": (0.35, 0.09),
    "BTN": (0.43, 0.12),
    "SB": (0.44, 0.145),
}
CHART_SIZE = 2.5
ASSUMED_DEFENCE = {
    # Hero seat: (SB call, SB 3-bet), (others call, others 3-bet). Not on the page, so
    # assumed from published 100 bb six-max solver frequencies (DECISIONS 54).
    "UTG": ((0.00, 0.08), (0.04, 0.07)),
    "HJ": ((0.00, 0.09), (0.04, 0.07)),
    "CO": ((0.00, 0.11), (0.04, 0.07)),
    "BTN": ((0.03, 0.14), (0.04, 0.07)),
    "SB": ((0.00, 0.00), (0.04, 0.07)),
}
BB_RATES = ("bb_call", "bb_3bet")
DEFENCE_RATES = (*BB_RATES, "sb_call", "sb_3bet", "behind_call", "behind_3bet")
LIMPER_RATES = ("open_raise", "limp", "iso_fold", "iso_reraise", "iso_slope")


def standard(regular: Profile, limpers: Profile) -> Profile:
    """The regular profile, with players behind defending like a modern chart (the BB
    fitted to VIP-Grinders' table, moved to the 3 bb reference by the fitted slope) and
    the limpers' own rates taken from `limpers` (DECISIONS 57: loose-passive)."""
    shift = regular.behind_slope * (3.0 - CHART_SIZE)
    by_seat = {}
    for seat, (flat, three_bet) in BB_CHART.items():
        (sb_call, sb_3bet), (others_call, others_3bet) = ASSUMED_DEFENCE[seat]
        values = (flat - shift, three_bet, sb_call, sb_3bet, others_call, others_3bet)
        by_seat[seat] = dict(zip(DEFENCE_RATES, values, strict=True))
    source = regular.source | dict.fromkeys(DEFENCE_RATES, "assumed")
    source |= dict.fromkeys(BB_RATES, "fitted")
    if limpers is not regular:
        source |= dict.fromkeys(LIMPER_RATES, f"fitted, {limpers.name}")
    rates = {r: getattr(limpers, r) for r in LIMPER_RATES}
    return replace(regular, name="standard", source=source, by_seat=by_seat, **rates)


def load_profiles(
    path: str | Path = PROFILES_PATH, *, standard_limpers: str = "loose-passive"
) -> dict[str, Profile]:
    """The three fitted profiles (DECISIONS 53) and "standard" (DECISIONS 54, 57)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {
        name: Profile(name=name, source=p["source"], **p["rates"])
        for name, p in data["profiles"].items()
    }
    out["standard"] = standard(out["regular"], out[standard_limpers])
    return out


# --- player types (DECISIONS 60) ------------------------------------------------

TYPES_PATH = ROOT / "data" / "sixmax_types.json"
TYPE_KEYS = ("standard", "nit", "tag", "lag", "maniac", "weak-tight", "station")
TABLE_RATES = tuple(r for r in RATES if r not in LIMPER_RATES)
CAPS = (  # (raise share, the share that continues without raising)
    ("behind_3bet", "behind_call"),
    ("sb_3bet", "sb_call"),
    ("bb_3bet", "bb_call"),
    ("limp_raise", "overlimp"),
    ("sb_limp_raise", "sb_complete"),
)


@dataclass(frozen=True)
class PlayerType:
    key: str
    name: str
    rates: dict = field(default_factory=dict)
    """The group's fitted 2009 rates (the pooled one where the group is thin)."""
    source: dict = field(default_factory=dict)
    ratio: dict = field(default_factory=dict)
    """Rate -> the type's rate over the pooled "all" rate; empty (all 1) for standard."""
    card: dict = field(default_factory=dict)
    players: int = 0


def load_types(path: str | Path = TYPES_PATH) -> dict[str, PlayerType]:
    """ "standard" and the six fitted types, in `TYPE_KEYS` order."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))["types"]
    pool = data["all"]["rates"]
    out = {"standard": PlayerType("standard", "Standard")}
    for key in TYPE_KEYS[1:]:
        t = data[key]
        rates = dict(t["rates"])
        ratio = {r: rates[r] / pool[r] if pool[r] else 1.0 for r in pool}
        pool_defend = pool["bb_call"] + pool["bb_3bet"]
        ratio["bb_defend"] = (rates["bb_call"] + rates["bb_3bet"]) / pool_defend
        out[key] = PlayerType(key, t["name"], rates, t["source"], ratio, t["card"], t["players"])
    return out


def _scale(rates: dict, ratio: dict) -> dict:
    """Each rate times its ratio, clipped so that every action's shares stay valid."""
    out = {r: v * ratio.get(r, 1.0) for r, v in rates.items()}
    for t, c in CAPS:
        if t in out:
            out[t] = min(1.0, out[t])
        if c in out:
            out[c] = min(1.0 - out.get(t, 0.0), out[c])
    if "bb_limp_raise" in out:
        out["bb_limp_raise"] = min(1.0, out["bb_limp_raise"])
    return out


def compose(
    limpers: str,
    table: str,
    *,
    profiles: dict[str, Profile] | None = None,
    types: dict[str, PlayerType] | None = None,
) -> Profile:
    """A spot's opponents: limper rates from the limper type, the others standard's times
    the table type's ratios (DECISIONS 60). Standard and standard is the standard profile."""
    std = (profiles or load_profiles())["standard"]
    if limpers == table == "standard":
        return std
    types = types or load_types()
    lim, tab = types[limpers], types[table]
    rates = _scale({r: getattr(std, r) for r in TABLE_RATES}, tab.ratio)
    by_seat = {seat: _scale(v, tab.ratio) for seat, v in std.by_seat.items()}
    source = dict(std.source)
    if table != "standard":
        source |= {r: f"{std.source.get(r, 'fitted')} × {tab.name}" for r in TABLE_RATES}
    if limpers != "standard":
        rates |= {r: lim.rates[r] for r in LIMPER_RATES}
        source |= {r: f"{lim.source.get(r, 'fitted')}, {lim.name}" for r in LIMPER_RATES}
    return replace(
        std,
        name=f"{lim.name} limpers, {tab.name} table",
        deal_name="standard" if limpers == "standard" else f"{limpers} limpers",
        source=source,
        by_seat=by_seat,
        **rates,
    )


def type_card(t: PlayerType) -> str:
    """The trait card: the group's fitted numbers (DECISIONS 60)."""
    if t.key == "standard":
        return (
            "Standard: blinds defend like a modern 100 bb chart; limpers are loose-passive "
            "(DECISIONS 54, 57)"
        )
    c = {k: "-" if v is None else f"{v:.0%}" for k, v in t.card.items()}
    return (
        f"{t.name} ({t.players:,} players, 2009 online): VPIP {c['vpip']}, PFR {c['pfr']}, "
        f"limps {c['limp']}, folds to an iso {c['iso_fold']}, 3-bets {c['three_bet']}, "
        f"BB defends {c['bb_defence']}"
    )


# --- spots and deals ------------------------------------------------------------


@dataclass(frozen=True)
class Spot:
    seat: str
    limpers: int = 0
    ante: float = 0.0

    def __post_init__(self) -> None:
        if self.seat not in SEATS:
            raise ValueError(f"seat must be one of {', '.join(SEATS)}")
        if not 0 <= self.limpers <= MAX_LIMPERS[self.seat]:
            raise ValueError(f"{self.seat} can have 0 to {MAX_LIMPERS[self.seat]} limpers ahead")
        if self.seat == "BB" and self.limpers == 0:
            raise ValueError("the BB with no limpers is a walk, not a decision")
        if self.ante < 0:
            raise ValueError("the ante must be at least 0")

    @property
    def posted(self) -> float:
        return BLINDS.get(self.seat, 0.0)

    @property
    def sizes(self) -> tuple[float, ...]:
        k = self.limpers
        return (2.5, 3.0, 4.0) if k == 0 else (3.0 + k, 4.0 + k, 5.0 + k)

    @property
    def pot(self) -> float:
        """Everything in before the hero acts."""
        return 6 * self.ante + 1.5 + self.limpers

    @property
    def dead(self) -> float:
        """Antes, and the SB's blind when it folded before a BB hero."""
        return 6 * self.ante + (0.5 if self.seat == "BB" else 0.0)

    def opponents(self) -> list[tuple[str, str]]:
        """(kind, seat) in the order they act after the hero: players behind, then limpers."""
        hero = SEATS.index(self.seat)
        behind = [(s if s in BLINDS else "behind", s) for s in SEATS[hero + 1 :]]
        ahead = [s for s in SEATS[:hero] if s not in BLINDS]
        limpers = [("limper", s) for s in ahead[len(ahead) - self.limpers :]]
        return behind + limpers

    def action_names(self) -> list[str]:
        if self.seat == "BB":
            names = ["check"]
        else:
            limp = {"SB": "complete"}.get(self.seat, "limp" if self.limpers == 0 else "overlimp")
            names = ["fold", limp]
        verb = "open" if self.limpers == 0 else ("raise" if self.seat == "BB" else "iso")
        return names + [f"{verb} to {x:g}" for x in self.sizes]

    @property
    def defence_seat(self) -> str:
        """The raiser's seat that players behind defend against: the hero's."""
        return self.seat

    @property
    def key_extra(self) -> tuple[int, ...]:
        return ()


# --- facing one open raise (DECISIONS 61) ---------------------------------------------

OPEN_WIDTH = {"UTG": 0.15, "HJ": 0.19, "CO": 0.27, "BTN": 0.45, "SB": 0.40}
"""Assumed modern 100 bb open widths by seat, times the opener type's open-raise ratio."""
OPEN_SIZES = (2.5, 3.0)
OPENER_4BET, OPENER_CALL = 0.12, 0.33
"""Standard's opener facing a 3-bet, as shares of its open range (assumed)."""
COLD_4BET = 0.02
"""Players behind 4-bet a 3-bet, or call a jam, with their top 2% and fold the rest."""


@dataclass(frozen=True)
class Opener:
    seat: str
    kind: str
    """The player type's key."""
    width: float
    four_bet: float
    call: float
    slope: float
    """The fall in its call share per bb of 3-bet above 3× the open."""
    fixed: str | None = None
    """A fixed open range in place of the top `width` (tests)."""

    def weights(self) -> np.ndarray:
        if self.fixed is not None:
            return from_text(self.fixed)
        return from_classes(top(ALL_HANDS, self.width))


def opener(
    seat: str,
    kind: str = "standard",
    *,
    profiles: dict[str, Profile] | None = None,
    types: dict[str, PlayerType] | None = None,
) -> Opener:
    if seat not in OPEN_WIDTH:
        raise ValueError(f"the opener is one of {', '.join(OPEN_WIDTH)}")
    ratio = {} if kind == "standard" else (types or load_types())[kind].ratio
    four_bet = min(1.0, OPENER_4BET * ratio.get("opener_4bet", 1.0))
    call = min(1.0 - four_bet, OPENER_CALL * ratio.get("opener_call", 1.0))
    width = min(1.0, OPEN_WIDTH[seat] * ratio.get("open_raise", 1.0))
    slope = (profiles or load_profiles())["standard"].behind_slope
    return Opener(seat, kind, width, four_bet, call, slope)


@dataclass(frozen=True)
class OpenSpot:
    """The hero facing one open raise; everyone between folded, no limpers."""

    seat: str
    opener: Opener
    size: float = 2.5
    ante: float = 0.0

    def __post_init__(self) -> None:
        if self.seat not in SEATS or SEATS.index(self.seat) <= SEATS.index(self.opener.seat):
            raise ValueError(f"the hero sits after the opener ({self.opener.seat})")
        if self.size not in OPEN_SIZES:
            raise ValueError("the open is 2.5 or 3 bb")
        if self.ante < 0:
            raise ValueError("the ante must be at least 0")

    limpers = 0

    @property
    def posted(self) -> float:
        return BLINDS.get(self.seat, 0.0)

    @property
    def sizes(self) -> tuple[float, ...]:
        """The 3-bets: 3× and 4× the open."""
        return (3 * self.size, 4 * self.size)

    @property
    def pot(self) -> float:
        return 6 * self.ante + 1.5 + self.size - (0.5 if self.opener.seat == "SB" else 0.0)

    @property
    def dead(self) -> float:
        """Antes, and the SB's blind when it folded before a BB hero."""
        sb_folded = self.seat == "BB" and self.opener.seat != "SB"
        return 6 * self.ante + (0.5 if sb_folded else 0.0)

    @property
    def defence_seat(self) -> str:
        return self.opener.seat

    @property
    def key_extra(self) -> tuple[int, ...]:
        return (10 + SEATS.index(self.opener.seat), zlib.crc32(self.opener.kind.encode()))

    def opponents(self) -> list[tuple[str, str]]:
        """Players behind in seat order, then the opener: the order they act after the hero."""
        hero = SEATS.index(self.seat)
        behind = [(s if s in BLINDS else "behind", s) for s in SEATS[hero + 1 :]]
        return behind + [("opener", self.opener.seat)]

    def action_names(self) -> list[str]:
        return ["fold", "call", *(f"3-bet to {x:g}" for x in self.sizes), "jam"]


@dataclass
class Deal:
    """Opponents' hands and boards for one spot, shared by all hero hands and actions."""

    spot: Spot
    profile: Profile
    kinds: list[str]
    seats: list[str]
    combos: np.ndarray  # (n, m) combo index
    q: np.ndarray  # (n, m) place in the player's own range, 0 weakest
    ranks: np.ndarray  # (n, m) 7-card strength on the board
    dead: np.ndarray  # (n, 52) cards dealt to opponents or the board
    boards: list  # n lists of 5 eval7 cards
    rng: np.random.Generator


def _deal_hands(weights: list[np.ndarray], n: int, rng: np.random.Generator) -> np.ndarray:
    """(n, m) combo indices, each tuple redrawn whole until no two hands share a card."""
    m = len(weights)
    out = np.empty((n, m), dtype=np.int64)
    todo = np.arange(n)
    probs = [w / w.sum() for w in weights]
    while todo.size:
        for o in range(m):
            out[todo, o] = rng.choice(len(ALL_COMBOS), size=todo.size, p=probs[o])
        cards = np.sort(COMBO_CARDS[out[todo]].reshape(todo.size, 2 * m), axis=1)
        todo = todo[(np.diff(cards, axis=1) == 0).any(axis=1)]
    return out


def deal(spot: Spot | OpenSpot, profile: Profile, *, samples: int = SAMPLES, seed: int = 0) -> Deal:
    profile = profile.for_seat(spot.defence_seat)
    name = profile.deal_name or profile.name
    key = [seed, SEATS.index(spot.seat), spot.limpers, zlib.crc32(name.encode())]
    rng = np.random.default_rng(key + list(spot.key_extra))
    kinds, seats = zip(*spot.opponents(), strict=True)
    limp_w = profile.limp_weights()
    special = {"limper": limp_w}
    if isinstance(spot, OpenSpot):
        special["opener"] = spot.opener.weights()
    weights = [special.get(k, ALL_HANDS) for k in kinds]
    combos = _deal_hands(weights, samples, rng)
    m = len(kinds)
    q = np.empty((samples, m))
    for o, w in enumerate(weights):
        low, high = _bounds(w)
        cls = COMBO_CLASS[combos[:, o]]
        q[:, o] = low[cls] + rng.random(samples) * (high[cls] - low[cls])
    dead = np.zeros((samples, 52), dtype=bool)
    hole = COMBO_CARDS[combos].reshape(samples, 2 * m)
    np.put_along_axis(dead, hole, True, axis=1)
    keys = rng.random((samples, 52)) + dead
    board = np.argpartition(keys, 5, axis=1)[:, :5]
    np.put_along_axis(dead, board, True, axis=1)
    E = EVAL7_CARDS
    boards = [[E[c] for c in row] for row in board.tolist()]
    ranks = np.empty((samples, m), dtype=np.int64)
    for s, (row, b) in enumerate(zip(hole.tolist(), boards, strict=True)):
        for o in range(m):
            ranks[s, o] = evaluate_eval7([E[row[2 * o]], E[row[2 * o + 1]], *b])
    return Deal(spot, profile, list(kinds), list(seats), combos, q, ranks, dead, boards, rng)


# --- what the opponents do ------------------------------------------------------


@dataclass
class Outcome:
    """One hero action under one fold shift; nothing here depends on the hero's hand."""

    name: str
    cost: float  # chips the hero adds
    reraiser: np.ndarray  # (n,) opponent index of the re-raise the hero faces, -1 for none
    raised_behind: np.ndarray  # (n,) a raise behind the hero's limp (the hero folds)
    pot: np.ndarray  # (n,) pot if the hand goes on without a re-raise
    allin_pot: np.ndarray  # (n,) pot if the hero stacks off against the re-raise
    callers: np.ndarray  # (n, m) still in at the flop
    r: np.ndarray  # (n,) the hero's R at the flop
    rr_ranges: list | None = None
    """Per opponent, the class weights it re-raises (or calls an all-in) with here, when they
    differ from `reraise_equities`' (facing an open, DECISIONS 61)."""
    allin: bool = False
    """The hero is all-in: there is no folding to a re-raise."""
    # Filled by `_finish` from the fields above:
    went_on: np.ndarray = None  # (n,) reached the flop with at least one opponent
    won: np.ndarray = None  # (n,) everyone folded to the hero
    count: np.ndarray = None  # (n,) opponents at the flop
    villain: np.ndarray = None  # (n,) the class of the one opponent left, when there is one
    best: np.ndarray = None  # (n,) the best opponent strength at the flop
    ties: np.ndarray = None  # (n,) opponents holding that strength
    rr_villain: np.ndarray = None  # (n,) the re-raiser's class


def _finish(d: Deal, o: Outcome) -> Outcome:
    n = len(o.pot)
    rows = np.arange(n)
    to_flop = ~o.raised_behind & (o.reraiser < 0)
    o.count = o.callers.sum(axis=1)
    o.went_on = (o.count > 0) & to_flop
    o.won = (o.count == 0) & to_flop
    o.villain = COMBO_CLASS[d.combos[rows, o.callers.argmax(axis=1)]]
    ranks = np.where(o.callers, d.ranks, -1)
    o.best = ranks.max(axis=1)
    o.ties = (ranks == o.best[:, None]).sum(axis=1)
    o.rr_villain = COMBO_CLASS[d.combos[rows, np.maximum(o.reraiser, 0)]]
    return o


def _prior(kind: str) -> float:
    return {"limper": 1.0, "SB": 0.5, "BB": 1.0}.get(kind, 0.0)


def raise_outcome(d: Deal, x: float, delta: float) -> Outcome:
    spot, p = d.spot, d.profile
    x_ref = spot.sizes[1]
    n, m = d.q.shape
    reraise = np.zeros((n, m), dtype=bool)
    call = np.zeros((n, m), dtype=bool)
    for o, kind in enumerate(d.kinds):
        q = d.q[:, o]
        if kind == "limper":
            r = p.iso_reraise
            f = min(1.0 - r, max(0.0, p.iso_fold + p.iso_slope * (x - x_ref) + delta))
            reraise[:, o] = q >= 1.0 - r
            call[:, o] = (q >= f) & ~reraise[:, o]
        else:
            t, c = {
                "behind": (p.behind_3bet, p.behind_call),
                "SB": (p.sb_3bet, p.sb_call),
                "BB": (p.bb_3bet, p.bb_call),
            }[kind]
            c = min(1.0 - t, max(0.0, c - p.behind_slope * (x - x_ref) - delta))
            reraise[:, o] = q >= 1.0 - t
            call[:, o] = (q >= 1.0 - t - c) & ~reraise[:, o]
    first = np.where(reraise.any(axis=1), reraise.argmax(axis=1), -1)
    prior = np.array([_prior(k) for k in d.kinds])
    before = np.arange(m)[None, :] < first[:, None]
    # Against a re-raise, callers before it leave X in; everyone else leaves their posts.
    dead = np.where(call & before, x, prior[None, :])
    rr = first >= 0
    dead_total = dead.sum(axis=1) - np.where(rr, prior[np.maximum(first, 0)], 0.0)
    allin_pot = 2 * (STACK - spot.ante) + spot.dead + dead_total
    callers = call & ~rr[:, None]
    pot = spot.dead + x + np.where(callers, x, prior[None, :]).sum(axis=1)
    outcome = Outcome(
        name="",
        cost=x - spot.posted,
        reraiser=first,
        raised_behind=np.zeros(n, dtype=bool),
        pot=pot,
        allin_pot=allin_pot,
        callers=callers,
        r=_r(d, callers, "raise"),
    )
    return _finish(d, outcome)


def limp_outcome(d: Deal) -> Outcome:
    spot, p = d.spot, d.profile
    n, m = d.q.shape
    raised = np.zeros(n, dtype=bool)
    stay = np.zeros((n, m), dtype=bool)
    for o, kind in enumerate(d.kinds):
        q = d.q[:, o]
        if kind == "limper":
            stay[:, o] = True
            continue
        x, c = {
            "behind": (p.limp_raise, p.overlimp),
            "SB": (p.sb_limp_raise, p.sb_complete),
            "BB": (p.bb_limp_raise, 1.0),
        }[kind]
        raised |= q >= 1.0 - x
        stay[:, o] = q >= 1.0 - x - c
    prior = np.array([_prior(k) for k in d.kinds])
    pot = spot.dead + 1.0 + np.where(stay, 1.0, prior[None, :]).sum(axis=1)
    callers = stay & ~raised[:, None]
    outcome = Outcome(
        name="",
        cost=1.0 - spot.posted,
        reraiser=np.full(n, -1),
        raised_behind=raised,
        pot=pot,
        allin_pot=np.zeros(n),
        callers=callers,
        r=_r(d, callers, "limp"),
    )
    return _finish(d, outcome)


def _r(d: Deal, callers: np.ndarray, pot: str) -> np.ndarray:
    hero = POSTFLOP[d.spot.seat]
    after = np.array([POSTFLOP[s] > hero for s in d.seats])
    oop = (callers & after[None, :]).any(axis=1)
    return np.where(oop, R[f"{pot}_oop"], R[f"{pot}_ip"])


def _behind(p: Profile, kind: str) -> tuple[float, float]:
    """A player behind's (3-bet, call) shares against an open, by its kind."""
    return {
        "behind": (p.behind_3bet, p.behind_call),
        "SB": (p.sb_3bet, p.sb_call),
        "BB": (p.bb_3bet, p.bb_call),
    }[kind]


def _first(reraise: np.ndarray) -> np.ndarray:
    return np.where(reraise.any(axis=1), reraise.argmax(axis=1), -1)


def _open_prior(d: Deal) -> np.ndarray:
    """Chips each opponent has in before the hero acts: the blinds' posts, the open."""
    return np.array([d.spot.size if k == "opener" else _prior(k) for k in d.kinds])


def open_call_outcome(d: Deal, delta: float, squeeze: list) -> Outcome:
    """The hero calls: players behind squeeze, overcall or fold; the opener stays in."""
    spot, p = d.spot, d.profile
    n, m = d.q.shape
    size = spot.size
    reraise = np.zeros((n, m), dtype=bool)
    call = np.zeros((n, m), dtype=bool)
    for o, kind in enumerate(d.kinds):
        if kind == "opener":
            call[:, o] = True
            continue
        t, c = _behind(p, kind)
        c = min(1.0 - t, max(0.0, c - p.behind_slope * (size - 3.0) - delta))
        reraise[:, o] = d.q[:, o] >= 1.0 - t
        call[:, o] = (d.q[:, o] >= 1.0 - t - c) & ~reraise[:, o]
    first = _first(reraise)
    prior = _open_prior(d)
    before = np.arange(m)[None, :] < first[:, None]
    dead = np.where(call & before, size, prior[None, :])
    rr = first >= 0
    dead_total = dead.sum(axis=1) - np.where(rr, prior[np.maximum(first, 0)], 0.0)
    callers = call & ~rr[:, None]
    pot = spot.dead + size + np.where(callers, size, prior[None, :]).sum(axis=1)
    outcome = Outcome(
        name="",
        cost=size - spot.posted,
        reraiser=first,
        raised_behind=np.zeros(n, dtype=bool),
        pot=pot,
        allin_pot=2 * (STACK - spot.ante) + spot.dead + dead_total,
        callers=callers,
        r=_r(d, callers, "limp"),
        rr_ranges=squeeze,
    )
    return _finish(d, outcome)


def open_raise_outcome(d: Deal, x: float | None, delta: float, ranges: list) -> Outcome:
    """The hero 3-bets to x, or jams (x None). Players behind cold 4-bet (or call the jam)
    with their top 2%; then the opener 4-bets, calls or folds (it calls a jam with its
    4-bet range)."""
    spot, op = d.spot, d.spot.opener
    n, m = d.q.shape
    reraise = np.zeros((n, m), dtype=bool)
    opener_calls = np.zeros(n, dtype=bool)
    for o, kind in enumerate(d.kinds):
        q = d.q[:, o]
        if kind != "opener":
            reraise[:, o] = q >= 1.0 - COLD_4BET
            continue
        reraise[:, o] = q >= 1.0 - op.four_bet
        if x is not None:
            c = min(1.0 - op.four_bet, max(0.0, op.call - op.slope * (x - 3 * spot.size) - delta))
            opener_calls = (q >= 1.0 - op.four_bet - c) & ~reraise[:, o]
    first = _first(reraise)
    rr = first >= 0
    prior = _open_prior(d)
    opener = d.kinds.index("opener")
    callers = np.zeros((n, m), dtype=bool)
    callers[:, opener] = opener_calls & ~rr
    allin_pot = 2 * (STACK - spot.ante) + spot.dead + prior.sum() - prior[np.maximum(first, 0)]
    to = STACK - spot.ante if x is None else x
    pot = spot.dead + to + np.where(callers, to, prior[None, :]).sum(axis=1)
    outcome = Outcome(
        name="",
        cost=to - spot.posted,
        reraiser=first,
        raised_behind=np.zeros(n, dtype=bool),
        pot=pot,
        allin_pot=np.where(rr, allin_pot, 0.0),
        callers=callers,
        r=_r(d, callers, "raise"),
        rr_ranges=ranges,
        allin=x is None,
    )
    return _finish(d, outcome)


def open_outcome_table(d: Deal) -> dict[float, list[Outcome]]:
    spot, p = d.spot, d.profile
    op = spot.opener
    open_w = op.weights()
    squeeze = [None if k == "opener" else top(ALL_HANDS, _behind(p, k)[0]) for k in d.kinds]
    over = [
        top(open_w, op.four_bet) if k == "opener" else top(ALL_HANDS, COLD_4BET) for k in d.kinds
    ]
    jam = open_raise_outcome(d, None, 0.0, over)
    table = {}
    for delta in FOLD_BAND:
        table[delta] = [
            open_call_outcome(d, delta, squeeze),
            *(open_raise_outcome(d, x, delta, over) for x in spot.sizes),
            jam,
        ]
        for o, name in zip(table[delta], spot.action_names()[1:], strict=True):
            o.name = name
    return table


def outcome_table(d: Deal) -> dict[float, list[Outcome]]:
    """Per fold shift, every action but fold, in `Spot.action_names` order. The limp is
    the same object at every shift: no fold rate applies to it."""
    if isinstance(d.spot, OpenSpot):
        return open_outcome_table(d)
    names = d.spot.action_names()
    if names[0] == "fold":
        names = names[1:]
    limp = limp_outcome(d)
    table = {}
    for delta in FOLD_BAND:
        table[delta] = [limp] + [raise_outcome(d, x, delta) for x in d.spot.sizes]
        for o, name in zip(table[delta], names, strict=True):
            o.name = name
    return table


# --- the hero's hand --------------------------------------------------------------


@dataclass
class Hero:
    cls: int
    weight: np.ndarray  # (n,) combos of the class that miss every dealt card
    rank: np.ndarray  # (n,) the drawn combo's 7-card strength
    combo: Combo  # a representative, for range equities


def hero_hand(d: Deal, hand: int | Combo) -> Hero:
    """A class index draws a combo per deal; an exact combo is used as it is."""
    combos = np.array([hand] if not isinstance(hand, int) else CLASS_COMBOS[hand])
    ok = ~d.dead[:, combos[:, 0]] & ~d.dead[:, combos[:, 1]]
    weight = ok.sum(axis=1).astype(float)
    pick = np.floor(d.rng.random(len(weight)) * weight).astype(np.int64)
    chosen = (np.cumsum(ok, axis=1) > pick[:, None]).argmax(axis=1)
    cards = combos[chosen].tolist()
    E = EVAL7_CARDS
    rank = np.array(
        [
            evaluate_eval7([E[a], E[b], *board])
            for (a, b), board in zip(cards, d.boards, strict=True)
        ]
    )
    cls = hand if isinstance(hand, int) else class_of(hand)
    return Hero(cls, weight, rank, (int(combos[0][0]), int(combos[0][1])))


def _share(hero: Hero, o: Outcome) -> np.ndarray:
    """The hero's pot share at the flop: exact heads-up, the board's showdown multiway."""
    heads_up = matrix().equity[hero.cls, o.villain]
    showdown = np.where(
        hero.rank > o.best, 1.0, np.where(hero.rank == o.best, 1.0 / (o.ties + 1), 0.0)
    )
    return np.where(o.count == 1, heads_up, showdown)


def reraise_equities(d: Deal, hero: Hero) -> np.ndarray:
    """Per opponent, the hero's exact equity against that player's re-raise range."""
    p = d.profile
    limp_w = p.limp_weights()
    out = []
    for kind in d.kinds:
        if kind == "limper":
            w = top(limp_w, p.iso_reraise)
        else:
            t = {"behind": p.behind_3bet, "SB": p.sb_3bet, "BB": p.bb_3bet}[kind]
            w = top(ALL_HANDS, t)
        out.append(jam_equity(hero.combo, w, matrix()) if w.sum() > 0 else 0.0)
    return np.array(out)


@dataclass
class Payoffs:
    """Per deal, an action's payoff at the base R, and its derivative in R."""

    base: np.ndarray
    slope: np.ndarray
    no_stackoff: np.ndarray


def payoffs(d: Deal, hero: Hero, o: Outcome, rr_eq: np.ndarray) -> Payoffs:
    flop_value = np.where(o.went_on, _share(hero, o) * o.pot, 0.0)
    base = np.where(o.won, o.pot, o.r * flop_value) - o.cost
    # A raise behind the limp loses the chips added: the limp EV is a floor.
    base = np.where(o.raised_behind, -o.cost, base)
    rr = o.reraiser >= 0
    no_stackoff = base
    if rr.any():
        stack_cost = STACK - d.spot.ante - d.spot.posted
        call = rr_eq[np.maximum(o.reraiser, 0)] * o.allin_pot - stack_cost > -o.cost
        called = matrix().equity[hero.cls, o.rr_villain] * o.allin_pot - stack_cost
        base = np.where(rr, np.where(call, called, -o.cost), base)
        no_stackoff = base if o.allin else np.where(rr, -o.cost, base)
    return Payoffs(base, flop_value, no_stackoff)


# --- answers --------------------------------------------------------------------


@dataclass
class Answer:
    hand: str
    actions: list[str]
    ev: np.ndarray  # base EV per action
    se: np.ndarray
    best: str
    runner_up: str
    gap_se: float  # the best's lead over the runner-up, in standard errors
    tier: str  # clear, close or review
    flips: list[tuple[float, float, str]]  # (R shift, fold shift, winner) where best loses
    no_stackoff_best: str


def _mean(w: np.ndarray, x: np.ndarray) -> float:
    return float((w * x).sum() / w.sum())


def _se(w: np.ndarray, x: np.ndarray) -> float:
    mean = _mean(w, x)
    return float(np.sqrt((w**2 * (x - mean) ** 2).sum()) / w.sum())


def evaluate(d: Deal, hand: int | Combo, table: dict[float, list[Outcome]]) -> Answer:
    """One hero hand against outcomes precomputed for each fold shift (`outcomes`)."""
    hero = hero_hand(d, hand)
    w = hero.weight
    if w.sum() == 0:
        raise ValueError("no deal leaves this hand possible")
    names = d.spot.action_names()
    has_fold = names[0] == "fold"
    done: dict[int, Payoffs] = {}
    rr_eqs: dict[int, np.ndarray] = {}

    def rr_for(o: Outcome) -> np.ndarray:
        key = id(o.rr_ranges)
        if key not in rr_eqs:
            if o.rr_ranges is None:
                rr_eqs[key] = reraise_equities(d, hero)
            else:
                rr_eqs[key] = np.array(
                    [
                        0.0 if w is None or w.sum() == 0 else jam_equity(hero.combo, w, matrix())
                        for w in o.rr_ranges
                    ]
                )
        return rr_eqs[key]

    def pay(o: Outcome) -> Payoffs:
        if id(o) not in done:
            done[id(o)] = payoffs(d, hero, o, rr_for(o))
        return done[id(o)]

    per_shift = {delta: [pay(o) for o in table[delta]] for delta in table}
    zero = np.zeros(len(w))

    def column(delta: float, attr: str) -> list[np.ndarray]:
        rows = [getattr(p, attr) for p in per_shift[delta]]
        return ([zero] if has_fold else []) + rows

    base = column(0.0, "base")
    ev = np.array([_mean(w, x) for x in base])
    se = np.array([_se(w, x) for x in base])
    order = np.argsort(-ev, kind="stable")
    best, second = int(order[0]), int(order[1])
    gap_se_value = _se(w, base[best] - base[second])
    gap = ev[best] - ev[second]
    no_noise = float("inf") if gap > 0 else 0.0
    gap_se = gap / gap_se_value if gap_se_value > 0 else no_noise

    flips = []
    for delta in FOLD_BAND:
        evs = np.array([_mean(w, x) for x in column(delta, "base")])
        slopes = np.array([_mean(w, x) for x in column(delta, "slope")])
        for shift in R_BAND:
            point = evs + shift * slopes
            winner = int(np.argmax(point))
            if point[winner] > point[best] + TIE:
                flips.append((shift, delta, names[winner]))
    no_stack = np.array([_mean(w, x) for x in column(0.0, "no_stackoff")])
    no_stack_best = names[int(np.argmax(no_stack))]
    if flips:
        tier = "close"
    elif gap_se < NOISE_SE or no_stack_best != names[best]:
        tier = "review"
    else:
        tier = "clear"
    label = CLASS_NAMES[hand] if isinstance(hand, int) else cards_str(hand)
    return Answer(
        label, names, ev, se, names[best], names[second], gap_se, tier, flips, no_stack_best
    )


def chart(spot: Spot, profile: Profile, *, samples: int = SAMPLES, seed: int = 0) -> list[Answer]:
    """Answers for all 169 classes, in class order."""
    d = deal(spot, profile, samples=samples, seed=seed)
    table = outcome_table(d)
    return [evaluate(d, i, table) for i in range(169)]


def parse_hand(text: str) -> int | Combo:
    """A class (A5s, 77, KQo) or an exact combo (As5s)."""
    if re.fullmatch(r"[2-9TJQKA]{2}[so]?", text.strip(), flags=re.IGNORECASE):
        return class_index(text.strip())
    cards = parse_cards(text)
    if len(cards) != 2:
        raise ValueError(f"expected a hand class like A5s or two cards like As5s, not {text!r}")
    return make_combo(*cards)


def answer(
    spot: Spot, profile: Profile, hand: int | Combo, *, samples: int = SAMPLES, seed: int = 0
) -> Answer:
    d = deal(spot, profile, samples=samples, seed=seed)
    return evaluate(d, hand, outcome_table(d))


# --- grades on GTO Wizard's scale (DECISIONS 60) ------------------------------------

LABELS = ("Best", "Correct", "Inaccuracy", "Wrong", "Blunder")
CUTS = ((3.0, "Correct"), (10.0, "Inaccuracy"), (25.0, "Wrong"))
"""The most EV lost, in % of the pot before acting, for each label below Best."""


@dataclass(frozen=True)
class Grade:
    label: str
    lost: float
    """bb behind the best action at the base point."""
    pct: float
    """`lost` as a % of the pot before acting."""


def grade_ev(
    ev: dict[str, float],
    best: str,
    action: str,
    pot: float,
    *,
    band_winners: set[str] | frozenset = frozenset(),
    size_only: bool = False,
) -> Grade:
    """Best: within TIE of the best, or of the best's kind when only the size is close.
    An action that wins at some band point is at least Correct. Otherwise by `CUTS`."""
    lost = float(ev[best] - ev[action])
    pct = 100.0 * lost / pot
    if lost <= TIE or (size_only and kind(action) == kind(best)):
        label = "Best"
    elif action in band_winners:
        label = "Correct"
    else:
        label = next((name for cut, name in CUTS if pct <= cut), "Blunder")
    return Grade(label, lost, pct)


def grade(a: Answer, action: str, pot: float) -> Grade:
    winners = {w for _, _, w in a.flips}
    size_only = bool(winners) and all(kind(w) == kind(a.best) for w in winners)
    ev = dict(zip(a.actions, (float(e) for e in a.ev), strict=True))
    return grade_ev(ev, a.best, action, pot, band_winners=winners, size_only=size_only)


def action_stats(d: Deal, hand: int | Combo, o: Outcome) -> dict[str, float]:
    """For one action at the base point: how often everyone folds, the hand goes on, it is
    re-raised or raised behind, and the hero's equity when it goes on. A private random
    stream picks the hero's combos, so `d` is not touched."""
    hero = hero_hand(replace(d, rng=np.random.default_rng(0)), hand)
    w = hero.weight / hero.weight.sum()
    went = (w * o.went_on).sum()
    share = (w * o.went_on * _share(hero, o)).sum()
    return {
        "fold_all": float((w * o.won).sum()),
        "went_on": float(went),
        "equity": float(share / went) if went > 0 else 0.0,
        "reraised": float((w * (o.reraiser >= 0)).sum()),
        "raised_behind": float((w * o.raised_behind).sum()),
    }


def why(d: Deal, table: dict[float, list[Outcome]], hand: int | Combo, a: Answer, action: str):
    """Deterministic lines from the engine's numbers: the best action, then the answer."""
    ev = dict(zip(a.actions, a.ev, strict=True))
    outcomes = {o.name: o for o in table[0.0]}
    pot = d.spot.pot
    lines = []
    for name in dict.fromkeys([a.best, action]):
        head = f"{name} {ev[name]:+.2f} bb"
        if name == "fold":
            lines.append(f"{head}: folding gives up nothing more.")
            continue
        s = action_stats(d, hand, outcomes[name])
        cost = outcomes[name].cost
        if name == "jam":
            lines.append(
                f"{head}: everyone folds {s['fold_all']:.0%} (you take the {pot:g} bb pot); "
                f"called {s['reraised']:.0%}, all in for {cost:g} bb."
            )
        elif name == "call":
            lines.append(
                f"{head}: you pay {cost:g} bb into {pot:g} ({cost / (cost + pot):.0%} of the "
                f"pot after you call); squeezed {s['reraised']:.0%} (you stack off or fold); "
                f"otherwise you see a flop with {s['equity']:.0%} equity."
            )
        elif kind(name) == "raise":
            lines.append(
                f"{head}: everyone folds {s['fold_all']:.0%} (you take the {pot:g} bb pot); "
                f"called {s['went_on']:.0%}, with {s['equity']:.0%} equity against the "
                f"callers; re-raised {s['reraised']:.0%}. You risk {cost:g} bb to win "
                f"{pot:g}, so a pure bluff needs {cost / (cost + pot):.0%} folds."
            )
        else:
            lines.append(
                f"{head}: someone raises behind {s['raised_behind']:.0%} (you fold, so the "
                f"limp EV is a floor); otherwise you see a flop with {s['equity']:.0%} "
                "equity."
            )
    return lines


# --- showing ranges ---------------------------------------------------------------


def range_text(class_weights: np.ndarray) -> str:
    """Classes at least half in the range, in short notation (22-77, A2s-A5s, KTs+)."""
    inside = {CLASS_NAMES[i] for i in np.flatnonzero(np.asarray(class_weights) >= 0.5)}
    if not inside:
        return "none"
    parts = []
    pairs = [r for r in range(12, -1, -1) if RANKS[r] * 2 in inside]
    parts += _runs(pairs, lambda r: RANKS[r] * 2, top=12)
    for shape in "so":
        for high in range(12, 0, -1):
            kickers = [
                k for k in range(high - 1, -1, -1) if f"{RANKS[high]}{RANKS[k]}{shape}" in inside
            ]
            parts += _runs(
                kickers, lambda k, h=high, s=shape: f"{RANKS[h]}{RANKS[k]}{s}", top=high - 1
            )
    return ", ".join(parts)


def _runs(ranks: list[int], name, *, top: int) -> list[str]:
    """Descending ranks grouped into runs: X+ when a run reaches the top, else lo-hi."""
    out = []
    i = 0
    while i < len(ranks):
        j = i
        while j + 1 < len(ranks) and ranks[j + 1] == ranks[j] - 1:
            j += 1
        hi, lo = ranks[i], ranks[j]
        if hi == top and lo != hi:
            out.append(name(lo) + "+")
        elif lo == hi:
            out.append(name(hi))
        else:
            out.append(f"{name(lo)}-{name(hi)}")
        i = j + 1
    return out


def share_of_hands(class_weights: np.ndarray) -> float:
    return float((np.asarray(class_weights) * CLASS_SIZES).sum() / len(ALL_COMBOS))


# --- text, for `showdown sixmax` and the drill trainer ------------------------------


def kind(action: str) -> str:
    """fold, limp (limp, overlimp, complete, check), call (facing an open) or raise (any
    raise, the jam included)."""
    if action in ("fold", "call"):
        return action
    return "raise" if " to " in action or action == "jam" else "limp"


def describe_spot(spot: Spot, p: Profile, hand: str) -> list[str]:
    """The spot, the profile, and its assumed ranges. `p` is already `for_seat`."""

    def pct(rate: str, value: float | None = None) -> str:
        v = getattr(p, rate) if value is None else value
        src = p.source.get(rate, "fitted")
        return f"{v:.0%}" + ("" if src == "fitted" else f" ({src})")

    def rng(weights) -> str:
        return f"{share_of_hands(weights):.1%} of hands: {range_text(weights)}"

    limpers = (
        f"{spot.limpers} limper{'s' * (spot.limpers != 1)} ahead" if spot.limpers else "unopened"
    )
    ante = f"ante {spot.ante:g} from everyone" if spot.ante else "no ante"
    if p.name == "standard":
        who = (
            "standard, one profile for the whole table: the regular profile, with players "
            "behind defending like a modern 100 bb chart and limpers from the loose-passive "
            "profile (DECISIONS 54, 57)"
        )
    elif p.name.endswith(" table"):
        who = (
            f"{p.name}: player types (DECISIONS 60). Limpers use their type's 2009 rates; "
            "everyone else plays standard's rates scaled by the table type (docs/sixmax-types.md)"
        )
    else:
        who = (
            f"{p.name}, one profile for the whole table: fitted to 2009 online 6-max hands "
            "(docs/sixmax-profiles.md)"
        )
    lines = [
        f"{spot.seat} with {hand}: {limpers}, 100 bb, blinds 0.5/1, {ante} ({spot.pot:g} bb in)",
        f"Opponents: {who}. Assumed, not measured on your players.",
        "",
        "Assumed ranges",
    ]
    x_ref = spot.sizes[1]
    kinds = [k for k, _ in spot.opponents()]
    if "limper" in kinds:
        limp = p.limp_weights()
        f = min(1 - p.iso_reraise, max(0.0, p.iso_fold))
        lines += [
            f"  Each limper: limp range {rng(band(limp, 0, 1 + 1e-12))}",
            f"    facing an iso to {x_ref:g} bb: fold {pct('iso_fold', f)}",
            f"      call: {rng(band(limp, f, 1 - p.iso_reraise))}",
            f"      re-raise ({pct('iso_reraise')} of the range): {rng(top(limp, p.iso_reraise))}",
        ]
    rates = {
        "behind": ("Each player behind", "behind_3bet", "behind_call"),
        "SB": ("SB", "sb_3bet", "sb_call"),
        "BB": ("BB", "bb_3bet", "bb_call"),
    }
    for who in ("behind", "SB", "BB"):
        if who not in kinds:
            continue
        label, t_rate, c_rate = rates[who]
        t, c = getattr(p, t_rate), getattr(p, c_rate)
        lines += [
            f"  {label}, facing a raise to {x_ref:g} bb:",
            f"    3-bet {pct(t_rate)}: {range_text(top(ALL_HANDS, t))}",
            f"    call {pct(c_rate)}: {range_text(band(ALL_HANDS, 1 - t - c, 1 - t))}",
        ]
    behind = []
    if "behind" in kinds:
        behind.append(f"each player behind raises {pct('limp_raise')}, overlimps {pct('overlimp')}")
    if "SB" in kinds:
        behind.append(f"SB raises {pct('sb_limp_raise')}, completes {pct('sb_complete')}")
    if "BB" in kinds:
        behind.append(f"BB raises {pct('bb_limp_raise')}")
    if behind:
        limp_name = next(n for n in spot.action_names() if kind(n) == "limp")
        lines.append(f"  Facing your {limp_name}: " + "; ".join(behind))
    lines.append(
        f"  Sizes move fold rates by {p.iso_slope:+.3f} (limpers) and {p.behind_slope:+.3f} "
        "(players behind) per bb away from the middle size."
    )
    return lines


def describe_open(spot: OpenSpot, p: Profile, hand: str, opener_name: str) -> list[str]:
    """The spot facing an open, the opener's range and answers, and the players behind.
    `p` is the table's profile, already `for_seat` the opener's seat."""
    op = spot.opener
    ante = f"ante {spot.ante:g} from everyone" if spot.ante else "no ante"
    open_w = op.weights()
    lines = [
        f"{spot.seat} with {hand}: {op.seat} opens to {spot.size:g} bb; 100 bb, blinds 0.5/1, "
        f"{ante} ({spot.pot:g} bb in)",
        f"Opener: {opener_name}. Players behind: {p.name}. Assumed, not measured on your "
        "players (DECISIONS 61).",
        "",
        "Assumed ranges",
        f"  The opener: {share_of_hands(class_mass(open_w) / CLASS_SIZES):.1%} of hands "
        f"({OPEN_WIDTH[op.seat]:.0%} assumed for {op.seat}, times its type's open ratio): "
        f"{range_text(class_mass(open_w) / CLASS_SIZES)}",
        f"    facing your 3-bet to {3 * spot.size:g}: 4-bets {op.four_bet:.0%} of its range "
        f"({range_text(top(open_w, op.four_bet))}), calls {op.call:.0%} (less "
        f"{op.slope:.3f} per bb above that size), folds the rest; it calls a jam with its "
        "4-bet range",
    ]
    for kind_, seat in spot.opponents()[:-1]:
        t, c = _behind(p, kind_)
        c = min(1.0 - t, max(0.0, c - p.behind_slope * (spot.size - 3.0)))
        lines.append(
            f"  {seat}, if you call: squeezes {t:.0%} "
            f"({range_text(top(ALL_HANDS, t))}), overcalls {c:.0%}; facing your 3-bet or jam, "
            f"continues with its top {COLD_4BET:.0%} only"
        )
    return lines


def band_note(a: Answer) -> list[str]:
    """The verdict, and where in the band another action wins."""
    lines = [
        f"Verdict: {a.tier.upper()}. Best: {a.best}. Runner-up: {a.runner_up} "
        f"({a.gap_se:.1f} standard errors behind)."
    ]
    if a.flips:
        winners = sorted({w for _, _, w in a.flips})
        for w in winners:
            where = [f"R {r:+.1f}/fold {d:+.0%}" for r, d, x in a.flips if x == w]
            lines.append(f"  {w} wins at " + ", ".join(where))
        if all(kind(w) == kind(a.best) for w in winners):
            lines.append(f"  Every band point picks a {kind(a.best)}: only the size is close.")
    if a.no_stackoff_best != a.best:
        lines.append(
            f"  Folding to every re-raise instead of stacking off, the best is {a.no_stackoff_best}."
        )
    return lines


def describe_answer(a: Answer, samples: int, seed: int) -> list[str]:
    """Each action's EV, the verdict, and why."""
    lines = [
        f"EV of each action, in bb against folding ({samples:,} deals, seed {seed})",
        f"  {'':12s} {'EV':>7s}  {'SE':>4s}",
    ]
    for name, ev, se in zip(a.actions, a.ev, a.se, strict=True):
        mark = "   best" if name == a.best else ""
        lines.append(f"  {name:12s} {ev:+7.2f}  {se:4.2f}{mark}")
    lines += ["", *band_note(a)]
    lines.append(
        "Band: every R moved 0.1 either way, fold-to-raise rates 10 points either way. "
        "The limp EV is a floor: a raise behind it is folded. Facing a re-raise, the hero "
        "stacks off or folds."
    )
    return lines
