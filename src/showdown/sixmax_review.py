"""Six-max hand review (DECISIONS 58): a player's first preflop decision in each completed
six-handed hand, graded by kind of action against `showdown sixmax`.

Study only (SCOPE A13, A17): it reads completed hands, never a live one.

A decision is graded when it fits an engine spot:
- six players, blinds 1:2, no straddle;
- an ante of 0 or 0.5 bb from everyone;
- an effective stack of 60 to 150 bb;
- an unopened pot, or 1 to 3 non-blind limpers (a BB hero needs the SB to have folded);
- known cards.

Anything else is skipped under the first cause in `CAUSES` that applies. Grades are the
drills' (DECISIONS 55): good, marginal or review, with the bb lost against the best action.
"""

from __future__ import annotations

import copy
import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, replace

import numpy as np

from showdown import sixmax as S
from showdown.equity.cards import CLASS_NAMES, cards_str, class_index, class_of, make_combo
from showdown.hh.parse import ParseReport
from showdown.hh.replay import HandRecord
from showdown.sixmax_drill import grade

CAUSES = (
    "not six-handed",
    "blinds",
    "ante",
    "stack depth",
    "no decision",
    "raised before you",
    "the SB completed",
    "short all-in before you",
    "too many limpers",
    "cards unknown",
)
SEAT_OF = ("SB", "BB", "UTG", "HJ", "CO", "BTN")
"""pokerkit's order for six players."""
ANTES = (0.0, 0.5)
DEPTH = (60.0, 150.0)
TIERS = ("clear", "close", "review")
GRADES = ("good", "marginal", "review")
LEAK_MIN, LEAKS_SHOWN, HANDS_SHOWN = 3, 3, 5


@dataclass
class Decision:
    source: str
    cause: str | None = None
    """Why it was skipped; None when graded."""
    seat: str = ""
    limpers: int = 0
    ante: float = 0.0
    cards: str = ""
    hand: str = ""
    kind: str = ""
    """fold, limp (limp, overlimp, complete or check) or raise."""
    size: float | None = None
    """Raise-to in bb, for a raise."""
    grade: str = ""
    best: str = ""
    tier: str = ""
    bb_lost: float = 0.0


def _same(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def classify(record: HandRecord, player: str) -> Decision | None:
    """The player's first preflop decision as an engine spot, or the reason it is not one.
    None when the player is not in the hand."""
    names = [p.name for p in record.players]
    if player not in names:
        return None
    me = names.index(player)
    d = Decision(record.source)

    def skip(cause: str) -> Decision:
        d.cause = cause
        return d

    if len(names) != 6:
        return skip("not six-handed")
    bb, posts = record.big_blind, record.blind_posts
    if set(posts) != {0, 1} or not _same(posts[1], bb) or not _same(2 * posts[0], bb):
        return skip("blinds")
    antes = [a / bb for a in record.antes]
    ante = next((x for x in ANTES if all(_same(a, x) for a in antes)), None)
    if ante is None:
        return skip("ante")
    stacks = [p.starting / bb for p in record.players]
    effective = min(stacks[me], max(s for i, s in enumerate(stacks) if i != me))
    if not (DEPTH[0] <= effective <= DEPTH[1] or any(_same(effective, x) for x in DEPTH)):
        return skip("stack depth")
    mine = [k for k, (who, _, _) in enumerate(record.preflop) if who == me]
    if not mine:
        return skip("no decision")
    before = record.preflop[: mine[0]]
    if any(kind == "raise" for _, kind, _ in before):
        return skip("raised before you")
    seat = SEAT_OF[me]
    if seat == "BB" and any(who == 0 and kind == "call" for who, kind, _ in before):
        return skip("the SB completed")
    calls = [amount for who, kind, amount in before if who >= 2 and kind == "call"]
    if any(amount < bb and not _same(amount, bb) for amount in calls):
        return skip("short all-in before you")
    if len(calls) > S.MAX_LIMPERS[seat]:
        return skip("too many limpers")
    hole = record.players[me].hole
    if hole is None:
        return skip("cards unknown")
    _, kind, amount = record.preflop[mine[0]]
    combo = make_combo(*hole)
    d.seat, d.limpers, d.ante = seat, len(calls), ante
    d.cards, d.hand = cards_str(combo), CLASS_NAMES[class_of(combo)]
    d.kind = kind if kind in ("fold", "raise") else "limp"
    d.size = round(amount / bb, 9) if kind == "raise" else None
    return d


class Grader:
    """Engine answers per spot and class, each equal to a fresh `sixmax.answer`: one deal per
    seat and limper count, its random state put back before each hand, as the drills do."""

    def __init__(self, profile: S.Profile, *, samples: int = S.SAMPLES, seed: int = 0) -> None:
        self.profile, self.samples, self.seed = profile, samples, seed
        self._deals: dict[tuple[str, int], tuple[S.Deal, dict]] = {}
        self._tables: dict[S.Spot, dict] = {}
        self._answers: dict[tuple[S.Spot, int], S.Answer] = {}

    def answer(self, spot: S.Spot, cls: int) -> S.Answer:
        if (spot, cls) not in self._answers:
            key = (spot.seat, spot.limpers)
            if key not in self._deals:
                d = S.deal(spot, self.profile, samples=self.samples, seed=self.seed)
                self._deals[key] = (d, copy.deepcopy(d.rng.bit_generator.state))
            base, state = self._deals[key]
            d = replace(base, spot=spot, rng=np.random.default_rng())
            d.rng.bit_generator.state = copy.deepcopy(state)
            if spot not in self._tables:
                self._tables[spot] = S.outcome_table(d)
            self._answers[(spot, cls)] = S.evaluate(d, cls, self._tables[spot])
        return self._answers[(spot, cls)]


def review(
    records: Iterable[HandRecord],
    player: str,
    profile: S.Profile,
    *,
    samples: int = S.SAMPLES,
    seed: int = 0,
) -> list[Decision]:
    """Every hand the player is in, graded or skipped with its cause."""
    grader = Grader(profile, samples=samples, seed=seed)
    out = []
    for record in records:
        d = classify(record, player)
        if d is None:
            continue
        if d.cause is None:
            a = grader.answer(S.Spot(d.seat, d.limpers, d.ante), class_index(d.hand))
            d.grade, d.bb_lost = grade(a, d.kind)
            d.best, d.tier = a.best, a.tier
        out.append(d)
    return out


def summarize(decisions: list[Decision]) -> dict:
    graded = [d for d in decisions if d.cause is None]
    causes = Counter(d.cause for d in decisions if d.cause)
    groups: dict[tuple, list[Decision]] = {}
    for d in graded:
        if d.grade == "review":
            pot = "limped" if d.limpers else "unopened"
            groups.setdefault((d.seat, pot, d.kind, S.kind(d.best)), []).append(d)
    leaks = [
        {
            "seat": seat,
            "pot": pot,
            "answer": answer,
            "best": best,
            "count": len(ds),
            "bb_lost": sum(d.bb_lost for d in ds),
            "hands": sorted(ds, key=lambda d: -d.bb_lost)[:HANDS_SHOWN],
        }
        for (seat, pot, answer, best), ds in groups.items()
        if len(ds) >= LEAK_MIN
    ]
    leaks.sort(key=lambda leak: (-leak["bb_lost"], leak["seat"], leak["pot"], leak["answer"]))
    return {
        "hands": len(decisions),
        "graded": len(graded),
        "skipped": {c: causes[c] for c in CAUSES if causes[c]},
        "tiers": {
            t: {g: sum(d.tier == t and d.grade == g for d in graded) for g in GRADES} for t in TIERS
        },
        "bb_lost": sum(d.bb_lost for d in graded),
        "bb_lost_clear": sum(d.bb_lost for d in graded if d.tier == "clear"),
        "leaks": leaks,
    }


def _spot(d: Decision) -> str:
    limpers = f"{d.limpers} limper{'s' * (d.limpers != 1)}" if d.limpers else "unopened"
    return f"{d.seat}, {limpers}, ante {d.ante:g}"


def describe(parsed: ParseReport, summary: dict, player: str, profile: str) -> list[str]:
    """The report `showdown sixmax review` prints."""
    sources = [r.source for r in parsed.records] + [s for s, _ in parsed.failures]
    files = len({s.split("#")[0] for s in sources})
    lines = [
        f"Six-max hand review for {player}, study only (DECISIONS 58). Profile: {profile}. "
        "Graded by kind of action (fold, limp, raise), as the drills; sizes are shown, "
        "not graded.",
        f"Read {files} file{'s' * (files != 1)}: {parsed.found} hands, {parsed.parsed} parsed, "
        f"{len(parsed.failures)} failed. {player} is in {summary['hands']}.",
        f"Graded: {summary['graded']}. Skipped: "
        + (", ".join(f"{c} {n}" for c, n in summary["skipped"].items()) or "none")
        + ".",
        "",
        "Grades by tier (good / marginal / review):",
    ]
    for t, row in summary["tiers"].items():
        lines.append(f"  {t:7s} {row['good']:5d} / {row['marginal']:5d} / {row['review']:5d}")
    lines += [
        f"bb lost against the best action: {summary['bb_lost']:.2f} in all, "
        f"{summary['bb_lost_clear']:.2f} on clear spots.",
        "",
        f"Leaks: review grades, at least {LEAK_MIN} alike, by bb lost:",
    ]
    if not summary["leaks"]:
        lines.append("  none")
    for n, leak in enumerate(summary["leaks"][:LEAKS_SHOWN], 1):
        lines.append(
            f"  {n}. {leak['seat']}, {leak['pot']} pots: you {leak['answer']} where the best is "
            f"a {leak['best']}. {leak['count']} hands, {leak['bb_lost']:.2f} bb."
        )
        for d in leak["hands"]:
            size = f" to {d.size:g}" if d.size is not None else ""
            lines.append(
                f"     {d.source}: {d.cards}, {_spot(d)}: you {d.kind}{size}; "
                f"best {d.best} ({d.tier}); {d.bb_lost:.2f} bb"
            )
    return lines
