"""The six-max drill trainer (DECISIONS 55, 60): practice spots, graded on GTO Wizard's scale.

Study only (SCOPE A13, A15, A20): it deals practice spots and never reads a live hand.

A drill draws a seat and limper count uniformly from the 17 allowed shapes, an ante of 0 or
0.5 unless one is set, and a combo uniformly from the 1,326. A hand whose best action is a
clear fold is shown one time in five; otherwise another hand is drawn. With player types
(DECISIONS 60), each drill also draws a limper type and a table type, unless they are fixed.

The player names an action with its size, graded Best, Correct, Inaccuracy, Wrong or
Blunder by `sixmax.grade`, with a "why" from the engine's numbers. The kind-only drill of
DECISIONS 55 (good, marginal, review) stays as `run(..., sizes=False)`, for Gate K.

Each seat, limper count and limper type is dealt once per session; the ante and the table
type change no deal. Before each hand is evaluated, the deal's random state is put back to
where `sixmax.answer` would have it. So every graded answer equals a fresh `sixmax.answer`.
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
KIND_GRADES = ("good", "marginal", "review")


def grade(a: S.Answer, answer: str) -> tuple[str, float]:
    """DECISIONS 55's kind grade: (good, marginal or review; the bb lost)."""
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
    deal: S.Deal | None = None
    table: dict | None = None
    limpers_type: str | None = None
    table_type: str | None = None


class Trainer:
    """Deals drills from one seeded stream; the engine's deals use seed 0, as `answer`."""

    def __init__(
        self,
        profile: S.Profile,
        *,
        ante: float | None = None,
        samples: int = S.SAMPLES,
        seed: int = 0,
        types: bool = False,
        limpers_type: str | None = None,
        table_type: str | None = None,
    ) -> None:
        self.profile = profile
        self.ante = ante
        self.samples = samples
        self.rng = np.random.default_rng(seed)
        self.types = types
        self.limpers_type, self.table_type = limpers_type, table_type
        self._deals: dict[tuple, tuple[S.Deal, dict]] = {}
        self._profiles: dict[tuple[str, str], S.Profile] = {}
        self.last: Drill | None = None
        if types:
            self._base = S.load_profiles()
            self._types = S.load_types()

    def compose(self, limpers: str, table: str) -> S.Profile:
        if (limpers, table) not in self._profiles:
            self._profiles[(limpers, table)] = S.compose(
                limpers, table, profiles=self._base, types=self._types
            )
        return self._profiles[(limpers, table)]

    def _deal(self, spot: S.Spot, profile: S.Profile | None = None) -> S.Deal:
        profile = profile or self.profile
        key = (spot.seat, spot.limpers, profile.deal_name or profile.name)
        if key not in self._deals:
            d = S.deal(spot, profile, samples=self.samples)
            self._deals[key] = (d, copy.deepcopy(d.rng.bit_generator.state))
        d, state = self._deals[key]
        fresh = replace(
            d, spot=spot, profile=profile.for_seat(spot.seat), rng=np.random.default_rng()
        )
        fresh.rng.bit_generator.state = copy.deepcopy(state)
        return fresh

    def answer(self, spot: S.Spot, profile: S.Profile, hand: int | Combo) -> S.Answer:
        """A fresh `sixmax.answer`, from the session's deals."""
        return S.evaluate(
            self._deal(spot, profile), hand, S.outcome_table(self._deal(spot, profile))
        )

    def next(self) -> Drill:
        seat, k = SHAPES[self.rng.integers(len(SHAPES))]
        ante = self.ante if self.ante is not None else float(self.rng.choice(ANTES))
        spot = S.Spot(seat, k, ante)
        profile, lt, tt = self.profile, None, None
        if self.types:
            lt = self.limpers_type or S.TYPE_KEYS[self.rng.integers(len(S.TYPE_KEYS))]
            tt = self.table_type or S.TYPE_KEYS[self.rng.integers(len(S.TYPE_KEYS))]
            profile = self.compose(lt, tt)
        table = S.outcome_table(self._deal(spot, profile))
        while True:
            combo = ALL_COMBOS[self.rng.integers(len(ALL_COMBOS))]
            d = self._deal(spot, profile)
            a = S.evaluate(d, class_of(combo), table)
            clear_fold = a.best == "fold" and a.tier == "clear"
            if not clear_fold or self.rng.random() < SHOW_CLEAR_FOLD:
                self.last = Drill(spot, combo, a, d.profile, d, table, lt, tt)
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


def _prompt_sizes(a: S.Answer) -> tuple[str, dict[str, str]]:
    """The prompt, and each reply's action: f, l or c, or a raise's size as a number."""
    keys: dict[str, str] = {}
    labels = []
    for name in a.actions:
        if S.kind(name) == "raise":
            verb, size = name.split(" to ")
            keys[size] = name
            labels.append(f"{verb} to [{size}]")
        elif name == "fold":
            keys["f"] = name
            labels.append("[f]old")
        else:
            keys["l"] = keys["c"] = name
            labels.append(name.replace("limp", "[l]imp", 1) if "limp" in name else f"[c]{name[1:]}")
    return "Your action? " + " / ".join(labels) + " / [q]uit: ", keys


def summarize(rows: list[dict], labels: tuple[str, ...] = KIND_GRADES) -> dict:
    grades = Counter(r["grade"] for r in rows)
    missed = [r for r in rows if r["grade"] != labels[0]]
    misses = Counter(
        f"{r['seat']}, {r['limpers']} limper{'s' * (r['limpers'] != 1)}" for r in missed
    )
    out = {
        "drills": len(rows),
        "grades": {g: grades[g] for g in labels},
        "bb_lost": sum(r["bb_lost"] for r in rows),
        "misses": dict(misses.most_common()),
    }
    if rows and "table_type" in rows[0]:
        by_type = Counter(f"{r['table_type']} table" for r in missed)
        by_type += Counter(f"{r['limpers_type']} limpers" for r in missed if r["limpers"])
        out["misses_by_type"] = dict(by_type.most_common())
    return out


def run(
    trainer: Trainer,
    count: int,
    *,
    log_dir: Path = LOG_DIR,
    ask: Callable[[str], str] | None = None,
    show: Callable[[str], None] = print,
    clock: Callable[[], float] = time.perf_counter,
    sizes: bool = True,
) -> dict:
    """A session of up to `count` drills; returns the summary, with the log's path.
    `sizes=False` is DECISIONS 55's kind-only drill (Gate K)."""
    ask = ask or input
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{datetime.now():%Y%m%d-%H%M%S-%f}.jsonl"
    rows: list[dict] = []
    if sizes:
        show(
            "Six-max drills, study only (DECISIONS 60). Name the action and its size; grades "
            "run Best, Correct, Inaccuracy, Wrong, Blunder by EV lost as a % of the pot."
        )
    else:
        show(
            "Six-max drills, study only (DECISIONS 55). Name the kind of action; the size is "
            "shown after."
        )
    std = None
    if trainer.types:
        std = trainer.compose("standard", "standard")
    with path.open("w", encoding="utf-8", newline="\n") as log:
        for i in range(count):
            start = clock()
            drill = trainer.next()
            a = drill.answer
            hand = cards_str(drill.combo)
            show(f"\nDrill {i + 1} of {count}")
            show("\n".join(S.describe_spot(drill.spot, drill.profile, hand)))
            if drill.limpers_type:
                types = trainer._types
                if drill.spot.limpers:
                    show("  Limpers: " + S.type_card(types[drill.limpers_type]))
                show("  Table: " + S.type_card(types[drill.table_type]))
            if sizes:
                prompt, keys = _prompt_sizes(a)
            else:
                prompt, kinds = _prompt(a)
                keys = {k: KEYS[k] for k in KEYS if KEYS[k] in kinds}
            seconds = clock() - start
            reply = ""
            while True:
                reply = ask(prompt).strip().lower()
                reply = reply if sizes else reply[:1]
                if sizes and reply.startswith("r") and reply[1:].strip() in keys:
                    reply = reply[1:].strip()
                if reply == "q" or reply in keys:
                    break
                show("  Answer " + ", ".join(dict.fromkeys(keys)) + " or q.")
            if reply == "q":
                break
            row = {
                "time": datetime.now().isoformat(timespec="seconds"),
                "seat": drill.spot.seat,
                "limpers": drill.spot.limpers,
                "ante": drill.spot.ante,
                "profile": drill.profile.name if drill.limpers_type else trainer.profile.name,
                "hand": hand,
                "class": CLASS_NAMES[class_of(drill.combo)],
            }
            if sizes:
                action = keys[reply]
                g = S.grade(a, action, drill.spot.pot)
                cost = f", {g.lost:.2f} bb ({g.pct:.0f}% of the pot) behind" if g.lost > 0 else ""
                show(f"\n{g.label.upper()}: you chose {action}{cost}. Best: {a.best}.")
                cls = class_of(drill.combo)
                for line in S.why(drill.deal, drill.table, cls, a, action):
                    show("  " + line)
                if std is not None and drill.profile.name != std.name:
                    s = trainer.answer(drill.spot, std, cls)
                    best_ev = float(s.ev[s.actions.index(s.best)])
                    show(f"  Against a standard player you'd {s.best} ({best_ev:+.2f} bb).")
                row |= {
                    "action": action,
                    "answer": S.kind(action),
                    "grade": g.label,
                    "bb_lost": g.lost,
                    "pct_lost": g.pct,
                }
                if drill.limpers_type:
                    row |= {"limpers_type": drill.limpers_type, "table_type": drill.table_type}
            else:
                answer = keys[reply]
                g_kind, lost = grade(a, answer)
                cost = f", {lost:.2f} bb behind the best" if lost > 0 else ""
                show(f"\n{g_kind.upper()}: you chose {answer}{cost}. Best: {a.best}.")
                row |= {"answer": answer, "grade": g_kind, "bb_lost": lost}
            show("\n".join(S.describe_answer(a, trainer.samples, 0)))
            row |= {
                "best": a.best,
                "tier": a.tier,
                "ev": dict(zip(a.actions, (float(e) for e in a.ev), strict=True)),
                "seconds": seconds,
            }
            log.write(json.dumps(row) + "\n")
            log.flush()
            rows.append(row)
    labels = S.LABELS if sizes else KIND_GRADES
    summary = summarize(rows, labels) | {"log": str(path)}
    g = summary["grades"]
    show(
        f"\nSession: {summary['drills']} drills, "
        + ", ".join(f"{g[label]} {label.lower()}" for label in labels)
        + f"; {summary['bb_lost']:.2f} bb behind the best in all."
    )
    if summary["misses"]:
        show("Misses by spot: " + "; ".join(f"{k} {v}" for k, v in summary["misses"].items()))
    if summary.get("misses_by_type"):
        show(
            "Misses by type: " + "; ".join(f"{k} {v}" for k, v in summary["misses_by_type"].items())
        )
    show(f"Log: {path}")
    return summary
