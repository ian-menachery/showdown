"""Play sessions: the game logic behind the play page, independent of HTTP (DECISIONS 23, 24).

A session plays hands between a human seat and a bot. Every response is a
plain dict for the JSON API. It never contains the bot's cards before the hand
is over.
"""

from __future__ import annotations

import json
import random
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from showdown import lessons
from showdown import sixmax as S
from showdown import sixmax_drill as D
from showdown.bot.policy import Grade, LeducStrategy, PushFoldStrategy, act
from showdown.engine.pokerkit_adapter import HandResult, PushFoldHand, deal_cards
from showdown.equity.cards import ALL_COMBOS, CLASS_NAMES, card_str, cards_str, class_of
from showdown.exploit import typed_spot
from showdown.games.base import CHANCE, TERMINAL
from showdown.games.leduc import CALL, DECK, FOLD, RAISE, LeducState, card_name

RANDOM_DEPTHS = (2, 20)


class PlayError(ValueError):
    """A request that does not fit the session's state."""


def _summary_line(total: float, count: int) -> float:
    return total / count if count else 0.0


@dataclass
class PushFoldSession:
    strategy: PushFoldStrategy
    seat: str = "alternate"
    """"sb", "bb" or "alternate"."""
    depth_mode: str = "fixed"
    """"fixed" or "random" (an integer from 2 to 20 bb each hand)."""
    depth: int = 10
    rng: random.Random = field(default_factory=random.Random)
    hands: int = 0
    decisions: int = 0
    mistakes: int = 0
    loss: float = 0.0
    net: float = 0.0
    _hand: PushFoldHand | None = None
    _human: str = "sb"
    _events: list[dict] = field(default_factory=list)
    _grades: list[dict] = field(default_factory=list)
    _result: HandResult | None = None

    def __post_init__(self) -> None:
        if self.seat not in ("sb", "bb", "alternate"):
            raise PlayError("seat must be sb, bb or alternate")
        if self.depth_mode not in ("fixed", "random"):
            raise PlayError("depth mode must be fixed or random")
        if not 1 <= int(self.depth) <= 20:
            raise PlayError("depth must be an integer from 1 to 20 bb")
        self.depth = int(self.depth)

    # --- hand flow --------------------------------------------------------------

    def new_hand(self) -> dict:
        if self._hand is not None and self._result is None:
            raise PlayError("finish the current hand first")
        if self.seat == "alternate":
            self._human = "sb" if self.hands % 2 == 0 else "bb"
        else:
            self._human = self.seat
        depth = self.depth if self.depth_mode == "fixed" else self.rng.randint(*RANDOM_DEPTHS)
        self._hand = PushFoldHand(depth, deal_cards(self.rng))
        self.hands += 1
        self._events, self._grades, self._result = [], [], None
        self._run_bot()
        return self.view()

    def act(self, action: str) -> dict:
        hand = self._hand
        if hand is None or self._result is not None or hand.to_act != self._human:
            raise PlayError("it is not your turn")
        if action not in ("fold", "all-in"):
            raise PlayError("action must be fold or all-in")
        allin = action == "all-in"
        cls = hand.sb_class if self._human == "sb" else hand.bb_class
        grade = self.strategy.grade(hand.stack, self._human, cls, allin)
        self._record(grade)
        if self._human == "sb":
            hand.sb_act(allin)
        else:
            hand.bb_act(allin)
        self._events.append({"who": "you", "seat": self._human, "action": action})
        self._run_bot()
        return self.view()

    def _record(self, grade: Grade) -> None:
        self.decisions += 1
        self.loss += grade.loss
        self.mistakes += grade.mistake
        self._grades.append(
            {
                "ev_fold": grade.ev_fold,
                "ev_allin": grade.ev_allin,
                "chosen": grade.chosen,
                "loss": grade.loss,
                "nash_allin": grade.nash_allin,
                "mistake": grade.mistake,
            }
        )

    def _run_bot(self) -> None:
        hand = self._hand
        assert hand is not None
        while hand.to_act is not None and hand.to_act != self._human:
            if hand.to_act == "sb":
                jam = act(self.strategy.push_prob(hand.stack, hand.sb_class), self.rng)
                hand.sb_act(jam)
                self._bot_event("sb", jam)
            else:
                call = act(self.strategy.call_prob(hand.stack, hand.bb_class), self.rng)
                hand.bb_act(call)
                self._bot_event("bb", call)
        if hand.to_act is None:
            self._result = hand.finish()
            sign = 1 if self._human == "sb" else -1
            self.net += sign * self._result.sb_net

    def _bot_event(self, seat: str, allin: bool) -> None:
        self._events.append({"who": "bot", "seat": seat, "action": "all-in" if allin else "fold"})

    # --- views ------------------------------------------------------------------

    def summary(self) -> dict:
        return {
            "game": "pushfold",
            "hands": self.hands,
            "decisions": self.decisions,
            "mistakes": self.mistakes,
            "bb_lost": self.loss,
            "bb_lost_per_decision": _summary_line(self.loss, self.decisions),
            "net_bb": self.net,
        }

    def view(self) -> dict:
        hand = self._hand
        if hand is None:
            return {"game": "pushfold", "summary": self.summary()}
        mine = hand.sb_cards if self._human == "sb" else hand.bb_cards
        cls = hand.sb_class if self._human == "sb" else hand.bb_class
        view: dict = {
            "game": "pushfold",
            "hand": self.hands,
            "depth": hand.stack,
            "seat": self._human,
            "cards": [card_str(c) for c in mine],
            "class": CLASS_NAMES[cls],
            "your_turn": self._result is None and hand.to_act == self._human,
            "events": list(self._events),
            "grades": list(self._grades),
            "summary": self.summary(),
        }
        if self._result is not None:
            r = self._result
            bot = r.bb_cards if self._human == "sb" else r.sb_cards
            sign = 1 if self._human == "sb" else -1
            view["result"] = {
                "bot_cards": [card_str(c) for c in bot],
                "board": [card_str(c) for c in r.board],
                "net_bb": sign * r.sb_net,
            }
        return view


_ACTION_NAMES = {FOLD: "fold", CALL: "call", RAISE: "raise"}


def _labels(state: LeducState) -> dict[str, str]:
    """Display names: a call with nothing to call is a check, a raise into nothing is a bet."""
    facing = state.contrib[state.to_act] < state.contrib[1 - state.to_act]
    return {
        "fold": "fold",
        "call": "call" if facing else "check",
        "raise": "raise" if facing else "bet",
    }


@dataclass
class LeducSession:
    strategy: LeducStrategy
    seat: str = "alternate"
    """"first" (player 0, acts first), "second" or "alternate"."""
    rng: random.Random = field(default_factory=random.Random)
    hands: int = 0
    net: float = 0.0
    _state: LeducState | None = None
    _deal: tuple[int, int, int] = (0, 0, 0)
    _human: int = 0
    _events: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.seat not in ("first", "second", "alternate"):
            raise PlayError("seat must be first, second or alternate")

    def new_hand(self) -> dict:
        if self._state is not None and self._state.current_player() != TERMINAL:
            raise PlayError("finish the current hand first")
        if self.seat == "alternate":
            self._human = self.hands % 2
        else:
            self._human = 0 if self.seat == "first" else 1
        a, b, public = self.rng.sample(DECK, 3)
        self._deal = (a, b, public)
        self._state = LeducState().child(a).child(b)
        self.hands += 1
        self._events = []
        self._advance()
        return self.view()

    def act(self, action: str) -> dict:
        state = self._state
        if state is None or state.current_player() != self._human:
            raise PlayError("it is not your turn")
        ids = {name: a for a, name in _ACTION_NAMES.items() if a in state.legal_actions()}
        if action not in ids:
            raise PlayError(f"legal actions: {', '.join(ids)}")
        label = _labels(state)[action]
        self._state = state.child(ids[action])
        self._events.append({"who": "you", "action": label})
        self._advance()
        return self.view()

    def _advance(self) -> None:
        """Deal the public card and play the bot until the human acts or the hand ends."""
        while True:
            state = self._state
            assert state is not None
            player = state.current_player()
            if player == CHANCE:
                self._state = state.child(self._deal[2])
                dealt = card_name(self._deal[2])
                self._events.append({"who": "dealer", "action": f"public card {dealt}"})
            elif player == TERMINAL:
                self.net += state.returns()[self._human]
                return
            elif player == self._human:
                return
            else:
                actions = {a: _ACTION_NAMES[a] for a in state.legal_actions()}
                label = _labels(state)
                choice = self.strategy.choose(state.information_state(), actions, self.rng)
                self._state = state.child(choice)
                self._events.append({"who": "bot", "action": label[_ACTION_NAMES[choice]]})

    def summary(self) -> dict:
        return {
            "game": "leduc",
            "hands": self.hands,
            "net_chips": self.net,
            "net_per_hand": _summary_line(self.net, self.hands),
        }

    def view(self) -> dict:
        state = self._state
        if state is None:
            return {"game": "leduc", "summary": self.summary()}
        done = state.current_player() == TERMINAL
        view: dict = {
            "game": "leduc",
            "hand": self.hands,
            "seat": "first" if self._human == 0 else "second",
            "card": card_name(state.private[self._human]),
            "public": card_name(state.public) if state.public is not None else None,
            "pot": sum(state.contrib),
            "your_turn": not done and state.current_player() == self._human,
            "events": list(self._events),
            "summary": self.summary(),
        }
        if view["your_turn"]:
            labels = _labels(state)
            view["actions"] = [
                {"action": _ACTION_NAMES[a], "label": labels[_ACTION_NAMES[a]]}
                for a in state.legal_actions()
            ]
        if done:
            view["result"] = {
                "bot_card": card_name(state.private[1 - self._human]),
                "net_chips": state.returns()[self._human],
                "folded": state.folded is not None,
            }
        return view


# --- the trainer page (DECISIONS 62) ------------------------------------------------

FAMILIES = ("sixmax", "open", "pushfold")
FAMILY_NAMES = {
    "sixmax": "Six-max, unopened or limped",
    "open": "Six-max, facing an open",
    "pushfold": "Push/fold, tournament-style (no ICM)",
}
PUSHFOLD_DEPTHS = (2, 20)
GATE_Z_NOTE = (
    "Facing an open, the engine still leans towards 3-betting (Gates Z and Z2 FAIL, bar 3): "
    "trust folds, calls and value 3-bets; read a close 3-bet with a weak hand as a fold."
)


@dataclass
class _Drill:
    family: str
    combo: tuple
    spot: object
    """A sixmax `Spot` or `OpenSpot`, or an `exploit.TypedSpot`."""
    drill: D.Drill | None = None
    villain: str = ""
    """The push/fold villain's type."""
    seconds: float = 0.0


@dataclass
class SixmaxSession:
    """Drills from the three families, graded on DECISIONS 60's scale. Every response is a
    plain dict for the JSON API; each answered drill is one line in the log."""

    pushfold: PushFoldStrategy
    families: tuple[str, ...] = FAMILIES
    seat: str | None = None
    limpers: int | None = None
    ante: float | None = None
    kind: str | None = None
    """One type for every opponent role, or None for random types."""
    seed: int = 0
    log_dir: Path = D.LOG_DIR
    samples: int = S.SAMPLES
    drills: int = 0
    rows: list[dict] = field(default_factory=list)
    _current: _Drill | None = None
    _result: dict | None = None

    def __post_init__(self) -> None:
        if not self.families or any(f not in FAMILIES for f in self.families):
            raise PlayError("family must be sixmax, open or pushfold")
        if self.seat is not None and self.seat not in S.SEATS:
            raise PlayError("seat must be UTG, HJ, CO, BTN, SB or BB")
        if self.limpers is not None and not 0 <= self.limpers <= 3:
            raise PlayError("limpers must be 0 to 3")
        if self.ante is not None and self.ante not in D.ANTES:
            raise PlayError("ante must be 0 or 0.5")
        if self.kind is not None and self.kind not in S.TYPE_KEYS:
            raise PlayError("type must be one of " + ", ".join(S.TYPE_KEYS))
        shapes = tuple(
            (s, k) for s, k in D.SHAPES if self.seat in (None, s) and self.limpers in (None, k)
        )
        pairs = tuple(p for p in D.OPEN_PAIRS if self.seat in (None, p[0]))
        usable = {
            "sixmax": bool(shapes),
            "open": bool(pairs) and self.limpers in (None, 0),
            "pushfold": self.seat in (None, "SB", "BB") and self.limpers in (None, 0),
        }
        self.families = tuple(f for f in self.families if usable[f])
        if not self.families:
            raise PlayError("no drill fits these filters")
        k = self.kind
        self.trainer = D.Trainer(
            S.load_profiles()["standard"],
            ante=self.ante,
            samples=self.samples,
            seed=self.seed,
            types=True,
            limpers_type=k,
            table_type=k,
            opener_type=k,
            shapes=shapes or D.SHAPES,
            pairs=pairs or D.OPEN_PAIRS,
        )
        self.types = self.trainer._types
        self.rng = np.random.default_rng([self.seed, 62])
        self.log_dir = Path(self.log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / f"{datetime.now():%Y%m%d-%H%M%S-%f}-trainer.jsonl"

    # --- drills ---------------------------------------------------------------------

    def new_hand(self) -> dict:
        if self._current is not None and self._result is None:
            raise PlayError("answer the current drill first")
        start = time.perf_counter()
        family = self.families[self.rng.integers(len(self.families))]
        if family == "sixmax":
            drill = self.trainer.next()
            current = _Drill(family, drill.combo, drill.spot, drill)
        elif family == "open":
            drill = self.trainer.next_open()
            current = _Drill(family, drill.combo, drill.spot, drill)
        else:
            depth = int(self.rng.integers(PUSHFOLD_DEPTHS[0], PUSHFOLD_DEPTHS[1] + 1))
            hero = self.seat.lower() if self.seat else ("sb", "bb")[self.rng.integers(2)]
            villain = self.kind or S.TYPE_KEYS[self.rng.integers(len(S.TYPE_KEYS))]
            combo = ALL_COMBOS[self.rng.integers(len(ALL_COMBOS))]
            p = self.pushfold
            spot = typed_spot(
                p.solution, p.matrix, depth, hero, self.types[villain], class_of(combo)
            )
            current = _Drill(family, combo, spot, villain=villain)
        current.seconds = time.perf_counter() - start
        self._current, self._result = current, None
        self.drills += 1
        return self.view()

    def _actions(self) -> list[str]:
        c = self._current
        return list(c.spot.ev) if c.family == "pushfold" else c.drill.answer.actions

    def act(self, action: str) -> dict:
        c = self._current
        if c is None or self._result is not None:
            raise PlayError("deal a drill first")
        if action not in self._actions():
            raise PlayError("actions: " + ", ".join(self._actions()))
        cls = class_of(c.combo)
        if c.family == "pushfold":
            result = self._grade_pushfold(c, action)
        else:
            result = self._grade_sixmax(c, action, cls)
        self._result = result
        row = self._row(c, action, result)
        with self.log_path.open("a", encoding="utf-8", newline="\n") as log:
            log.write(json.dumps(row) + "\n")
        self.rows.append(row)
        return self.view()

    def _grade_sixmax(self, c: _Drill, action: str, cls: int) -> dict:
        a, spot, d = c.drill.answer, c.spot, c.drill
        g = S.grade(a, action, spot.pot)
        if c.family == "open":
            std_spot = S.OpenSpot(
                spot.seat, self.trainer.opener(spot.opener.seat, "standard"), spot.size, spot.ante
            )
            limpers = 0
        else:
            std_spot, limpers = spot, spot.limpers
        std = self.trainer.answer(std_spot, self.trainer.compose("standard", "standard"), cls)
        std_ev = float(std.ev[std.actions.index(std.best)])
        lesson = lessons.lesson_for(c.family, spot.seat, limpers, S.kind(action), S.kind(a.best))
        return {
            "label": g.label,
            "lost": g.lost,
            "pct": g.pct,
            "best": a.best,
            "tier": a.tier,
            "ev": [
                {"action": n, "ev": float(e), "pct": 100 * float(e) / spot.pot}
                for n, e in zip(a.actions, a.ev, strict=True)
            ],
            "why": S.why(d.deal, d.table, cls, a, action),
            "standard": f"Against a standard player you'd {std.best} ({std_ev:+.2f} bb).",
            "band": S.band_note(a),
            "lesson": lessons.card(lesson),
        }

    def _grade_pushfold(self, c: _Drill, action: str) -> dict:
        t = c.spot
        g = t.grade(action)
        p = self.pushfold
        cls = class_of(c.combo)
        std = typed_spot(p.solution, p.matrix, t.depth, t.hero, self.types["standard"], cls)
        name = self.types[c.villain].name
        verb = "calls" if t.hero == "sb" else "jams"
        other = next(a for a in t.ev if a != t.best)
        why = [
            f"{name} {verb} the top {t.width:.0f}% of hands. {t.best} {t.ev[t.best]:+.2f} bb, "
            f"{other} {t.ev[other]:+.2f} bb. Nash would {t.nash}."
        ]
        band = [
            f"Band: the villain's width {max(1, t.width - 10):.0f}% to "
            f"{min(100, t.width + 10):.0f}% of hands."
        ]
        if t.band_winners:
            band.append("  " + ", ".join(sorted(t.band_winners)) + " wins somewhere in it.")
        return {
            "label": g.label,
            "lost": g.lost,
            "pct": g.pct,
            "best": t.best,
            "tier": "",
            "ev": [{"action": n, "ev": e, "pct": 100 * e / t.pot} for n, e in t.ev.items()],
            "why": why,
            "standard": f"Against a standard player (Nash's width, {std.width:.0f}%) you'd "
            f"{std.best} ({std.ev[std.best]:+.2f} bb).",
            "band": band,
            "lesson": lessons.card("pushfold-vs-types"),
        }

    def _row(self, c: _Drill, action: str, result: dict) -> dict:
        row = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "family": c.family,
            "hand": cards_str(c.combo),
            "class": CLASS_NAMES[class_of(c.combo)],
            "action": action,
            "grade": result["label"],
            "bb_lost": result["lost"],
            "pct_lost": result["pct"],
            "best": result["best"],
            "tier": result["tier"],
            "ev": {e["action"]: e["ev"] for e in result["ev"]},
            "seconds": c.seconds,
        }
        spot = c.spot
        if c.family == "pushfold":
            row |= {"seat": spot.hero.upper(), "depth": spot.depth, "villain_type": c.villain}
        else:
            row |= {"seat": spot.seat, "ante": spot.ante, "table_type": c.drill.table_type}
            if c.family == "open":
                row |= {
                    "opener": spot.opener.seat,
                    "open": spot.size,
                    "opener_type": c.drill.opener_type,
                }
            else:
                row |= {"limpers": spot.limpers, "limpers_type": c.drill.limpers_type}
        return row

    # --- views --------------------------------------------------------------------------

    def summary(self) -> dict:
        rows = self.rows
        grades = Counter(r["grade"] for r in rows)
        missed = [r for r in rows if r["grade"] != "Best"]
        by_type = Counter(
            r.get("villain_type") or r.get("opener_type") or r.get("table_type") for r in missed
        )
        return {
            "game": "trainer",
            "drills": len(rows),
            "grades": {label: grades[label] for label in S.LABELS},
            "accuracy": (grades["Best"] + grades["Correct"]) / len(rows) if rows else 0.0,
            "bb_lost": sum(r["bb_lost"] for r in rows),
            "misses_by_spot": dict(Counter(_spot_name(r) for r in missed).most_common()),
            "misses_by_type": {self.types[k].name: n for k, n in by_type.most_common() if k},
            "log": str(self.log_path),
        }

    def _seats(self) -> list[dict]:
        c = self._current
        roles: dict[str, tuple[str, str | None]] = {}
        if c.family == "pushfold":
            hero = c.spot.hero.upper()
            villain = "BB" if hero == "SB" else "SB"
            roles = {hero: ("you", None), villain: ("villain", c.villain)}
        else:
            spot, drill = c.spot, c.drill
            roles[spot.seat] = ("you", None)
            for kind, seat in spot.opponents():
                if kind == "limper":
                    roles[seat] = ("limper", drill.limpers_type)
                elif kind == "opener":
                    roles[seat] = ("opener", drill.opener_type)
                else:
                    roles[seat] = ("behind", drill.table_type)
        out = []
        for seat in S.SEATS:
            role, kind = roles.get(seat, ("folded", None))
            entry = {"seat": seat, "role": role}
            if kind:
                t = self.types[kind]
                entry |= {"type": kind, "type_name": t.name, "card": S.type_card(t)}
            out.append(entry)
        return out

    def view(self) -> dict:
        c = self._current
        if c is None:
            return {"game": "trainer", "summary": self.summary()}
        hand = CLASS_NAMES[class_of(c.combo)]
        view: dict = {
            "game": "trainer",
            "drill": self.drills,
            "family": c.family,
            "family_name": FAMILY_NAMES[c.family],
            "cards": [card_str(x) for x in c.combo],
            "hand": hand,
            "seats": self._seats(),
            "actions": [{"action": a, "label": a[0].upper() + a[1:]} for a in self._actions()],
            "your_turn": self._result is None,
            "summary": self.summary(),
        }
        if c.family == "pushfold":
            t = c.spot
            role = "SB: jam or fold" if t.hero == "sb" else "BB: the SB jams; call or fold"
            view |= {
                "headline": f"{t.depth} bb heads-up, you are the {role}. Tournament-style, no ICM.",
                "pot": t.pot,
                "ranges": [
                    f"Villain: {S.type_card(self.types[c.villain])}",
                    f"It {'calls' if t.hero == 'sb' else 'jams'} the top {t.width:.0f}% of hands "
                    "by equity: Nash's width times its type's ratio (DECISIONS 60).",
                ],
            }
        else:
            spot, drill = c.spot, c.drill
            if c.family == "open":
                lines = S.describe_open(
                    spot, drill.profile, hand, self.types[drill.opener_type].name
                )
                view["note"] = GATE_Z_NOTE
            else:
                lines = S.describe_spot(spot, drill.profile, hand)
            view |= {"headline": lines[0], "pot": spot.pot, "ranges": lines[1:]}
        if self._result is not None:
            view["result"] = self._result
        return view


def _spot_name(row: dict) -> str:
    if row["family"] == "pushfold":
        return f"push/fold {row['seat']}"
    if row["family"] == "open":
        return f"{row['seat']} vs {row['opener']} open"
    k = row["limpers"]
    return f"{row['seat']}, " + (f"{k} limper{'s' * (k != 1)}" if k else "unopened")
