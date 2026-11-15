"""Play sessions: the game logic behind the play page, independent of HTTP (DECISIONS 23, 24).

A session plays hands between a human seat and a bot. Every response is a
plain dict for the JSON API. It never contains the bot's cards before the hand
is over.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from showdown.bot.policy import Grade, LeducStrategy, PushFoldStrategy, act
from showdown.engine.pokerkit_adapter import HandResult, PushFoldHand, deal_cards
from showdown.equity.cards import CLASS_NAMES, card_str
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
