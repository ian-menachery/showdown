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

from showdown import lessons
from showdown import sixmax as S
from showdown import sixmax_drill as D
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


OPEN_CAUSES = (
    *CAUSES[:5],
    "raised before you",
    "open called before you",
    "open size",
    *CAUSES[6:],
)
"""DECISIONS 63's causes with pots facing one open raise graded (`opens=True`)."""
OPEN_RANGE = (2.0, 3.5)
JAM_BB = 40.0
MIN_HANDS = 30
LEAK_LABELS = ("Inaccuracy", "Wrong", "Blunder")
LEAKS_TYPED = 5


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
    """fold, limp (limp, overlimp, complete or check) or raise; call facing an open."""
    size: float | None = None
    """Raise-to in bb, for a raise."""
    grade: str = ""
    best: str = ""
    tier: str = ""
    bb_lost: float = 0.0
    # DECISIONS 63, with `opens=True`:
    family: str = "sixmax"
    """sixmax (unopened or limped) or open (facing one open raise)."""
    opener: str = ""
    open: float = 0.0
    """The open's bucket, 2.5 or 3 bb."""
    open_size: float = 0.0
    """The open's raise-to in bb, as played."""
    action: str = ""
    """The engine action the answer maps to."""
    pct: float = 0.0
    limpers_type: str = "standard"
    table_type: str = "standard"
    opener_type: str = "standard"
    limper_names: tuple = ()
    behind_names: tuple = ()
    opener_name: str = ""


def _same(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def classify(record: HandRecord, player: str, *, opens: bool = False) -> Decision | None:
    """The player's first preflop decision as an engine spot, or the reason it is not one.
    None when the player is not in the hand. With `opens`, pots facing one open raise are
    graded too, under DECISIONS 63's causes."""
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
    raises = [k for k, (_, kind, _) in enumerate(before) if kind == "raise"]
    if raises and not opens:
        return skip("raised before you")
    seat = SEAT_OF[me]
    hero = S.SEATS.index(seat)
    d.behind_names = tuple(names[SEAT_OF.index(s)] for s in S.SEATS[hero + 1 :])
    if raises:
        first = raises[0]
        if len(raises) > 1 or any(kind == "call" for _, kind, _ in before[:first]):
            return skip("raised before you")
        if any(kind == "call" for _, kind, _ in before[first + 1 :]):
            return skip("open called before you")
        who, _, open_to = before[first]
        size = open_to / bb
        if not OPEN_RANGE[0] - 1e-9 <= size <= OPEN_RANGE[1] + 1e-9:
            return skip("open size")
        hole = record.players[me].hole
        if hole is None:
            return skip("cards unknown")
        _, kind, amount = record.preflop[mine[0]]
        combo = make_combo(*hole)
        d.family, d.opener, d.opener_name = "open", SEAT_OF[who], names[who]
        d.open_size, d.open = size, (3.0 if size >= 2.75 - 1e-9 else 2.5)
        d.seat, d.ante = seat, ante
        d.cards, d.hand = cards_str(combo), CLASS_NAMES[class_of(combo)]
        d.kind = kind if kind in ("fold", "raise") else "call"
        d.size = round(amount / bb, 9) if kind == "raise" else None
        allin = kind == "raise" and amount >= record.players[me].starting - record.antes[me] - 1e-9
        d.action = _open_action(d, allin)
        return d
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
    d.limper_names = tuple(names[who] for who, k, _ in before if who >= 2 and k == "call")
    d.action = _sixmax_action(d)
    return d


def _open_action(d: Decision, allin: bool) -> str:
    """DECISIONS 63: a raise is the jam when all in or at least 40 bb, else the 3-bet to 3×
    or 4× the open by raise-to over the open."""
    if d.kind != "raise":
        return d.kind
    if allin or d.size >= JAM_BB - 1e-9:
        return "jam"
    mult = 3 if d.size / d.open_size <= 3.5 + 1e-9 else 4
    return f"3-bet to {mult * d.open:g}"


def _sixmax_action(d: Decision) -> str:
    """The spot's action: fold, its limp action, or the raise at the nearest size."""
    names = S.Spot(d.seat, d.limpers, d.ante).action_names()
    if d.kind == "fold":
        return "fold"
    if d.kind == "limp":
        return names[0] if d.seat == "BB" else names[1]
    raises = [n for n in names if " to " in n]
    return min(
        raises, key=lambda n: (abs(float(n.split(" to ")[1]) - d.size), float(n.split(" to ")[1]))
    )


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


# --- the leak finder (DECISIONS 63) -------------------------------------------------------

STAT_KEYS = ("hands", "vpip", "pfr", "limp_n", "limp_x", "iso_n", "iso_x")


def player_stats(records: Iterable[HandRecord]) -> dict[str, dict[str, int]]:
    """Per player name, counts for VPIP, PFR, limp % and fold to iso (DECISIONS 63)."""
    stats: dict[str, dict[str, int]] = {}
    for record in records:
        names = [p.name for p in record.players]
        sb, bb = record.blind_seats
        blinds = {sb, bb}
        raises, open_first = 0, True
        limpers, acted, iso_done, vpip, pfr = set(), set(), set(), set(), set()
        for who, kind, _ in record.preflop:
            s = stats.setdefault(names[who], dict.fromkeys(STAT_KEYS, 0))
            if raises == 0 and open_first and who not in blinds and who not in acted:
                s["limp_n"] += 1
                s["limp_x"] += kind == "call"
            if who in limpers and raises == 1 and who not in iso_done:
                iso_done.add(who)
                s["iso_n"] += 1
                s["iso_x"] += kind == "fold"
            if kind == "call":
                vpip.add(who)
                if raises == 0 and who not in blinds:
                    limpers.add(who)
            elif kind == "raise":
                vpip.add(who)
                pfr.add(who)
                raises += 1
            if kind != "fold":
                open_first = False
            acted.add(who)
        for i, name in enumerate(names):
            s = stats.setdefault(name, dict.fromkeys(STAT_KEYS, 0))
            s["hands"] += 1
            s["vpip"] += i in vpip
            s["pfr"] += i in pfr
    return stats


def rates(s: dict[str, int]) -> dict[str, float]:
    """The stats as shares; a stat with no chances is left out."""
    out = {"vpip": s["vpip"] / s["hands"], "pfr": s["pfr"] / s["hands"]}
    if s["limp_n"]:
        out["limp"] = s["limp_x"] / s["limp_n"]
    if s["iso_n"]:
        out["iso_fold"] = s["iso_x"] / s["iso_n"]
    return out


def type_of(s: dict[str, int], types: dict[str, S.PlayerType]) -> str:
    """The nearest fitted type over the stats, in percentage points; standard under 30 hands."""
    if s["hands"] < MIN_HANDS:
        return "standard"
    mine = rates(s)

    def distance(key: str) -> float:
        card = types[key].card
        return math.sqrt(sum((100 * (v - card[k])) ** 2 for k, v in mine.items()))

    return min(S.TYPE_KEYS[1:], key=distance)


def _majority(names: Iterable[str], kinds: dict[str, str]) -> str:
    """The most common type among the players, ties to the earliest; standard if none."""
    order = [kinds.get(n, "standard") for n in names]
    if not order:
        return "standard"
    counts = Counter(order)
    return max(order, key=lambda k: (counts[k], -order.index(k)))


class TypedGrader:
    """Answers under composed profiles, each equal to a fresh `sixmax.answer`."""

    def __init__(self, *, samples: int = S.SAMPLES, seed: int = 0) -> None:
        self.trainer = D.Trainer(
            S.load_profiles()["standard"], samples=samples, seed=seed, types=True
        )
        self._tables: dict = {}
        self._answers: dict = {}

    def spot(self, d: Decision) -> tuple[S.Spot | S.OpenSpot, S.Profile]:
        t = self.trainer
        if d.family == "open":
            op = t.opener(d.opener, d.opener_type)
            return S.OpenSpot(d.seat, op, d.open, d.ante), t.compose("standard", d.table_type)
        return S.Spot(d.seat, d.limpers, d.ante), t.compose(d.limpers_type, d.table_type)

    def answer(self, spot, profile: S.Profile, cls: int) -> S.Answer:
        key = (spot, profile.name, cls)
        if key not in self._answers:
            tkey = (spot, profile.name)
            if tkey not in self._tables:
                self._tables[tkey] = S.outcome_table(self.trainer._deal(spot, profile))
            d = self.trainer._deal(spot, profile)
            self._answers[key] = S.evaluate(d, cls, self._tables[tkey])
        return self._answers[key]


def review_typed(
    records: list[HandRecord], player: str, *, samples: int = S.SAMPLES, seed: int = 0
) -> tuple[list[Decision], dict[str, dict]]:
    """Every hand the player is in, graded on DECISIONS 60's scale against typed opponents,
    or skipped with its cause; and each player's stats and type."""
    types = S.load_types()
    stats = player_stats(records)
    kinds = {name: type_of(s, types) for name, s in stats.items()}
    grader = TypedGrader(samples=samples, seed=seed)
    out = []
    for record in records:
        d = classify(record, player, opens=True)
        if d is None:
            continue
        if d.cause is None:
            d.table_type = _majority(d.behind_names, kinds)
            d.limpers_type = _majority(d.limper_names, kinds)
            d.opener_type = (
                kinds.get(d.opener_name, "standard") if d.family == "open" else "standard"
            )
            spot, profile = grader.spot(d)
            a = grader.answer(spot, profile, class_index(d.hand))
            g = S.grade(a, d.action, spot.pot)
            d.grade, d.bb_lost, d.pct, d.best, d.tier = g.label, g.lost, g.pct, a.best, a.tier
        out.append(d)
    players = {
        name: {"hands": s["hands"], **rates(s), "type": kinds[name]} for name, s in stats.items()
    }
    return out, players


def opponent_type(d: Decision) -> str:
    if d.family == "open":
        return d.opener_type
    return d.limpers_type if d.limpers else d.table_type


def summarize_typed(decisions: list[Decision], players: dict[str, dict], player: str) -> dict:
    graded = [d for d in decisions if d.cause is None]
    causes = Counter(d.cause for d in decisions if d.cause)
    groups: dict[tuple, list[Decision]] = {}
    for d in graded:
        if d.grade in LEAK_LABELS:
            key = (d.family, d.seat, opponent_type(d), S.kind(d.action), S.kind(d.best))
            groups.setdefault(key, []).append(d)
    leaks = []
    for (family, seat, kind, answer, best), ds in groups.items():
        if len(ds) < LEAK_MIN:
            continue
        lesson = lessons.lesson_for(family, seat, ds[0].limpers, answer, best)
        leaks.append(
            {
                "family": family,
                "seat": seat,
                "opponent_type": kind,
                "answer": answer,
                "best": best,
                "count": len(ds),
                "bb_lost": sum(d.bb_lost for d in ds),
                "grades": {g: sum(d.grade == g for d in ds) for g in LEAK_LABELS},
                "lesson": lesson,
                "hands": sorted(ds, key=lambda d: -d.bb_lost)[:HANDS_SHOWN],
            }
        )
    leaks.sort(key=lambda x: (-x["bb_lost"], x["family"], x["seat"], x["opponent_type"]))
    others = {n: p for n, p in players.items() if n != player}
    return {
        "hands": len(decisions),
        "graded": len(graded),
        "by_family": {f: sum(d.family == f for d in graded) for f in ("sixmax", "open")},
        "skipped": {c: causes[c] for c in OPEN_CAUSES if causes[c]},
        "grades": {g: sum(d.grade == g for d in graded) for g in S.LABELS},
        "grades_by_family": {
            f: {g: sum(d.grade == g and d.family == f for d in graded) for g in S.LABELS}
            for f in ("sixmax", "open")
        },
        "bb_lost": sum(d.bb_lost for d in graded),
        "opponents": {
            "players": len(others),
            "by_type": dict(Counter(p["type"] for p in others.values()).most_common()),
            "standard_thin": sum(p["hands"] < MIN_HANDS for p in others.values()),
        },
        "leaks": leaks[:LEAKS_TYPED],
        "all_leaks": len(leaks),
    }


def _typed_spot(d: Decision) -> str:
    if d.family == "open":
        return f"{d.seat} vs {d.opener} open to {d.open_size:g} ({d.opener_type})"
    limpers = (
        f"{d.limpers} {d.limpers_type} limper{'s' * (d.limpers != 1)}" if d.limpers else "unopened"
    )
    return f"{d.seat}, {limpers}, {d.table_type} table, ante {d.ante:g}"


def hand_line(d: Decision) -> dict:
    """One example hand for the report, as plain values."""
    return {
        "source": d.source,
        "cards": d.cards,
        "spot": _typed_spot(d),
        "action": d.action,
        "best": d.best,
        "grade": d.grade,
        "bb_lost": d.bb_lost,
        "pct": d.pct,
    }


def describe_typed(parsed: ParseReport, summary: dict, player: str) -> list[str]:
    """The leak finder's report (DECISIONS 63)."""
    sources = [r.source for r in parsed.records] + [s for s, _ in parsed.failures]
    files = len({s.split("#")[0] for s in sources})
    g = summary["grades"]
    o = summary["opponents"]
    lines = [
        f"Leak finder for {player}, study only (DECISIONS 63). Graded on GTO Wizard's scale "
        "against each opponent's type, typed from these files.",
        f"Read {files} file{'s' * (files != 1)}: {parsed.found} hands, {parsed.parsed} parsed, "
        f"{len(parsed.failures)} failed. {player} is in {summary['hands']}.",
        f"Graded: {summary['graded']} ({summary['by_family']['sixmax']} unopened or limped, "
        f"{summary['by_family']['open']} facing an open). Skipped: "
        + (", ".join(f"{c} {n}" for c, n in summary["skipped"].items()) or "none")
        + ".",
        "Grades: "
        + ", ".join(f"{label} {g[label]}" for label in S.LABELS)
        + f"; {summary['bb_lost']:.2f} bb behind the best in all.",
        f"Opponents: {o['players']} typed: "
        + ", ".join(f"{k} {n}" for k, n in o["by_type"].items())
        + f" ({o['standard_thin']} with fewer than {MIN_HANDS} hands count as standard).",
        "",
        f"Leaks: Inaccuracy, Wrong or Blunder, at least {LEAK_MIN} alike, by bb lost:",
    ]
    if not summary["leaks"]:
        lines.append("  none")
    for n, leak in enumerate(summary["leaks"], 1):
        where = "facing an open" if leak["family"] == "open" else "unopened or limped"
        lines.append(
            f"  {n}. {leak['seat']}, {where}, against {leak['opponent_type']}: you {leak['answer']} "
            f"where the best is {leak['best']}. {leak['count']} hands, {leak['bb_lost']:.2f} bb. "
            f"Lesson: docs/lessons/{leak['lesson']}.md"
        )
        for d in leak["hands"]:
            lines.append(
                f"     {d.source}: {d.cards}, {_typed_spot(d)}: you {d.action}; best {d.best}; "
                f"{d.grade}, {d.bb_lost:.2f} bb ({d.pct:.0f}% of the pot)"
            )
    return lines
