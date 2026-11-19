"""Live suggestions (DECISIONS 31, 32, 35).

Preflop: push/fold Nash at 20 bb or less, and the preflop model's chart above
it. Postflop: an equity helper against a villain range: the model's, weighted,
or a fixed top-% default. Postflop hints are heuristics, not GTO, and every
suggestion says where it came from. Every suggestion can be appended to a local
JSONL hand log.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from showdown import preflop_model as pm
from showdown.bot.policy import PushFoldStrategy
from showdown.equity.cards import ALL_COMBOS, CLASS_COMBOS, CLASS_NAMES, Combo, class_of
from showdown.equity.exact import range_vs_range
from showdown.equity.matrix import PreflopMatrix
from showdown.equity.montecarlo import monte_carlo
from showdown.equity.ranges import parse_range
from showdown.games.preflop import OPEN_TO, THREEBET_TO
from showdown.hh.grade import depth_for
from showdown.live import jam, narrow, solve
from showdown.live.spot import DECISIONS, Spot, SpotError

CALL_MARGIN = 0.05
BET_EQUITY = 0.60
BET_FRACTION = {"flop": 0.33, "turn": 0.66, "river": 0.75}
DEFAULT_TOP = {("srp", "sb"): 75, ("srp", "bb"): 55, ("3bp", "bb"): 15, ("3bp", "sb"): 30}
"""(pot type, villain seat) -> the villain's fixed default range, top % of combos (DECISIONS 32)."""
PUSHFOLD_MAX_BB = 20
HEURISTIC = "equity heuristic, not GTO"
REACH_MIN = 0.001
"""Below 0.1% of deals reaching a decision or pot, the model gives no answer (DECISIONS 35)."""
SIZE_TOLERANCE_BB = 0.05
POT_LINES = {"srp": "rc", "3bp": "rrc"}
RANGES = ("model", "fixed")
SHOWN = {"fold": "fold", "call": "call", "raise": "raise", "all-in": "jam"}
"""The model's action names as the advisor shows them."""


@dataclass(frozen=True)
class Suggestion:
    street: str
    action: str | None
    """jam, raise, call, fold, bet or check; None when there is no suggestion or in equity mode."""
    size_bb: float | None = None
    equity: float | None = None
    se: float | None = None
    """Standard error of `equity` (0 when exact)."""
    threshold: float | None = None
    """Equity needed to call (pot odds plus the margin), or to bet."""
    evs: dict[str, float] | None = None
    """Push/fold: the EV in bb of each action against the opponent's Nash strategy."""
    mix: dict[str, float] | None = None
    """Model chart: every action's frequency for the hero's class."""
    notes: tuple[str, ...] = ()
    """Warnings shown with the suggestion: "depends on R", a raise size the model doesn't use."""
    source: str = ""
    villain_range: str = ""
    elapsed_ms: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)


def top_range(percent: float, matrix: PreflopMatrix) -> tuple[Combo, ...]:
    """Whole classes, best first by equity against a random hand, up to `percent` of combos."""
    w = matrix.pair_counts.astype(float)
    vs_random = (w * matrix.equity).sum(axis=1) / w.sum(axis=1)
    target, taken, keep = 1326 * percent / 100, 0, []
    for cls in np.argsort(-vs_random, kind="stable"):
        n = len(CLASS_COMBOS[cls])
        if taken + n > target + 1e-9:
            break
        keep.append(int(cls))
        taken += n
    chosen = set(keep)
    return tuple(c for c in ALL_COMBOS if class_of(c) in chosen)


@dataclass(frozen=True)
class VillainRange:
    combos: tuple[Combo, ...]
    weights: tuple[float, ...] | None
    """One per combo, or None for equal weights."""
    label: str


class Advisor:
    def __init__(
        self,
        strategy: PushFoldStrategy,
        model: pm.PreflopModel | None = None,
        *,
        ranges: str = "model",
        samples: int = 20_000,
        seed: int = 0,
        log_path: str | Path | None = None,
        live_solves: bool = True,
    ) -> None:
        if ranges not in RANGES:
            raise ValueError("ranges must be model or fixed")
        if ranges == "model" and model is None:
            raise ValueError("model ranges need the preflop model")
        self.strategy = strategy
        self.model = model
        self.ranges = ranges
        self.samples = samples
        self.seed = seed
        self.log_path = Path(log_path) if log_path else None
        self._defaults: dict[tuple[str, str], tuple[Combo, ...]] = {}
        self._reach: dict[tuple[float, str], float] = {}
        self._model_ranges: dict[tuple[str, str, float], VillainRange | None] = {}
        self._range_model: narrow.RangeModel | None | bool = False
        """The stopgap range model (DECISIONS 46), loaded on first use; None if absent."""
        self.solves = solve.LiveSolves(self) if live_solves else None
        """Live turn and river solves (DECISIONS 47); None when switched off."""

    @classmethod
    def load(cls, model_path: str | Path = pm.DEFAULT_MODEL, **kwargs) -> Advisor:
        return cls(PushFoldStrategy.load(), pm.PreflopModel.load(model_path), **kwargs)

    def default_range(self, pot_type: str, villain_seat: str) -> tuple[Combo, ...]:
        """The fixed top-% default (DECISIONS 32)."""
        key = (pot_type, villain_seat)
        if key not in self._defaults:
            self._defaults[key] = top_range(DEFAULT_TOP[key], self.strategy.matrix)
        return self._defaults[key]

    def reach(self, depth: float, line: str) -> float:
        """The share of deals in which the model, at R 0.90 and `depth`, follows `line`."""
        key = (depth, line)
        if key not in self._reach:
            solution = self.model.at(depth)
            self._reach[key] = solution.reach(line, self.strategy.matrix.pair_counts)
        return self._reach[key]

    def model_range(
        self, pot_type: str, villain_seat: str, effective_bb: float
    ) -> VillainRange | None:
        """The villain's weighted range from the model, or None below the reach bar."""
        depth = pm.PreflopModel.depth_for(effective_bb) or pm.GRID[0]
        key = (pot_type, villain_seat, depth)
        if key not in self._model_ranges:
            line = POT_LINES[pot_type]
            result = None
            if self.reach(depth, line) >= REACH_MIN:
                sb, bb = self.model.at(depth).line_factors(line)
                per_class = sb if villain_seat == "sb" else bb
                kept = [(c, float(per_class[class_of(c)])) for c in ALL_COMBOS]
                kept = [(c, w) for c, w in kept if w > 0]
                share = sum(w for _, w in kept) / len(ALL_COMBOS)
                result = VillainRange(
                    tuple(c for c, _ in kept),
                    tuple(w for _, w in kept),
                    f"model range (assumed): the {villain_seat.upper()}'s {pot_type} line at "
                    f"{depth:g} bb, R {pm.R_PRODUCT:.2f}, {share:.0%} of combos",
                )
            self._model_ranges[key] = result
        return self._model_ranges[key]

    def given_range(self, spot: Spot) -> VillainRange | None:
        """Ian's range for the villain: `--villain` or `--villain-top`, or None."""
        if spot.villain_range:
            return VillainRange(
                parse_range(spot.villain_range), None, f"custom: {spot.villain_range}"
            )
        if spot.villain_top is not None:
            combos = top_range(spot.villain_top, self.strategy.matrix)
            share = len(combos) / len(ALL_COMBOS)
            label = f"top {spot.villain_top:g}% (--villain-top), {share:.1%} of combos"
            return VillainRange(combos, None, label)
        return None

    def villain(self, spot: Spot) -> VillainRange:
        """Ian's range as given; otherwise the assumed one, narrowed by the villain's moves."""
        given = self.given_range(spot)
        if given is not None:
            return given
        base = self._assumed_villain(spot)
        if spot.street == "preflop" or not spot.history:
            return base
        if self.range_model() is None:
            return base
        weights, used, missing = narrow.narrow(
            self._range_model,
            base.combos,
            base.weights,
            spot.board,
            spot.history,
            spot.villain_seat,
            spot.pot_type,
        )
        if used + missing == 0:
            return base
        label = (
            f"{base.label}; range model (assumed, not solved): narrowed by {used} villain "
            f"move{'s' if used != 1 else ''}, fitted to S2b/S2c solves"
        )
        if missing:
            label += f"; {missing} move{'s' if missing != 1 else ''} with no curve"
        return VillainRange(base.combos, weights, label)

    def range_model(self) -> narrow.RangeModel | None:
        if self._range_model is False:
            self._range_model = narrow.RangeModel.load()
        return self._range_model

    def advice_range(self, spot: Spot) -> VillainRange:
        """The villain's range the advice uses: the solved one where a live solve answers."""
        if self.solves is not None:
            try:
                return self._solved_range(spot, self.solves.answer(spot))
            except solve.NoSolve:
                pass
        return self.villain(spot)

    def prefetch(self, spot: Spot) -> None:
        """Start the live solve for this street, if one will answer it (DECISIONS 47)."""
        if self.solves is not None:
            self.solves.prefetch(spot)

    def solving(self, spot: Spot) -> bool:
        """True while a live solve that answers this spot is still running or not started."""
        return self.solves is not None and self.solves.pending(spot)

    def solve_started(self, spot: Spot) -> bool:
        return self.solves is not None and self.solves.started(spot)

    def _solved_range(self, spot: Spot, answer: solve.Answer) -> VillainRange:
        keep = [i for i, w in enumerate(answer.villain) if w > 0]
        base = self._assumed_villain(spot).label
        return VillainRange(
            tuple(ALL_COMBOS[i] for i in keep),
            tuple(float(answer.villain[i]) for i in keep),
            f"{base}; narrowed by {answer.narrowed}",
        )

    def _assumed_villain(self, spot: Spot) -> VillainRange:
        top = DEFAULT_TOP[(spot.pot_type, spot.villain_seat)]
        fixed = f"default (assumed): top {top}% for the {spot.villain_seat.upper()}"
        if self.ranges == "fixed":
            return VillainRange(self.default_range(spot.pot_type, spot.villain_seat), None, fixed)
        found = self.model_range(spot.pot_type, spot.villain_seat, spot.effective_bb)
        if found is not None:
            return found
        depth = pm.PreflopModel.depth_for(spot.effective_bb) or pm.GRID[0]
        return VillainRange(
            self.default_range(spot.pot_type, spot.villain_seat),
            None,
            f"{fixed}; the model almost never reaches this pot at {depth:g} bb",
        )

    def suggest(self, spot: Spot) -> Suggestion:
        start = time.perf_counter()
        result = self._preflop(spot) if spot.street == "preflop" else self._postflop(spot)
        if spot.legal is not None:
            result = _legalize(result, spot)
        elapsed = (time.perf_counter() - start) * 1000
        result = Suggestion(**{**result.as_dict(), "elapsed_ms": elapsed})
        if self.log_path is not None:
            self._log(spot, result)
        return result

    # --- preflop -------------------------------------------------------------------

    def _preflop(self, spot: Spot) -> Suggestion:
        if spot.has_villain_range and spot.preflop not in jam.JAM_DECISIONS:
            raise SpotError(
                "a preflop villain range is used only against a jam: "
                + ", ".join(jam.JAM_DECISIONS)
            )
        if spot.preflop == "other":
            return _none("not one of the model's decisions")
        seat, node = DECISIONS[spot.preflop]
        if seat != spot.seat:
            raise SpotError(f"{spot.preflop} is a decision for the {seat.upper()}")
        reference = self._reference(spot, node)
        given = self.given_range(spot)
        if given is not None:  # Ian's read: the exploit view (DECISIONS 36)
            return self._jam(spot, given, reference)
        if reference.action is None and spot.preflop in jam.DEFAULT_TOP:
            top = jam.DEFAULT_TOP[spot.preflop]
            combos = top_range(top, self.strategy.matrix)
            label = (
                f"default (assumed): top {top:g}% for a {jam.JAM_KIND[spot.preflop]}, "
                f"{len(combos) / len(ALL_COMBOS):.1%} of combos"
            )
            return self._jam(spot, VillainRange(combos, None, label), None)
        return reference

    def _reference(self, spot: Spot, node: str) -> Suggestion:
        """Push/fold Nash or the model chart, or "no suggestion" (DECISIONS 32, 35)."""
        if spot.effective_bb <= PUSHFOLD_MAX_BB:
            if spot.preflop in ("sb_first", "bb_vs_jam"):
                return self._pushfold(spot)
            if spot.preflop == "sb_vs_jam":
                return _none(
                    "at 20 bb or less push/fold has no jam over a raise; "
                    "give --villain or --villain-top"
                )
            return _none("at 20 bb or less only push/fold answers, for sb_first and bb_vs_jam")
        if self.model is None:
            return _none("no preflop model loaded above 20 bb")
        return self._model_chart(spot, node)

    def _jam(self, spot: Spot, villain: VillainRange, reference: Suggestion | None) -> Suggestion:
        """Call or fold against an all-in, as the best response to `villain` (DECISIONS 36)."""
        if spot.to_call_bb <= 0:
            raise SpotError(f"{spot.preflop} needs the amount to call for the jam helper")
        try:
            weights = jam.class_weights(villain.combos)
            equity = jam.jam_equity(spot.hero, weights, self.strategy.matrix)
        except jam.RangeError as error:
            raise SpotError(str(error)) from None
        result = jam.answer(equity, spot.pot_bb, spot.to_call_bb)
        notes = ["close"] if result.close else []
        if reference is not None and reference.action is not None:
            said = f"{_reference_label(reference)} says {reference.action}"
            if reference.action == result.action:
                notes.append(f"{said}; it agrees")
            else:
                gain = result.ev_call if result.action == "call" else -result.ev_call
                verb = "calling" if result.action == "call" else "folding"
                notes.append(f"{said}; against this range {verb} gains {gain:+.2f} bb")
        return Suggestion(
            street="preflop",
            action=result.action,
            equity=result.equity,
            threshold=result.price,
            evs={"call": result.ev_call, "fold": 0.0},
            notes=tuple(notes),
            source="jam vs range: exact equity; EV relative to folding",
            villain_range=villain.label,
        )

    def _pushfold(self, spot: Spot) -> Suggestion:
        depth = depth_for(spot.effective_bb)
        cls = class_of(spot.hero)
        grade = self.strategy.grade(depth, spot.seat, cls, True)
        allin = "jam" if spot.seat == "sb" else "call"
        action = allin if grade.ev_allin > grade.ev_fold else "fold"
        return Suggestion(
            street="preflop",
            action=action,
            evs={allin: grade.ev_allin, "fold": grade.ev_fold},
            source=f"push/fold Nash at {depth} bb ({CLASS_NAMES[cls]})",
        )

    def _model_chart(self, spot: Spot, node: str) -> Suggestion:
        depth = pm.PreflopModel.depth_for(spot.effective_bb)
        reach = self.reach(depth, node)
        if reach < REACH_MIN:
            return _none(
                f"the model almost never reaches this decision at {depth:g} bb "
                f"({reach:.3%} of deals)"
            )
        notes = []
        faced = None
        if spot.preflop in ("bb_vs_raise", "sb_vs_3bet"):
            if spot.to_call_bb <= 0:
                raise SpotError(f"{spot.preflop} needs the amount to call")
            faced = spot.raise_to_bb
            model_size, kind = (
                (OPEN_TO, "open") if spot.preflop == "bb_vs_raise" else (THREEBET_TO, "3-bet")
            )
            if abs(faced - model_size) > SIZE_TOLERANCE_BB:
                notes.append(f"model assumes a {model_size:g} bb {kind}; you face {faced:g} bb")
        cls = class_of(spot.hero)
        probs = self.model.at(depth).probs(node, cls)
        top = max(probs, key=probs.get)  # ties go to the earlier action
        if self.model.depends_on_r(depth, node, cls):
            notes.insert(0, "depends on R")
        size = None
        if top == "raise":
            size = OPEN_TO if spot.preflop == "sb_first" else round(3 * faced, 2)
        return Suggestion(
            street="preflop",
            action=SHOWN[top],
            size_bb=size,
            mix={SHOWN[a]: p for a, p in probs.items()},
            notes=tuple(notes),
            source=f"model chart, R {pm.R_PRODUCT:.2f}, {depth:g} bb ({CLASS_NAMES[cls]})",
        )

    # --- postflop ------------------------------------------------------------------

    def _postflop(self, spot: Spot) -> Suggestion:
        """A live solve on the turn and river where one answers (DECISIONS 47); otherwise, and
        on the flop, the equity helper against the stopgap's range."""
        if self.solves is None or spot.street not in ("turn", "river") or not spot.history:
            return self._equity(spot)
        try:
            answer = self.solves.answer(spot)
        except solve.NoSolve as why:
            helper = self._equity(spot)
            return replace(helper, source=f"{helper.source}; no live solve: {why}")
        villain = self._solved_range(spot, answer)
        equity = range_vs_range([spot.hero], villain.combos, spot.board, villain.weights).equity
        return Suggestion(
            street=spot.street,
            action=answer.action,
            size_bb=answer.size_bb,
            equity=equity,
            se=0.0,
            mix=answer.mix,
            notes=answer.notes,
            source=answer.source,
            villain_range=villain.label,
        )

    def _equity(self, spot: Spot) -> Suggestion:
        villain = self.villain(spot)
        if spot.street == "flop":
            estimate = monte_carlo(
                [spot.hero],
                villain.combos,
                spot.board,
                samples=self.samples,
                seed=self.seed,
                villain_weights=villain.weights,
            )
            equity, se = estimate.equity, estimate.se
        else:
            exact = range_vs_range([spot.hero], villain.combos, spot.board, villain.weights)
            equity, se = exact.equity, 0.0
        if spot.to_call_bb > 0:
            threshold = spot.to_call_bb / (spot.pot_bb + spot.to_call_bb) + CALL_MARGIN
            action, size = ("call" if equity >= threshold else "fold"), None
        elif spot.mode == "equity":
            threshold, action, size = None, None, None
        else:
            threshold = BET_EQUITY
            if equity >= BET_EQUITY:
                action, size = "bet", round(spot.pot_bb * BET_FRACTION[spot.street], 2)
            else:
                action, size = "check", None
        return Suggestion(
            street=spot.street,
            action=action,
            size_bb=size,
            equity=equity,
            se=se,
            threshold=threshold,
            source=HEURISTIC,
            villain_range=villain.label,
        )

    # --- log ----------------------------------------------------------------------------

    def _log(self, spot: Spot, suggestion: Suggestion) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        line = {
            "time": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "spot": spot.describe(),
            "suggestion": suggestion.as_dict(),
        }
        with self.log_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(line) + "\n")


RAISES = ("bet", "raise", "jam", "all-in")


def _legalize(s: Suggestion, spot: Spot) -> Suggestion:
    """Keep the advice to legal actions and sizes (DECISIONS 41). The rules behind it are unchanged.

    A size is held within pokerkit's smallest and largest raise-to and capped at the most
    the opponent can match; one that reaches that cap is shown as all-in. When the cap is
    below the smallest legal raise, no raise fits both limits, so the advice calls or checks.
    """
    legal = spot.legal
    if s.action is None:
        return s
    facing = legal.to_call_bb > 0
    action, size, notes = s.action, s.size_bb, list(s.notes)
    passive = "call" if facing else "check"
    if action in RAISES:
        cap = min(legal.raise_max_bb, legal.cap_bb) if legal.can_raise else None
        if cap is None or cap < legal.raise_min_bb:
            notes.append(f"no {action} fits the legal sizes here: {passive} instead")
            action, size = passive, None
        else:
            wanted = cap if action in ("jam", "all-in") or size is None else size
            size = max(legal.raise_min_bb, min(wanted, cap))
            if size >= cap - 1e-9:
                if action not in ("jam", "all-in"):
                    notes.append(f"{action} {wanted:g} bb is more than can be matched: all-in")
                action = "jam" if spot.street == "preflop" else "all-in"
            elif size != wanted:
                notes.append(f"{action} {wanted:g} bb is below the minimum: {size:g} bb")
    elif action == "fold" and not facing:
        notes.append("nothing to call: check, not fold")
        action = "check"
    elif action in ("call", "check") and action != passive:
        notes.append(f"{action} is not legal here: {passive}")
        action = passive
    behind = spot.stack_behind_bb
    if action == "call" and behind is not None and legal.to_call_bb >= behind - 1e-9:
        notes.append("calling puts you all-in")
    return Suggestion(**{**s.as_dict(), "action": action, "size_bb": size, "notes": tuple(notes)})


def _reference_label(reference: Suggestion) -> str:
    """The source without its class: "push/fold Nash at 10 bb", "model chart, R 0.90, 100 bb"."""
    return reference.source.rsplit(" (", 1)[0]


def _none(why: str) -> Suggestion:
    return Suggestion(street="preflop", action=None, source=f"no suggestion: {why}")
