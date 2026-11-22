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
R = {"raise_ip": 1.00, "raise_oop": 0.90, "limp_ip": 0.85, "limp_oop": 0.75}
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


STANDARD_DEFENCE = {
    # Hero seat: (BB call, BB 3-bet), (SB call, SB 3-bet), (others call, others 3-bet).
    # Assumed from published 100 bb six-max solver frequencies (DECISIONS 54).
    "UTG": ((0.24, 0.09), (0.00, 0.08), (0.04, 0.07)),
    "HJ": ((0.27, 0.10), (0.00, 0.09), (0.04, 0.07)),
    "CO": ((0.33, 0.11), (0.00, 0.11), (0.04, 0.07)),
    "BTN": ((0.44, 0.14), (0.03, 0.14), (0.04, 0.07)),
    "SB": ((0.50, 0.14), (0.00, 0.00), (0.04, 0.07)),
}
DEFENCE_RATES = ("bb_call", "bb_3bet", "sb_call", "sb_3bet", "behind_call", "behind_3bet")


def standard(regular: Profile) -> Profile:
    """The regular profile, with players behind defending like a modern chart."""
    by_seat = {
        seat: dict(zip(DEFENCE_RATES, (*bb, *sb, *others), strict=True))
        for seat, (bb, sb, others) in STANDARD_DEFENCE.items()
    }
    source = regular.source | dict.fromkeys(DEFENCE_RATES, "assumed")
    return replace(regular, name="standard", source=source, by_seat=by_seat)


def load_profiles(path: str | Path = PROFILES_PATH) -> dict[str, Profile]:
    """The three fitted profiles (DECISIONS 53) and "standard" (DECISIONS 54)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {
        name: Profile(name=name, source=p["source"], **p["rates"])
        for name, p in data["profiles"].items()
    }
    out["standard"] = standard(out["regular"])
    return out


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


def deal(spot: Spot, profile: Profile, *, samples: int = SAMPLES, seed: int = 0) -> Deal:
    profile = profile.for_seat(spot.seat)
    key = [seed, SEATS.index(spot.seat), spot.limpers, zlib.crc32(profile.name.encode())]
    rng = np.random.default_rng(key)
    kinds, seats = zip(*spot.opponents(), strict=True)
    limp_w = profile.limp_weights()
    weights = [limp_w if k == "limper" else ALL_HANDS for k in kinds]
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


def outcome_table(d: Deal) -> dict[float, list[Outcome]]:
    """Per fold shift, every action but fold, in `Spot.action_names` order. The limp is
    the same object at every shift: no fold rate applies to it."""
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
        no_stackoff = np.where(rr, -o.cost, base)
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
    rr_eq = reraise_equities(d, hero)
    names = d.spot.action_names()
    has_fold = names[0] == "fold"
    done: dict[int, Payoffs] = {}

    def pay(o: Outcome) -> Payoffs:
        if id(o) not in done:
            done[id(o)] = payoffs(d, hero, o, rr_eq)
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
