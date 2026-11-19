"""The live tracker: table frames in, advice and hand histories out (DECISIONS 42).

For a heads-up hand it keeps a pokerkit state. Between frames it finds the shortest
sequence of legal actions that turns that state into one matching the new frame, and
applies it, recording every decision as DECISIONS 41's replay does. At each of Ian's turns
it asks the advisor; at the end frame it writes the hand as PHH.
"""

from __future__ import annotations

import copy
import time
import warnings
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from pokerkit import Automation, HandHistory, NoLimitTexasHoldem

from showdown.equity.cards import cards_str, make_combo, parse_cards
from showdown.hh.replay import card_id
from showdown.live.advisor import Advisor, Suggestion
from showdown.live.hand import (
    SEATS,
    Decision,
    HandReplay,
    _apply,
    _code,
    _decision,
    preflop_raises,
)
from showdown.live.spot import Spot, SpotError
from showdown.live.table import TableState

AUTOMATIONS = (
    Automation.ANTE_POSTING,
    Automation.BLIND_OR_STRADDLE_POSTING,
    Automation.CARD_BURNING,
    Automation.HAND_KILLING,
    Automation.CHIPS_PUSHING,
    Automation.CHIPS_PULLING,
)
"""Bet collection and showing are left out: the frame says when bets are swept into the pot
(the table can show a closed street's bets for a moment) and which cards were shown."""
MAX_ACTIONS = 6
HANDS_DIR = Path("data/live/hands")


@dataclass(frozen=True)
class Event:
    kind: str
    """advice, solving, no suggestion, written, not written, or error."""
    text: str
    decision: Decision | None = None
    suggestion: Suggestion | None = None
    elapsed_ms: float = 0.0
    since_card_ms: float | None = None
    """Turn and river advice: from feeding the frame that first showed the card (DECISIONS 47)."""
    live_solve: bool = False
    """A live solve was started for this decision's street."""


class TrackError(ValueError):
    """A frame no legal sequence of actions explains."""


class _Hand:
    def __init__(self, frame: TableState) -> None:
        self.ignored = None
        dealt = [s for s in frame.seats if s.in_hand]
        if len(dealt) != 2:
            self.ignored = f"{len(dealt)} players dealt in"
            return
        if frame.board or frame.ended:
            self.ignored = "joined mid-hand"
            return
        # Seat order -> pokerkit player: the button is the SB (player 1), the other the BB.
        other = next(i for i, s in enumerate(frame.seats) if s.in_hand and i != frame.button)
        self.player_of = {other: 0, frame.button: 1}
        self.seat_of = {p: i for i, p in self.player_of.items()}
        self.hero = self.player_of[frame.hero]
        self.names = [frame.seats[self.seat_of[p]].name for p in (0, 1)]
        self.big_blind, self.small_blind = _chips(frame.big_blind), _chips(frame.small_blind)
        start = [
            _chips(frame.seats[self.seat_of[p]].stack + frame.seats[self.seat_of[p]].bet)
            for p in (0, 1)
        ]
        self.start = start
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.state = NoLimitTexasHoldem.create_state(
                AUTOMATIONS, True, 0, (self.small_blind, self.big_blind), self.big_blind, start, 2
            )
            hero_cards = frame.seats[frame.hero].cards
            for p in (0, 1):
                self.state.deal_hole(hero_cards if p == self.hero else "????")
        self.replay = HandReplay(
            "live",
            self.big_blind,
            {SEATS[p]: start[p] / self.big_blind for p in (0, 1)},
            {SEATS[p]: None for p in (0, 1)},
        )
        self.replay.holes[SEATS[self.hero]] = make_combo(*parse_cards(hero_cards))
        self.line, self.history, self.unseen = "", [], 0
        self.hero_cards = hero_cards
        self.card_at: dict[str, float] = {}
        """perf_counter when the frame that first showed each street's card was fed."""

    # --- matching a frame ---------------------------------------------------------------

    def target(self, frame: TableState) -> dict:
        seats = [frame.seats[self.seat_of[p]] for p in (0, 1)]
        return {
            "board": frame.board,
            "stacks": [_chips(s.stack) for s in seats],
            "bets": [_chips(s.bet) for s in seats],
            "actor": None if frame.to_act is None else self.player_of.get(frame.to_act),
            "ended": frame.ended,
            "shown": [s.cards for s in seats],
            "hero": self.hero,
        }

    def explain(self, frame: TableState) -> list[tuple]:
        """The shortest list of actions taking the state to `frame`."""
        t = self.target(frame)
        queue = deque([(copy.deepcopy(self.state), [])])
        while queue:
            state, seq = queue.popleft()
            if not _advance(state, t):
                continue
            if _matches(state, t):
                return seq
            if len(seq) >= MAX_ACTIONS or state.actor_index is None:
                continue
            for act in _candidates(state, t):
                nxt = copy.deepcopy(state)
                _do(nxt, act)
                if not _impossible(nxt, t):
                    queue.append((nxt, [*seq, act]))
        raise TrackError(f"no legal sequence of up to {MAX_ACTIONS} actions explains the frame")

    def apply(self, actions: list[tuple], frame: TableState) -> None:
        t = self.target(frame)
        for act in actions:
            _advance(self.state, t)
            pending = _decision(
                self.state,
                self.replay,
                _street(self.state),
                _board(self.state),
                self.history,
                self.line,
                self.big_blind,
            )
            before = len(self.state.operations)
            _do(self.state, act)
            op = self.state.operations[before]
            move, step = _apply(op, pending, self.big_blind, min(self.start))
            if pending.street == "preflop":
                self.line += _code(move, min(self.start) / self.big_blind)
            self.history.append(move)
            self.replay.decisions.append(replace(pending, taken=move))
            self.replay.steps.append(step)
            if act[0] == "unseen":
                self.unseen += 1
        _advance(self.state, t)

    def hero_spot(self) -> Spot:
        """Ian's side of the hand now, enough to start a live solve (DECISIONS 47)."""
        open_bb, threebet_bb = preflop_raises(tuple(self.history))
        return Spot(
            hero=self.replay.holes[SEATS[self.hero]],
            seat=SEATS[self.hero],
            effective_bb=min(self.replay.starting_bb.values()),
            board=_board(self.state),
            history=tuple(str(m) for m in self.history),
            open_bb=open_bb,
            threebet_bb=threebet_bb,
        )

    def decision(self) -> Decision:
        return _decision(
            self.state,
            self.replay,
            _street(self.state),
            _board(self.state),
            self.history,
            self.line,
            self.big_blind,
        )

    def history_text(self) -> str:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            game = NoLimitTexasHoldem(
                AUTOMATIONS, True, 0, (self.small_blind, self.big_blind), self.big_blind
            )
            hh = HandHistory.from_game_state(game, self.state)
        hh.players = self.names
        hh.finishing_stacks = list(self.state.stacks)
        note = f"# showdown live tracker, {datetime.now():%Y-%m-%d %H:%M}"
        if self.unseen:
            note += f"\n# {self.unseen} bet(s) written at the smallest size: the size was not seen"
        return note + "\n" + hh.dumps()


def _chips(x: float) -> float:
    """Whole chip counts as ints, so pokerkit and the written PHH keep them whole."""
    return int(x) if float(x).is_integer() else x


def _street(state) -> int:
    return {0: 0, 3: 1, 4: 2, 5: 3}[len(_board(state))]


def _board(state) -> tuple[int, ...]:
    return tuple(card_id(slot[0]) for slot in state.board_cards)


def _advance(state, t: dict) -> bool:
    """Deal the board cards and show or muck as the frame says."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        while True:
            if state.can_collect_bets():
                later = len(t["board"]) > len(cards_str(_board(state)))
                if not (t["ended"] or later or not any(t["bets"])):
                    return True  # the frame still shows the bets in front
                state.collect_bets()
            elif state.can_deal_board():
                have = cards_str(_board(state))
                n = 3 if not have else 1
                if len(t["board"]) < len(have) + 2 * n or not t["board"].startswith(have):
                    return True  # the frame shows no more cards yet
                state.deal_board(t["board"][len(have) : len(have) + 2 * n])
            elif state.showdown_index is not None:
                # Show the opponent's cards once the frame shows them (pokerkit needs them
                # spelled out, as it dealt them unknown). Ian's are always on his screen, so
                # his show waits, like any muck, until the run-out or the result is on.
                i = state.showdown_index
                cards = t["shown"][i] or False
                later = len(t["board"]) > len(cards_str(_board(state)))
                if not (later or t["ended"] or (cards and i != t["hero"])):
                    return True
                if not state.can_show_or_muck_hole_cards(cards):
                    return True
                state.show_or_muck_hole_cards(cards)
            else:
                return True


def _matches(state, t: dict) -> bool:
    if cards_str(_board(state)) != t["board"]:
        return False
    if t["ended"]:
        return not state.status and list(state.stacks) == t["stacks"]
    if not state.status or list(state.stacks) != t["stacks"] or list(state.bets) != t["bets"]:
        return False
    return t["actor"] is None or state.actor_index == t["actor"]


def _impossible(state, t: dict) -> bool:
    """A player's chips outside the pot (stack plus bet) only fall during a hand, since an
    uncalled bet goes back to the stack; and an open street's bets only rise."""
    if t["ended"] or not state.status:
        return False
    outside = [s + b for s, b in zip(state.stacks, state.bets, strict=True)]
    if any(o < s + b for o, s, b in zip(outside, t["stacks"], t["bets"], strict=True)):
        return True
    open_street = state.actor_index is not None and cards_str(_board(state)) == t["board"]
    return open_street and any(b > f for b, f in zip(state.bets, t["bets"], strict=True))


def _candidates(state, t: dict) -> list[tuple]:
    p = state.actor_index
    out = [("cc",)]
    if state.can_complete_bet_or_raise_to():
        lo = state.min_completion_betting_or_raising_to_amount
        hi = state.max_completion_betting_or_raising_to_amount
        amounts = []
        later = len(t["board"]) > len(cards_str(_board(state)))
        if not later and not t["ended"]:
            amounts.append(t["bets"][p])
        if later and not t["ended"]:
            amounts.append(state.bets[p] + state.stacks[p] - t["stacks"][p] - t["bets"][p])
        unseen = t["ended"] and not t["shown"][1 - p]  # bet, then a fold: size never seen
        if t["ended"]:  # a called last bet: the loser's final stack gives its size
            cover = state.bets[1 - p] + state.stacks[1 - p]
            for i in (0, 1):
                a = state.bets[i] + state.stacks[i] - t["stacks"][i]
                amounts.append(a)
                # Called all-in for less than a legal raise: the excess came back, unseen.
                unseen = unseen or (a == cover and a < lo)
        for a in sorted(set(amounts)):
            if lo <= a <= hi and a > max(state.bets):
                out.append(("cbr", a))
        if unseen:
            out.append(("unseen", lo))
    if state.checking_or_calling_amount > 0:
        out.append(("f",))
    return out


def _do(state, act: tuple) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if act[0] == "cc":
            state.check_or_call()
        elif act[0] == "f":
            state.fold()
        else:
            state.complete_bet_or_raise_to(act[1])


class Tracker:
    """Feed it frames; it returns what happened on each."""

    def __init__(
        self,
        advisor: Advisor,
        hands_dir: Path | None = HANDS_DIR,
        on_solving: Callable[[Event], None] | None = None,
    ) -> None:
        self.advisor = advisor
        self.hands_dir = hands_dir
        self.on_solving = on_solving
        """Called with the "solving…" event before waiting on a live solve, so the overlay
        can show it at once (DECISIONS 47)."""
        self.hand: _Hand | None = None
        self.last: TableState | None = None
        self.written = 0

    def _new_hand(self, frame: TableState) -> bool:
        last = self.last
        if last is None or (last.ended and not frame.ended):
            return True
        if frame.seats[frame.hero].cards != last.seats[last.hero].cards:
            return True
        return bool(last.board) and not frame.board

    def feed(self, frame: TableState) -> list[Event]:
        start = time.perf_counter()
        events: list[Event] = []
        if self._new_hand(frame):
            if (
                self.hand is not None
                and not self.hand.ignored
                and self.last
                and not self.last.ended
            ):
                events.append(Event("not written", "the last hand had no end frame"))
            self.hand = _Hand(frame)
        self.last = frame
        hand = self.hand
        if hand.ignored:
            if frame.to_act == frame.hero and not frame.ended:
                events.append(Event("no suggestion", f"no suggestion: {hand.ignored}"))
            return events
        cards = len(_board(hand.state))
        try:
            hand.apply(hand.explain(frame), frame)
        except TrackError as error:
            hand.ignored = f"reading error: {error}"
            events.append(Event("error", hand.ignored))
            return events
        if frame.ended:
            events.append(self._write(hand))
            return events
        street = {4: "turn", 5: "river"}.get(len(_board(hand.state)))
        if street and len(_board(hand.state)) > cards:
            hand.card_at[street] = start
            if hand.state.actor_index is not None:
                self.advisor.prefetch(hand.hero_spot())  # solve while the table plays on
        if frame.to_act == frame.hero and hand.state.actor_index == hand.hero:
            decision = hand.decision()
            try:
                spot = decision.spot()
                if self.advisor.solving(spot):
                    waiting = Event("solving", "solving…", decision)
                    events.append(waiting)
                    if self.on_solving is not None:
                        self.on_solving(waiting)
                suggestion = self.advisor.suggest(spot)
            except SpotError as error:
                events.append(Event("no suggestion", f"no suggestion: {error}", decision))
            else:
                now = time.perf_counter()
                since = (now - hand.card_at[street]) * 1000 if street in hand.card_at else None
                events.append(
                    Event(
                        "advice",
                        "",
                        decision,
                        suggestion,
                        (now - start) * 1000,
                        since,
                        self.advisor.solve_started(spot),
                    )
                )
        return events

    def _write(self, hand: _Hand) -> Event:
        if self.hands_dir is None:
            return Event("written", "not saved (no folder)")
        self.hands_dir.mkdir(parents=True, exist_ok=True)
        self.written += 1
        path = self.hands_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{self.written:04d}.phh"
        path.write_text(hand.history_text(), encoding="utf-8")
        return Event("written", str(path))
