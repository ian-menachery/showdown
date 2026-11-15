"""V1 suggestions: push/fold Nash preflop, an equity helper postflop (DECISIONS 31, 32).

Postflop hints are heuristics, not GTO, and every suggestion says so. Every
suggestion can be appended to a local JSONL hand log.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from showdown.bot.policy import PushFoldStrategy
from showdown.equity.cards import ALL_COMBOS, CLASS_COMBOS, CLASS_NAMES, Combo, class_of
from showdown.equity.exact import range_vs_range
from showdown.equity.matrix import PreflopMatrix
from showdown.equity.montecarlo import monte_carlo
from showdown.equity.ranges import parse_range
from showdown.hh.grade import depth_for
from showdown.live.spot import Spot, SpotError

CALL_MARGIN = 0.05
BET_EQUITY = 0.60
BET_FRACTION = {"flop": 0.33, "turn": 0.66, "river": 0.75}
DEFAULT_TOP = {("srp", "sb"): 75, ("srp", "bb"): 55, ("3bp", "bb"): 15, ("3bp", "sb"): 30}
"""(pot type, villain seat) -> the villain's default range, top % of combos (DECISIONS 32)."""
PUSHFOLD_MAX_BB = 20
HEURISTIC = "equity heuristic, not GTO"


@dataclass(frozen=True)
class Suggestion:
    street: str
    action: str | None
    """jam, call, fold, bet or check; None when there is no suggestion or in equity mode."""
    size_bb: float | None = None
    equity: float | None = None
    se: float | None = None
    """Standard error of `equity` (0 when exact)."""
    threshold: float | None = None
    """Equity needed to call (pot odds plus the margin), or to bet."""
    evs: dict[str, float] | None = None
    """Preflop: the EV in bb of each action against the opponent's Nash strategy."""
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


class Advisor:
    def __init__(
        self,
        strategy: PushFoldStrategy,
        *,
        samples: int = 20_000,
        seed: int = 0,
        log_path: str | Path | None = None,
    ) -> None:
        self.strategy = strategy
        self.samples = samples
        self.seed = seed
        self.log_path = Path(log_path) if log_path else None
        self._defaults: dict[tuple[str, str], tuple[Combo, ...]] = {}

    @classmethod
    def load(cls, **kwargs) -> Advisor:
        return cls(PushFoldStrategy.load(), **kwargs)

    def default_range(self, pot_type: str, villain_seat: str) -> tuple[Combo, ...]:
        key = (pot_type, villain_seat)
        if key not in self._defaults:
            self._defaults[key] = top_range(DEFAULT_TOP[key], self.strategy.matrix)
        return self._defaults[key]

    def suggest(self, spot: Spot) -> Suggestion:
        start = time.perf_counter()
        result = self._preflop(spot) if spot.street == "preflop" else self._postflop(spot)
        elapsed = (time.perf_counter() - start) * 1000
        result = Suggestion(**{**result.as_dict(), "elapsed_ms": elapsed})
        if self.log_path is not None:
            self._log(spot, result)
        return result

    # --- preflop -------------------------------------------------------------------

    def _preflop(self, spot: Spot) -> Suggestion:
        expected = {"sb_first": "sb", "bb_vs_jam": "bb"}.get(spot.preflop)
        if expected is not None and expected != spot.seat:
            raise SpotError(f"{spot.preflop} is a decision for the {expected.upper()}")
        if expected is None or spot.effective_bb > PUSHFOLD_MAX_BB:
            return Suggestion(
                street="preflop",
                action=None,
                source="no suggestion: only push/fold at 20 bb or less until D3 picks a source",
            )
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

    # --- postflop ------------------------------------------------------------------

    def _postflop(self, spot: Spot) -> Suggestion:
        if spot.villain_range:
            villain = parse_range(spot.villain_range)
            label = f"custom: {spot.villain_range}"
        else:
            villain = self.default_range(spot.pot_type, spot.villain_seat)
            top = DEFAULT_TOP[(spot.pot_type, spot.villain_seat)]
            label = f"default (assumed): top {top}% for the {spot.villain_seat.upper()}"
        if spot.street == "flop":
            estimate = monte_carlo(
                [spot.hero], villain, spot.board, samples=self.samples, seed=self.seed
            )
            equity, se = estimate.equity, estimate.se
        else:
            equity, se = range_vs_range([spot.hero], villain, spot.board).equity, 0.0
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
            villain_range=label,
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
