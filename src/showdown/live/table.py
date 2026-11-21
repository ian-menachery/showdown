"""One read of the table: what the screen reader must deliver (DECISIONS 42).

Until the reader exists (S1), frames come from recorded files or from replaying a hand
history, which is how the tracker is tested and demonstrated.
"""

from __future__ import annotations

import json
import warnings
from collections.abc import Iterator
from dataclasses import asdict, dataclass

from pokerkit import HandHistory

from showdown.equity.cards import cards_str
from showdown.hh.replay import card_id


@dataclass(frozen=True)
class Seat:
    name: str
    stack: float
    """Chips behind."""
    bet: float = 0.0
    """Chips in front of the player on this street."""
    in_hand: bool = True
    """Still holds cards."""
    cards: str | None = None
    """Hole cards when visible: always Ian's, others' only at a showdown."""


@dataclass(frozen=True)
class TableState:
    seats: tuple[Seat, ...]
    hero: int
    """Ian's seat index."""
    button: int
    to_act: int | None
    """The seat whose turn it is, or None."""
    big_blind: float
    small_blind: float
    board: str = ""
    ended: bool = False
    """The hand's result is showing, so the stacks are final."""
    pot: float | None = None
    """The pot as shown, if the reader reads it; checked against the tracker's count."""

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, line: str) -> TableState:
        data = json.loads(line)
        data["seats"] = tuple(Seat(**s) for s in data["seats"])
        return cls(**data)


@dataclass(frozen=True)
class ReadError:
    """What the reader gives instead of a frame it can't read in full (DECISIONS 51, 52)."""

    reason: str


def frame_from_state(
    state,
    hero: int,
    names: list[str],
    big_blind: float,
    small_blind: float,
    known: dict[int, str] | None = None,
) -> TableState | None:
    """A frame from a heads-up pokerkit state, as Ian at player `hero` would see it.

    Seat i is pokerkit player i (0 the BB, 1 the SB, so the SB holds the button). Cards
    stay on the table once seen: `known` holds them, and this adds any newly visible.
    None until Ian's cards are seen.
    """
    known = {} if known is None else known
    holes = state.hole_cards
    for i in range(2):
        shown = i == hero or (len(holes[i]) == 2 and all(state.hole_card_statuses[i]))
        if shown and len(holes[i]) == 2 and None not in (card_id(c) for c in holes[i]):
            known[i] = cards_str(card_id(c) for c in holes[i])
    if hero not in known:
        return None
    seats = []
    for i in range(2):
        cards = known.get(i)
        seats.append(
            Seat(
                names[i],
                float(state.stacks[i]),
                float(state.bets[i]),
                bool(state.statuses[i]),
                cards,
            )
        )
    board = cards_str(card_id(slot[0]) for slot in state.board_cards)
    actor = state.actor_index if state.status else None
    return TableState(tuple(seats), hero, 1, actor, big_blind, small_blind, board, not state.status)


def frames_from_history(
    hh: HandHistory, hero_seat: str, *, every_change: bool = True
) -> Iterator[TableState]:
    """Frames of a recorded heads-up hand: one after every change, or only at Ian's turns
    and the end."""
    hero = {"bb": 0, "sb": 1}[hero_seat]
    names = list(hh.players) if hh.players else ["p1", "p2"]
    blinds = [float(b) for b in hh.blinds_or_straddles]
    big, small = max(blinds), min(blinds)
    last, known = None, {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for state in hh:
            frame = frame_from_state(state, hero, names, big, small, known)
            if frame is None:
                continue
            if frame == last:
                continue
            if every_change or frame.ended or frame.to_act == hero:
                yield frame
            last = frame
