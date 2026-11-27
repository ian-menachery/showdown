r"""Writes Gate W2's fixture (DECISIONS 63): fictional six-handed hands and their labels.

Run once from the repo root, before any of step 4's review code exists:

    .venv\Scripts\python -I tests\fixtures\sixmax_review_w2\make_fixture.py

Every hand is built here from a scenario for Hero (the spot and Hero's action) and simple
seeded tendencies for the five opponents. The labels come from this script's own
construction and its own counts, not from the review code:
- per hand: Hero's family, seat, limpers, ante, opener and open bucket, the engine action
  and the hand class, or the skip cause;
- per player: hands, VPIP, PFR, limp % and fold to iso (DECISIONS 63's definitions), and the
  nearest type by the type cards in data/sixmax_types.json, or standard under 30 hands.

Blinds are 1/2 chips, so 1 bb = 2 chips; stacks are 200 chips (100 bb); an ante is 1 chip
(0.5 bb). Hands stop after Hero's first decision has been answered by the table, or when
Hero would face a second decision. PHH seats: p1 SB, p2 BB, p3 UTG, p4 HJ, p5 CO, p6 BTN.
"""

import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SEATS = ("SB", "BB", "UTG", "HJ", "CO", "BTN")
ORDER = (2, 3, 4, 5, 0, 1)  # preflop order of action, as PHH player indices
RANKS = "23456789TJQKA"
OPPONENTS = ("Ned", "Sue", "Mo", "Tom")
"""Designed: Ned folds and opens rarely; Sue limps and calls; Mo raises and calls a lot; Tom
opens a fair share. The sixth seat is Fay for hands 1 to 20 and Lou after: both under 30."""


def hand_class(cards: str) -> str:
    a, b = cards[:2], cards[2:]
    hi, lo = sorted((a, b), key=lambda c: RANKS.index(c[0]), reverse=True)
    if hi[0] == lo[0]:
        return hi[0] * 2
    return hi[0] + lo[0] + ("s" if hi[1] == lo[1] else "o")


# --- the scenarios: (kind, hero seat, hero cards, ante, details, hero action) ------------
# kind "open": details (opener seat, opener, open in bb); hero action f, c, 3x, 4x or jam.
# kind "limped": details [(seat, limper), ...]; hero action f, l or r<bb>.
# kind "unopened": details (); hero action f, l or r<bb>.
# kinds "threebet", "called", "size": skips facing a raise (details as "open", plus a
# second actor for the first two).
SCENARIOS = [
    ("open", "BTN", "AhJd", 0, ("CO", "Mo", 2.5), "3x"),
    ("open", "BTN", "9s9h", 0, ("CO", "Tom", 2.5), "c"),
    ("open", "BB", "Kh7d", 0, ("BTN", "Mo", 2.5), "c"),
    ("open", "BB", "7c2d", 0.5, ("UTG", "Ned", 3.0), "f"),
    ("open", "SB", "AsKs", 0, ("BTN", "Sue", 2.5), "4x"),
    ("open", "CO", "QsJs", 0, ("UTG", "Ned", 2.5), "f"),
    ("open", "HJ", "QhQd", 0.5, ("UTG", "Tom", 3.0), "3x"),
    ("open", "BTN", "AdAc", 0, ("HJ", "Mo", 3.0), "jam"),
    ("open", "SB", "Td9d", 0, ("CO", "Tom", 2.5), "f"),
    ("open", "BB", "AhTc", 0, ("SB", "Mo", 3.0), "3x"),
    ("open", "CO", "KcQc", 0.5, ("HJ", "Sue", 2.5), "c"),
    ("open", "BTN", "6h5h", 0, ("UTG", "Tom", 2.5), "c"),
    ("open", "BB", "JhTh", 0, ("CO", "Ned", 2.5), "c"),
    ("open", "SB", "8s8d", 0.5, ("HJ", "Mo", 3.0), "3x"),
    ("open", "BTN", "KdJc", 0, ("CO", "Sue", 3.0), "4x"),
    ("open", "BB", "As5s", 0, ("BTN", "Tom", 2.5), "3x"),
    ("threebet", "BTN", "AsQh", 0, ("UTG", "Tom", 2.5, "CO", "Mo"), "f"),
    ("called", "BB", "9c8c", 0, ("CO", "Mo", 2.5, "BTN", "Sue"), "c"),
    ("size", "BTN", "KsTs", 0, ("CO", "Mo", 4.0), "f"),
    ("limped", "BTN", "KhJh", 0, [("CO", "Sue")], "r5"),
    ("limped", "BTN", "7d6d", 0.5, [("HJ", "Sue"), ("CO", "Mo")], "l"),
    ("limped", "CO", "AdQs", 0, [("UTG", "Sue")], "r5"),
    ("limped", "SB", "Qc8d", 0, [("HJ", "Sue"), ("BTN", "Mo")], "l"),
    ("limped", "BB", "AcKd", 0, [("CO", "Sue")], "r6"),
    ("limped", "HJ", "4c4d", 0.5, [("UTG", "Sue")], "l"),
    ("limped", "BTN", "Jd4s", 0, [("UTG", "Mo"), ("HJ", "Sue"), ("CO", "Tom")], "f"),
    ("limped", "BB", "8h3c", 0, [("UTG", "Sue"), ("BTN", "Mo")], "l"),
    ("unopened", "BTN", "Kc8s", 0, (), "r2.5"),
    ("unopened", "UTG", "AhKh", 0, (), "r3"),
    ("unopened", "HJ", "9d7c", 0, (), "f"),
    ("unopened", "CO", "Ts9s", 0.5, (), "r2.5"),
    ("unopened", "SB", "Kd5c", 0, (), "l"),
    ("unopened", "UTG", "2c2h", 0.5, (), "l"),
    ("unopened", "SB", "QdJh", 0, (), "r3"),
    ("unopened", "BTN", "8c3d", 0, (), "f"),
    ("unopened", "CO", "AsTd", 0, (), "r4"),
    ("unopened", "HJ", "JsJc", 0, (), "r2.5"),
    ("unopened", "UTG", "Th8h", 0, (), "f"),
    ("open", "CO", "AcJc", 0, ("UTG", "Mo", 2.5), "3x"),
    ("open", "BTN", "QcTd", 0.5, ("HJ", "Tom", 2.5), "f"),
    ("open", "BB", "6c6s", 0, ("UTG", "Sue", 2.5), "c"),
    ("limped", "BTN", "As9h", 0, [("UTG", "Sue"), ("CO", "Ned")], "r6"),
    ("unopened", "CO", "Kh9h", 0, (), "r3"),
    ("open", "SB", "Ah4h", 0, ("BTN", "Mo", 2.5), "jam"),
    ("limped", "CO", "QhTc", 0, [("HJ", "Mo")], "r5"),
]
PS_SCENARIOS = [  # the PokerStars file: hands that end preflop with everyone folding
    ("open", "BTN", "KhQh", 0, ("CO", "Tom", 2.5), "3x"),
    ("unopened", "BTN", "Ad7c", 0, (), "r2.5"),
    ("limped", "CO", "AhJh", 0, [("HJ", "Sue")], "r5"),
]


# --- a small preflop table --------------------------------------------------------------


class Table:
    def __init__(self, names: list[str], ante: int, rng: random.Random) -> None:
        self.names, self.ante, self.rng = names, ante, rng
        self.contrib = [1, 2, 0, 0, 0, 0]
        self.level, self.raises = 2, 0
        self.folded = [False] * 6
        self.acted = [False] * 6
        self.limpers: list[int] = []
        self.actions: list[tuple[int, str, int]] = []
        self.opener: int | None = None

    def act(self, i: int, kind: str, to: int = 0) -> None:
        if kind == "f":
            self.folded[i] = True
        elif kind == "cc":
            if self.raises == 0 and i >= 2 and self.contrib[i] < self.level:
                self.limpers.append(i)
            self.contrib[i] = self.level
        else:
            if self.raises == 0 and not self.limpers:
                self.opener = i
            self.raises += 1
            self.level = to
            self.contrib[i] = to
            self.acted = [False] * 6
        self.acted[i] = True
        self.actions.append((i, kind, to))

    def pending(self) -> list[int]:
        """Players still to act in this round, in order, starting after the last actor."""
        start = (ORDER.index(self.actions[-1][0]) + 1) if self.actions else 0
        out = []
        for k in range(6):
            i = ORDER[(start + k) % 6]
            if self.folded[i]:
                continue
            if not self.acted[i] or self.contrib[i] < self.level:
                out.append(i)
        return out

    def tendency(self, i: int) -> tuple[str, int]:
        """A seeded answer for an opponent, by name and situation."""
        name, r = self.names[i], self.rng.random()
        facing = self.level - self.contrib[i]
        if self.raises == 0:  # limps only
            if i == 1:
                return ("cbr", 8) if name == "Mo" and r < 0.3 else ("cc", 0)
            if name == "Sue" and r < 0.7:
                return ("cc", 0)
            return ("f", 0)
        if i in self.limpers and self.raises == 1:  # a limper facing an iso
            calls = {"Sue": 0.7, "Mo": 0.5}.get(name, 0.0)
            return ("cc", 0) if r < calls else ("f", 0)
        if i == self.opener and self.raises == 2:  # the opener facing a 3-bet
            calls = {"Sue": 0.9, "Mo": 0.5, "Tom": 0.4}.get(name, 0.0)
            return ("cc", 0) if r < calls else ("f", 0)
        if self.raises == 1 and facing <= 12:
            calls = {"Sue": 0.6, "Mo": 0.4, "Tom": 0.15}.get(name, 0.0)
            return ("cc", 0) if r < calls else ("f", 0)
        return ("f", 0)


def build(spec, names: list[str], rng: random.Random, fold_after: bool = False):
    """(PHH actions after the deal, Hero's label) for one scenario. With `fold_after`,
    everyone folds after Hero (the PokerStars hands)."""
    kind, hero_seat, _, ante, details, hero_action = spec
    hero = SEATS.index(hero_seat)
    t = Table(names, 1 if ante else 0, rng)  # the 0.5 bb ante is 1 chip
    script: dict[int, tuple[str, int]] = {}
    label: dict = {"seat": hero_seat, "ante": 0.5 if ante else 0.0}
    if kind in ("open", "threebet", "called", "size"):
        seat, _, size = details[:3]
        script[SEATS.index(seat)] = ("cbr", round(2 * size))
        if kind == "threebet":
            script[SEATS.index(details[3])] = ("cbr", round(2 * size * 3))
        if kind == "called":
            script[SEATS.index(details[3])] = ("cc", 0)
    elif kind == "limped":
        for seat, _ in details:
            script[SEATS.index(seat)] = ("cc", 0)
    hero_done = False
    while True:
        todo = t.pending()
        if not todo:
            break
        i = todo[0]
        if i == hero:
            if hero_done:
                break  # Hero would face a second decision: the hand stops here
            hero_done = True
            move = _hero_move(t, hero_action, label, kind, details)
        elif not hero_done:
            move = script.get(i, ("f", 0))
        else:
            move = ("f", 0) if fold_after else t.tendency(i)
        t.act(i, *move)
        if sum(not f for f in t.folded) == 1:
            break
    if kind in ("threebet", "called", "size"):
        label["cause"] = {
            "threebet": "raised before you",
            "called": "open called before you",
            "size": "open size",
        }[kind]
    actions = [f"p{i + 1} f" if k == "f" else f"p{i + 1} cc" if k == "cc" else f"p{i + 1} cbr {to}"
               for i, k, to in t.actions]
    return actions, label | {"_table": t}


def _hero_move(t: Table, action: str, label: dict, kind: str, details) -> tuple[str, int]:
    hero_limps = len(t.limpers)
    if kind in ("open", "threebet", "called", "size"):
        seat, _, size = details[:3]
        bucket = 3.0 if size >= 2.75 else 2.5
        label |= {"family": "open", "opener": seat, "open": bucket}
        if action == "f":
            label["action"] = "fold"
            return ("f", 0)
        if action == "c":
            label["action"] = "call"
            return ("cc", 0)
        if action == "jam":
            label["action"] = "jam"
            return ("cbr", 200 - t.ante)
        mult = 3 if action == "3x" else 4
        label["action"] = f"3-bet to {mult * bucket:g}"
        return ("cbr", round(2 * mult * size))
    label |= {"family": "sixmax", "limpers": hero_limps}
    seat = label["seat"]
    if action == "f":
        label["action"] = "fold"
        return ("f", 0)
    if action == "l":
        if seat == "BB":
            label["action"] = "check"
        elif seat == "SB":
            label["action"] = "complete"
        else:
            label["action"] = "limp" if hero_limps == 0 else "overlimp"
        return ("cc", 0)
    to = float(action[1:])
    verb = "open" if hero_limps == 0 else ("raise" if seat == "BB" else "iso")
    label["action"] = f"{verb} to {to:g}"
    return ("cbr", round(2 * to))


# --- the stats, counted from the construction ----------------------------------------------


def count(stats: dict, names: list[str], actions: list[tuple[int, str, int]]) -> None:
    seen_raise, limpers = 0, set()
    acted: set[int] = set()
    vpip, pfr = set(), set()
    first_in_open = True
    for i, kind, _ in actions:
        s = stats.setdefault(names[i], dict.fromkeys(
            ("hands", "vpip", "pfr", "limp_n", "limp_x", "iso_n", "iso_x"), 0))
        if seen_raise == 0 and first_in_open and i >= 2 and i not in acted:
            s["limp_n"] += 1
            s["limp_x"] += kind == "cc"
        if i in limpers and seen_raise == 1 and i not in _iso_counted:
            _iso_counted.add(i)
            s["iso_n"] += 1
            s["iso_x"] += kind == "f"
        if kind == "cc" and not (i == 1 and seen_raise == 0):
            vpip.add(i)
        if kind == "cbr":
            vpip.add(i)
            pfr.add(i)
        if kind != "f":
            first_in_open = False
        if kind == "cc" and seen_raise == 0 and i >= 2:
            limpers.add(i)
        if kind == "cbr":
            seen_raise += 1
        acted.add(i)
    for i, name in enumerate(names):
        s = stats.setdefault(name, dict.fromkeys(
            ("hands", "vpip", "pfr", "limp_n", "limp_x", "iso_n", "iso_x"), 0))
        s["hands"] += 1
        s["vpip"] += i in vpip
        s["pfr"] += i in pfr


_iso_counted: set[int] = set()


def nearest(s: dict, cards: dict) -> str:
    if s["hands"] < 30:
        return "standard"
    mine = {"vpip": s["vpip"] / s["hands"], "pfr": s["pfr"] / s["hands"]}
    if s["limp_n"]:
        mine["limp"] = s["limp_x"] / s["limp_n"]
    if s["iso_n"]:
        mine["iso_fold"] = s["iso_x"] / s["iso_n"]
    best, best_d = None, math.inf
    for key in ("nit", "tag", "lag", "maniac", "weak-tight", "station"):
        d = math.sqrt(sum((100 * (v - cards[key][k])) ** 2 for k, v in mine.items()))
        if d < best_d:
            best, best_d = key, d
    return best


# --- writing ----------------------------------------------------------------------------


def seat_names(n: int, spec) -> list[str]:
    """Hero and the scenario's actors at their seats; the others fill the rest in turn."""
    kind, hero_seat, _, _, details, _ = spec
    sixth = "Fay" if n <= 20 else "Lou"
    names: list[str | None] = [None] * 6
    names[SEATS.index(hero_seat)] = "Hero"
    fixed = []
    if kind == "limped":
        fixed = list(details)
    elif kind in ("open", "threebet", "called", "size"):
        fixed = [(details[0], details[1])] + ([(details[3], details[4])] if len(details) > 3 else [])
    for seat, name in fixed:
        names[SEATS.index(seat)] = name
    rest = [p for p in (*OPPONENTS, sixth) if p not in names]
    rest = rest[n % len(rest):] + rest[: n % len(rest)]
    for k in range(6):
        if names[k] is None:
            names[k] = rest.pop(0)
    return names


def deal_others(hero_cards: str, rng: random.Random) -> list[str]:
    deck = [r + s for r in RANKS for s in "cdhs" if r + s not in (hero_cards[:2], hero_cards[2:])]
    rng.shuffle(deck)
    return [deck[2 * k] + deck[2 * k + 1] for k in range(5)]


def phh(names, cards, ante, actions) -> str:
    deals = [f"'d dh p{k + 1} {cards[k]}'" for k in range(6)]
    acts = ", ".join(deals + [f"'{a}'" for a in actions])
    a = ante
    return (
        "variant = 'NT'\nante_trimming_status = true\n"
        f"antes = [{a}, {a}, {a}, {a}, {a}, {a}]\n"
        "blinds_or_straddles = [1, 2, 0, 0, 0, 0]\nmin_bet = 2\n"
        "starting_stacks = [200, 200, 200, 200, 200, 200]\n"
        f"actions = [{acts}]\n"
        "players = [" + ", ".join(f"'{p}'" for p in names) + "]\n"
    )


def pokerstars(number: int, names, cards, actions) -> str:
    """One PokerStars hand, $0.01/$0.02, that ends preflop with everyone folding."""
    seat_of = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6}
    lines = [
        f"PokerStars Hand #{number}: Hold'em No Limit ($0.01/$0.02 USD) - 2026/11/27 12:0{number % 10}:00 ET",
        "Table 'Review' 6-max Seat #6 is the button",
    ]
    lines += [f"Seat {seat_of[k]}: {names[k]} ($2 in chips)" for k in range(6)]
    lines += [f"{names[0]}: posts small blind $0.01", f"{names[1]}: posts big blind $0.02",
              "*** HOLE CARDS ***", f"Dealt to Hero [{cards[names.index('Hero')][:2]} {cards[names.index('Hero')][2:]}]"]
    level, contrib = 2, [1, 2, 0, 0, 0, 0]
    last = None
    for i, kind, to in actions:
        if kind == "f":
            lines.append(f"{names[i]}: folds")
        elif kind == "cc":
            lines.append(f"{names[i]}: calls ${(level - contrib[i]) / 100:.2f}")
            contrib[i] = level
        else:
            lines.append(f"{names[i]}: raises ${(to - level) / 100:.2f} to ${to / 100:.2f}")
            level, contrib[i], last = to, to, i
    second = max(c for k, c in enumerate(contrib) if k != last)
    pot = sum(contrib) - (level - second)
    lines += [f"Uncalled bet (${(level - second) / 100:.2f}) returned to {names[last]}",
              f"{names[last]} collected ${pot / 100:.2f} from pot", "*** SUMMARY ***",
              f"Total pot ${pot / 100:.2f} | Rake $0"]
    return "\n".join(lines) + "\n\n\n\n"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    cards_by_type = {k: v["card"] for k, v in json.loads(
        (ROOT / "data" / "sixmax_types.json").read_text(encoding="utf-8"))["types"].items()}
    rng = random.Random(20261127)
    stats: dict = {}
    hands: dict = {}
    ps_text = ""
    for n, spec in enumerate(SCENARIOS + PS_SCENARIOS, 1):
        names = seat_names(n, spec)
        others = iter(deal_others(spec[2], rng))
        cards = [spec[2] if p == "Hero" else next(others) for p in names]
        _iso_counted.clear()
        actions, label = build(spec, names, rng, fold_after=n > len(SCENARIOS))
        table = label.pop("_table")
        count(stats, names, table.actions)
        label["hand"] = hand_class(spec[2])
        if "cause" in label:
            label = {"cause": label["cause"]}
        if n <= len(SCENARIOS):
            key = f"w{n:02d}"
            chips = 1 if spec[3] else 0  # the 0.5 bb ante is 1 chip
            (HERE / f"{key}.phh").write_text(phh(names, cards, chips, actions), encoding="utf-8")
        else:
            k = n - len(SCENARIOS)
            key = f"session#{k}"
            ps_text += pokerstars(3000 + k, names, cards, table.actions)
        hands[key] = label
    (HERE / "session.txt").write_text(ps_text, encoding="utf-8")
    players = {}
    for name, s in sorted(stats.items()):
        entry = {"hands": s["hands"], "vpip": s["vpip"] / s["hands"], "pfr": s["pfr"] / s["hands"]}
        if s["limp_n"]:
            entry["limp"] = s["limp_x"] / s["limp_n"]
        if s["iso_n"]:
            entry["iso_fold"] = s["iso_x"] / s["iso_n"]
        entry["type"] = nearest(s, cards_by_type)
        players[name] = entry
    out = ["# Gate W2 (DECISIONS 63): labels written by make_fixture.py from its own construction.",
           "# Hands: Hero's family, seat, limpers, ante, opener, open bucket, engine action and",
           "# class, or the skip cause. Players: DECISIONS 63's stats and type.", ""]
    for key, label in hands.items():
        out.append(f'["{key}"]')
        out += [f"{k} = {json.dumps(v)}" for k, v in label.items()]
        out.append("")
    for name, entry in players.items():
        out.append(f'["player.{name}"]')
        out += [f"{k} = {json.dumps(v)}" for k, v in entry.items()]
        out.append("")
    (HERE / "labels.toml").write_text("\n".join(out), encoding="utf-8")
    for name, entry in players.items():
        print(name, entry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
