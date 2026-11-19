"""Live turn and river solves in the advice (DECISIONS 47).

At a turn or river decision in a replayed or tracked hand, the streets bridge solves the street
from the hand's real pot and stacks. Both ranges start as the preflop model's at the nearest
depth and are narrowed street by street: the flop by the stopgap's curves (DECISIONS 46), the
turn by the turn solve's own per-hand frequencies. The advice is the solved strategy for Ian's
hand at the node his line reached. The bridge runs as a separate process (DECISIONS 29).
"""

from __future__ import annotations

import itertools
import json
import re
import subprocess
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from showdown import preflop_model as pm
from showdown.equity.cards import ALL_COMBOS, Combo, card_str, cards_str
from showdown.live import narrow
from showdown.live.spot import threebet_size
from showdown.postflop import bridge
from showdown.postflop.spot import CHIPS_PER_BB, SETTINGS, TREE_T1

if TYPE_CHECKING:
    from showdown.live.advisor import Advisor
    from showdown.live.spot import Spot

STREETS_EXE = bridge.TARGET_DIR / "release" / "streets.exe"
TREE = {k: v for k, v in TREE_T1.items() if not k.startswith("flop")}
"""T1's turn and river sizes; the OOP keeps its turn bets after every flop line."""
TIMEOUT = {"turn": 6.0, "river": 3.0}
HERO_FLOOR = 0.001
MIN_COMBOS = 1.0
MAX_MOVES = 8
CACHE = 32
STREETS = ("preflop", "flop", "turn", "river")
SEATS = ("bb", "sb")
"""The solver's players: 0 is out of position (the BB), 1 in position (the SB)."""
LINES = {("raise", "call"): "srp", ("raise", "raise", "call"): "3bp"}
"""The preflop lines the model takes to a flop: an open and a call, a 3-bet and a call."""
SHOWN = {
    "Fold": "fold",
    "Check": "check",
    "Call": "call",
    "Bet": "bet",
    "Raise": "raise",
    "AllIn": "all-in",
}
SOURCE = "live solve"
KINDS = {"folds": "fold", "checks": "check", "calls": "call", "bets": "bet", "raises": "raise"}
SOLVER_INDEX = np.array([narrow.INDEX[(b, a)] for a, b in itertools.combinations(range(52), 2)])
"""For each combo in the solver's raw range order, its index in `ALL_COMBOS`."""
HAND_INDEX = {
    card_str(a) + card_str(b): narrow.INDEX[c] for c in ALL_COMBOS for a, b in (c, c[::-1])
}
_ACTION = re.compile(r"^(\w+)(?:\((\d+)\))?$")


class NoSolve(Exception):
    """Why no live solve answers a spot; the equity helper answers instead."""


def _paths() -> list[tuple[str, ...]]:
    """Every decision node a street's tree can have, by action labels (DECISIONS 47)."""
    out, frontier = [()], [()]
    while frontier:
        grown = []
        for path in frontier:
            last = path[-1] if path else None
            if last is None:
                options = ("Check", "Bet", "AllIn")
            elif last == "Check":
                options = ("Bet", "AllIn")
            elif last in ("Bet", "Raise"):
                options = ("Raise", "AllIn")
            else:
                options = ()
            grown += [(*path, o) for o in options if len(path) < MAX_MOVES]
        out += grown
        frontier = grown
    return out


REPORT = _paths()


# --- the hand so far ---------------------------------------------------------------------


@dataclass(frozen=True)
class Act:
    """One move on a street, with the real amounts before it, in bb."""

    seat: str
    kind: str
    """check, call, bet, raise or fold."""
    to_bb: float
    """The player's total on the street after the move."""
    allin: bool
    pot_bb: float
    """Everything in the middle before the move, this street's bets included."""
    own_bb: float
    to_call_bb: float

    @property
    def f(self) -> float:
        """DECISIONS 46's size: bet / pot, or (raise − to call) / (pot + to call)."""
        return (self.to_bb - self.own_bb - self.to_call_bb) / (self.pot_bb + self.to_call_bb)


@dataclass(frozen=True)
class StreetLine:
    pot_bb: float
    """Everything in the middle when the street starts."""
    put_bb: float
    """The most either player had put in when it started."""
    acts: tuple[Act, ...]
    bets_bb: dict[str, float]
    """Each player's total on the street after `acts`."""


def street_line(history: tuple[str, ...], street: str) -> StreetLine:
    """A street's start and its moves, rebuilt from the history (blinds 0.5 and 1 bb)."""
    target = STREETS.index(street)
    before, put = {"sb": 0.0, "bb": 0.0}, {"sb": 0.5, "bb": 1.0}
    current, acts = 0, []
    for text in history:
        m = narrow._MOVE.match(text)
        if not m:
            raise ValueError(f"unreadable move {text!r}")
        s = STREETS.index(m.group(1))
        if s > target:
            break
        while current < s:
            before = {k: before[k] + put[k] for k in put}
            put, current = {"sb": 0.0, "bb": 0.0}, current + 1
        me = m.group(2).lower()
        other = "bb" if me == "sb" else "sb"
        kind = KINDS[m.group(3).split()[0]]
        if kind == "call":
            to = put[me] + float(m.group(4))
        elif kind in ("bet", "raise"):
            to = float(m.group(5) or m.group(6))
        else:
            to = put[me]
        if s == target:
            pot = sum(before.values()) + put["sb"] + put["bb"]
            to_call = max(put[other] - put[me], 0.0)
            acts.append(Act(me, kind, to, bool(m.group(7)), pot, put[me], to_call))
        put[me] = to
    while current < target:
        before = {k: before[k] + put[k] for k in put}
        put, current = {"sb": 0.0, "bb": 0.0}, current + 1
    return StreetLine(sum(before.values()), max(before.values()), tuple(acts), dict(put))


@dataclass(frozen=True)
class Context:
    """What a spot's solves depend on."""

    hero: Combo
    seat: str
    effective_bb: float
    board: tuple[int, ...]
    history: tuple[str, ...]
    pot_type: str
    size: str | None = None
    """The re-solved model's 3-bet pot, "3x" or "4x" (DECISIONS 49); None otherwise."""

    def key(self, street: str) -> tuple:
        k = STREETS.index(street)
        before = tuple(h for h in self.history if STREETS.index(h.split(" ", 1)[0]) < k)
        cards = self.board[: narrow.STREET_CARDS[street]]
        return (
            street,
            self.hero,
            self.seat,
            self.effective_bb,
            cards,
            before,
            self.pot_type,
            self.size,
        )


# --- the solve -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Node:
    seat: str
    actions: tuple[tuple[str, int | None], ...]
    """(Fold, Check, Call, Bet, Raise or AllIn; its chips for the sized ones)."""
    index: np.ndarray
    """Each hand's place in `ALL_COMBOS`."""
    strategy: np.ndarray
    """Actions × hands."""

    @classmethod
    def read(cls, report: dict) -> Node:
        actions = []
        for text in report["actions"]:
            m = _ACTION.match(text)
            actions.append((m.group(1), int(m.group(2)) if m.group(2) else None))
        index = np.array([HAND_INDEX[h] for h in report["hands"]], dtype=int)
        strategy = np.asarray(report["strategy"], dtype=float).reshape(len(actions), len(index))
        return cls(SEATS[report["player"]], tuple(actions), index, strategy)

    def freq(self, a: int, floor: float = 0.0) -> np.ndarray:
        """Per combo in `ALL_COMBOS` order, how often it takes action `a` here, at least `floor`;
        0 off the range."""
        out = np.zeros(len(ALL_COMBOS))
        out[self.index] = np.maximum(self.strategy[a], floor)
        return out


@dataclass(frozen=True)
class Solved:
    street: str
    spec: dict
    nodes: dict[tuple[str, ...], Node]
    start: dict[str, np.ndarray]
    """Each seat's range at the street's start, in `ALL_COMBOS` order."""
    narrowed: tuple[str, ...]
    """How each earlier street was narrowed, for the label."""
    seconds: float
    exploitability_pct: float


@dataclass(frozen=True)
class Walk:
    path: tuple[str, ...]
    mult: dict[str, np.ndarray]
    """Per seat, the product of its floored frequencies of its moves along the line."""
    bets: dict[str, int]
    """Each player's chips bet on the street in the tree."""
    notes: tuple[str, ...]


def _tree_f(chips: int, seat: str, pot: int, bets: dict[str, int]) -> float:
    other = "bb" if seat == "sb" else "sb"
    own, call = bets[seat], max(bets[other] - bets[seat], 0)
    middle = pot + bets["sb"] + bets["bb"]
    return (chips - own - call) / (middle + call)


def _match(act: Act, node: Node, pot: int, bets: dict[str, int], street: str) -> tuple[int, str]:
    """The tree action a real move maps to, and a note when its size was off the tree."""
    names = [n for n, _ in node.actions]
    left = NoSolve(f"the {street} line left the solved tree")
    if act.kind in ("check", "call", "fold"):
        want = act.kind.capitalize()
        if want not in names:
            raise left
        return names.index(want), ""
    sized = [i for i, (_, chips) in enumerate(node.actions) if chips is not None]
    if not sized:
        raise left
    if act.allin and "AllIn" in names:
        return names.index("AllIn"), ""
    fs = {i: _tree_f(node.actions[i][1], act.seat, pot, bets) for i in sized}
    a = min(sized, key=lambda i: abs(fs[i] - act.f))
    if abs(node.actions[a][1] - act.to_bb * CHIPS_PER_BB) <= 1:
        return a, ""
    tree = "all-in" if names[a] == "AllIn" else f"{fs[a]:.0%} {names[a].lower()}"
    note = (
        f"{act.seat.upper()}'s {street} {act.kind} to {act.to_bb:g} bb ({act.f:.0%} of the pot) "
        f"solved as the tree's {tree}"
    )
    return a, note


def walk(solved: Solved, line: StreetLine) -> Walk:
    """Map the street's real moves onto the solved tree, narrowing each mover's range.

    Each move's multiplier is max(the solver's frequency, the floor): DECISIONS 46's 0.25 for
    a check and 0.10 otherwise (DECISIONS 47's amendment), since friends mix and misplay.
    """
    path, bets, notes = (), {"sb": 0, "bb": 0}, []
    mult = {s: np.ones(len(ALL_COMBOS)) for s in SEATS}
    pot = solved.spec["starting_pot"]
    for act in line.acts:
        node = solved.nodes.get(path)
        if node is None or node.seat != act.seat:
            raise NoSolve(f"the {solved.street} line left the solved tree")
        a, note = _match(act, node, pot, bets, solved.street)
        if note:
            notes.append(note)
        name, chips = node.actions[a]
        floor = narrow.FLOORS.get(name, narrow.FLOOR)
        mult[act.seat] = mult[act.seat] * node.freq(a, floor)
        other = "bb" if act.seat == "sb" else "sb"
        if name == "Call":
            bets[act.seat] = bets[other]
        elif chips is not None:
            bets[act.seat] = chips
        path = (*path, name)
    return Walk(path, mult, dict(bets), tuple(notes))


def run(spec: dict, timeout: float, street: str = "") -> dict:
    """One solve by the streets bridge, as a separate process."""
    try:
        proc = subprocess.run(
            [str(STREETS_EXE)],
            input=json.dumps(spec),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise NoSolve(f"the {street} solve timed out after {timeout:g} s") from None
    if proc.returncode != 0:
        raise NoSolve(f"the {street} solve failed: {proc.stderr.strip()[-200:]}")
    return json.loads(proc.stdout)


def _live_weight(w: np.ndarray, dead: tuple[int, ...]) -> float:
    return float(sum(x for c, x in zip(ALL_COMBOS, w, strict=True) if x and not set(c) & set(dead)))


# --- answers -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Answer:
    action: str
    size_bb: float | None
    mix: dict[str, float]
    villain: np.ndarray
    """The villain's range at the node, in `ALL_COMBOS` order."""
    notes: tuple[str, ...]
    source: str
    narrowed: str
    """How each street narrowed the ranges, for the range label."""
    spec: dict
    path: tuple[str, ...]


class LiveSolves:
    """An advisor's live solves, cached by their inputs and run in background threads."""

    def __init__(self, advisor: Advisor) -> None:
        self.advisor = advisor
        self._futures: dict[tuple, Future] = {}
        self._lock = threading.Lock()

    def context(self, spot: Spot) -> Context:
        """The spot's solve inputs; NoSolve says why no live solve answers it."""
        a = self.advisor
        if spot.street not in ("turn", "river"):
            raise NoSolve("only the turn and river are solved live")
        if not spot.history:
            raise NoSolve("no hand history")
        if a.ranges != "model":
            raise NoSolve("fixed ranges")
        if spot.has_villain_range:
            raise NoSolve("your range for the villain is used as given")
        acts = street_line(spot.history, "preflop").acts
        pot_type = LINES.get(tuple(x.kind for x in acts))
        if pot_type is None:
            raise NoSolve("the preflop line is not an open and a call, or a 3-bet and a call")
        size = None
        if a.resolved and pot_type == "3bp":  # the 3x or 4x line, by the ratio rule
            size = threebet_size(acts[1].to_bb, acts[0].to_bb)
        if any(a.model_range(pot_type, s, spot.effective_bb, size) is None for s in SEATS):
            depth = pm.PreflopModel.depth_for(spot.effective_bb) or pm.GRID[0]
            raise NoSolve(f"the model almost never reaches this pot at {depth:g} bb")
        if a.range_model() is None:
            raise NoSolve(f"{narrow.MODEL_PATH.name} is missing")
        if not STREETS_EXE.exists():
            raise NoSolve("the streets bridge is not built: run `showdown postflop build`")
        return Context(
            spot.hero, spot.seat, spot.effective_bb, spot.board, spot.history, pot_type, size
        )

    def _context(self, spot: Spot) -> Context | None:
        try:
            return self.context(spot)
        except NoSolve:
            return None

    def future(self, ctx: Context, street: str) -> Future:
        """The street's solve, started now if it was not already."""
        key = ctx.key(street)
        with self._lock:
            found = self._futures.get(key)
            if found is not None:
                return found
            fut = Future()
            self._futures[key] = fut
            for old in list(self._futures)[: max(len(self._futures) - CACHE, 0)]:
                if self._futures[old].done():
                    del self._futures[old]
        threading.Thread(target=self._run, args=(fut, ctx, street), daemon=True).start()
        return fut

    def _run(self, fut: Future, ctx: Context, street: str) -> None:
        if not fut.set_running_or_notify_cancel():
            return
        try:
            fut.set_result(self._solve(ctx, street))
        except BaseException as error:  # handed to whoever waits on the answer
            fut.set_exception(error)

    def prefetch(self, spot: Spot) -> None:
        """Start the spot's solve, if a live solve answers it (the tracker, at a new card)."""
        ctx = self._context(spot)
        if ctx is not None:
            self.future(ctx, spot.street)

    def started(self, spot: Spot) -> bool:
        ctx = self._context(spot)
        return ctx is not None and ctx.key(spot.street) in self._futures

    def pending(self, spot: Spot) -> bool:
        """True when a live solve answers the spot and has not finished yet."""
        ctx = self._context(spot)
        if ctx is None:
            return False
        fut = self._futures.get(ctx.key(spot.street))
        return fut is None or not fut.done()

    def _stopgap(self, w: np.ndarray, ctx: Context, seat: str, street: str) -> np.ndarray:
        weights, _, _ = narrow.narrow(
            self.advisor.range_model(),
            ALL_COMBOS,
            tuple(w),
            ctx.board,
            ctx.history,
            seat,
            ctx.pot_type,
            streets=(street,),
        )
        return np.array(weights)

    def _start(self, ctx: Context, street: str) -> tuple[dict[str, np.ndarray], tuple[str, ...]]:
        """Both ranges at the street's start, and how each earlier street narrowed them."""
        w = {}
        for seat in SEATS:
            found = self.advisor.model_range(ctx.pot_type, seat, ctx.effective_bb, ctx.size)
            w[seat] = np.zeros(len(ALL_COMBOS))
            w[seat][[narrow.INDEX[c] for c in found.combos]] = found.weights
            w[seat] = self._stopgap(w[seat], ctx, seat, "flop")
        narrowed = ["flop: range model (assumed)"]
        if street == "river":
            try:
                turn = self.future(ctx, "turn").result()
                walked = walk(turn, street_line(ctx.history, "turn"))
            except NoSolve as why:
                w = {s: self._stopgap(w[s], ctx, s, "turn") for s in SEATS}
                narrowed.append(f"turn: range model (assumed; {why})")
            else:
                w = {s: turn.start[s] * walked.mult[s] for s in SEATS}
                narrowed.append("turn: solved")
        hero = narrow.INDEX[ctx.hero]
        w[ctx.seat][hero] = max(w[ctx.seat][hero], HERO_FLOOR)
        return w, tuple(narrowed)

    def _solve(self, ctx: Context, street: str) -> Solved:
        w, narrowed = self._start(ctx, street)
        line = street_line(ctx.history, street)
        board = ctx.board[: narrow.STREET_CARDS[street]]
        if min(_live_weight(w[s], board) for s in SEATS) < MIN_COMBOS:
            raise NoSolve(f"a range weighs under {MIN_COMBOS:g} combo at the {street}")
        stack = round((ctx.effective_bb - line.put_bb) * CHIPS_PER_BB)
        if stack <= 0:
            raise NoSolve("no chips behind")
        spec = {
            "oop_range": [float(x) for x in w["bb"][SOLVER_INDEX]],
            "ip_range": [float(x) for x in w["sb"][SOLVER_INDEX]],
            "board": cards_str(board),
            "starting_pot": round(line.pot_bb * CHIPS_PER_BB),
            "effective_stack": stack,
            **TREE,
            **SETTINGS,
            "report": [list(p) for p in REPORT],
        }
        start = time.perf_counter()
        result = run(spec, TIMEOUT[street], street)
        seconds = time.perf_counter() - start
        nodes = {tuple(r["path"]): Node.read(r) for r in result["reports"] if r["reached"]}
        return Solved(street, spec, nodes, w, narrowed, seconds, result["exploitability_pct"])

    def answer(self, spot: Spot) -> Answer:
        """The solved strategy for the hero's hand at the node the line reached."""
        ctx = self.context(spot)
        street = spot.street
        solved = self.future(ctx, street).result()
        line = street_line(spot.history, street)
        walked = walk(solved, line)
        node = solved.nodes.get(walked.path)
        if node is None or node.seat != spot.seat:
            raise NoSolve(f"the {street} line left the solved tree")
        (k,) = np.flatnonzero(node.index == narrow.INDEX[spot.hero])
        row = node.strategy[:, k]
        names = [SHOWN[n] for n, _ in node.actions]
        mix = {names[i]: float(row[i]) for i in range(len(names))}
        top = int(np.argmax(row))  # ties go to the earlier action
        name, chips = node.actions[top]
        size = None
        if name in ("Bet", "Raise"):
            f = _tree_f(chips, spot.seat, solved.spec["starting_pot"], walked.bets)
            own, call = line.bets_bb[spot.seat], spot.to_call_bb
            size = round(own + call + f * (spot.pot_bb + call), 2)
        villain = solved.start[spot.villain_seat] * walked.mult[spot.villain_seat]
        if _live_weight(villain, (*spot.hero, *spot.board)) <= 0:
            raise NoSolve("the villain's line has no weight in the solve")
        moves = sum(a.seat == spot.villain_seat for a in line.acts)
        narrowed = ", ".join(
            (*solved.narrowed, f"{street}: solved, {moves} villain move{'s' if moves != 1 else ''}")
        )
        source = (
            f"{SOURCE}: postflop-solver, tree T1; {street} solve {solved.seconds:.2f} s, "
            f"within {solved.exploitability_pct:.1f}% of the pot"
        )
        return Answer(
            SHOWN[name],
            size,
            mix,
            villain,
            walked.notes,
            source,
            narrowed,
            solved.spec,
            walked.path,
        )
