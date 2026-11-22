"""The six-max drill trainer (DECISIONS 55): practice spots, graded by kind of action.

Study only (SCOPE A13, A15): it deals practice spots and never reads a live hand.

A drill draws a seat and limper count uniformly from the 17 allowed shapes, an ante of 0 or
0.5 unless one is set, and a combo uniformly from the 1,326. A hand whose best action is a
clear fold is shown one time in five; otherwise another hand is drawn. The player names
the kind of action (fold, limp, raise), and it is graded:
- good: the best action's kind;
- marginal: another kind, but one that wins at some band point;
- review: anything else, with the bb lost against the best action.

Each seat and limper count is dealt once per session; the ante changes no deal. Before
each hand is evaluated, the deal's random state is put back to where `sixmax.answer`
would have it. So every graded answer equals a fresh `sixmax.answer` exactly.
"""

from __future__ import annotations

import copy
import json
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

import numpy as np

from showdown import sixmax as S
from showdown.equity.cards import ALL_COMBOS, CLASS_NAMES, Combo, cards_str, class_of

LOG_DIR = S.ROOT / "data" / "drills"
SHAPES = tuple(
    (seat, k)
    for seat, most in S.MAX_LIMPERS.items()
    for k in range(1 if seat == "BB" else 0, most + 1)
)
ANTES = (0.0, 0.5)
SHOW_CLEAR_FOLD = 0.2
KEYS = {"f": "fold", "l": "limp", "c": "limp", "r": "raise"}


def grade(a: S.Answer, answer: str) -> tuple[str, float]:
    """(good, marginal or review; the bb lost) for an answered kind of action."""
    ev = dict(zip(a.actions, a.ev, strict=True))
    lost = float(ev[a.best] - max(ev[n] for n in a.actions if S.kind(n) == answer))
    if answer == S.kind(a.best):
        return "good", lost
    if any(S.kind(w) == answer for _, _, w in a.flips):
        return "marginal", lost
    return "review", lost


@dataclass
class Drill:
    spot: S.Spot
    combo: Combo
    answer: S.Answer
    profile: S.Profile
    """The profile for the hero's seat, as the ranges are shown."""


class Trainer:
    """Deals drills from one seeded stream; the engine's deals use seed 0, as `answer`."""

    def __init__(
        self,
        profile: S.Profile,
        *,
        ante: float | None = None,
        samples: int = S.SAMPLES,
        seed: int = 0,
    ) -> None:
        self.profile = profile
        self.ante = ante
        self.samples = samples
        self.rng = np.random.default_rng(seed)
        self._deals: dict[tuple[str, int], tuple[S.Deal, dict]] = {}
        self.last: Drill | None = None

    def _deal(self, spot: S.Spot) -> S.Deal:
        key = (spot.seat, spot.limpers)
        if key not in self._deals:
            d = S.deal(spot, self.profile, samples=self.samples)
            self._deals[key] = (d, copy.deepcopy(d.rng.bit_generator.state))
        d, state = self._deals[key]
        fresh = replace(d, spot=spot, rng=np.random.default_rng())
        fresh.rng.bit_generator.state = copy.deepcopy(state)
        return fresh

    def next(self) -> Drill:
        seat, k = SHAPES[self.rng.integers(len(SHAPES))]
        ante = self.ante if self.ante is not None else float(self.rng.choice(ANTES))
        spot = S.Spot(seat, k, ante)
        table = S.outcome_table(self._deal(spot))
        while True:
            combo = ALL_COMBOS[self.rng.integers(len(ALL_COMBOS))]
            d = self._deal(spot)
            a = S.evaluate(d, class_of(combo), table)
            clear_fold = a.best == "fold" and a.tier == "clear"
            if not clear_fold or self.rng.random() < SHOW_CLEAR_FOLD:
                self.last = Drill(spot, combo, a, d.profile)
                return self.last


def _prompt(a: S.Answer) -> tuple[str, list[str]]:
    kinds = []
    labels = []
    for name in a.actions:
        k = S.kind(name)
        if k in kinds:
            continue
        kinds.append(k)
        word = "raise" if k == "raise" else name
        labels.append(
            word.replace("limp", "[l]imp", 1) if word == "overlimp" else f"[{word[0]}]{word[1:]}"
        )
    return "Your action? " + " / ".join(labels) + " / [q]uit: ", kinds


def summarize(rows: list[dict]) -> dict:
    grades = Counter(r["grade"] for r in rows)
    misses = Counter(
        f"{r['seat']}, {r['limpers']} limper{'s' * (r['limpers'] != 1)}"
        for r in rows
        if r["grade"] != "good"
    )
    return {
        "drills": len(rows),
        "grades": {g: grades[g] for g in ("good", "marginal", "review")},
        "bb_lost": sum(r["bb_lost"] for r in rows),
        "misses": dict(misses.most_common()),
    }


def run(
    trainer: Trainer,
    count: int,
    *,
    log_dir: Path = LOG_DIR,
    ask: Callable[[str], str] | None = None,
    show: Callable[[str], None] = print,
    clock: Callable[[], float] = time.perf_counter,
) -> dict:
    """A session of up to `count` drills; returns the summary, with the log's path."""
    ask = ask or input
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{datetime.now():%Y%m%d-%H%M%S-%f}.jsonl"
    rows: list[dict] = []
    show(
        "Six-max drills, study only (DECISIONS 55). Name the kind of action; the size is "
        "shown after."
    )
    with path.open("w", encoding="utf-8", newline="\n") as log:
        for i in range(count):
            start = clock()
            drill = trainer.next()
            a = drill.answer
            hand = cards_str(drill.combo)
            show(f"\nDrill {i + 1} of {count}")
            show("\n".join(S.describe_spot(drill.spot, drill.profile, hand)))
            prompt, kinds = _prompt(a)
            seconds = clock() - start
            reply = ""
            while True:
                reply = ask(prompt).strip().lower()[:1]
                if reply == "q" or KEYS.get(reply) in kinds:
                    break
                show("  Answer " + ", ".join(k[0] for k in kinds) + " or q.")
            if reply == "q":
                break
            answer = KEYS[reply]
            g, lost = grade(a, answer)
            cost = f", {lost:.2f} bb behind the best" if lost > 0 else ""
            show(f"\n{g.upper()}: you chose {answer}{cost}. Best: {a.best}.")
            show("\n".join(S.describe_answer(a, trainer.samples, 0)))
            row = {
                "time": datetime.now().isoformat(timespec="seconds"),
                "seat": drill.spot.seat,
                "limpers": drill.spot.limpers,
                "ante": drill.spot.ante,
                "profile": trainer.profile.name,
                "hand": hand,
                "class": CLASS_NAMES[class_of(drill.combo)],
                "answer": answer,
                "grade": g,
                "best": a.best,
                "tier": a.tier,
                "ev": dict(zip(a.actions, (float(e) for e in a.ev), strict=True)),
                "bb_lost": lost,
                "seconds": seconds,
            }
            log.write(json.dumps(row) + "\n")
            log.flush()
            rows.append(row)
    summary = summarize(rows) | {"log": str(path)}
    g = summary["grades"]
    show(
        f"\nSession: {summary['drills']} drills, {g['good']} good, {g['marginal']} marginal, "
        f"{g['review']} review; {summary['bb_lost']:.2f} bb behind the best in all."
    )
    if summary["misses"]:
        show("Misses by spot: " + "; ".join(f"{k} {v}" for k, v in summary["misses"].items()))
    show(f"Log: {path}")
    return summary
