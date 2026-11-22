"""Replay one pokerkit HandHistory into the facts the analyzer needs (DECISIONS 25 to 27).

pokerkit's iterator yields the same mutable State after every operation, so
nothing here keeps a State. At each yield we read who acts next and whether
they could raise, then attribute the next decision to that context.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field

from pokerkit import (
    BlindOrStraddlePosting,
    BoardDealing,
    CheckingOrCalling,
    ChipsPushing,
    CompletionBettingOrRaisingTo,
    Folding,
    HandHistory,
    HoleDealing,
)

from showdown.equity.cards import parse_card

PREFLOP = 0


class ReplayError(ValueError):
    """The hand could not be replayed faithfully; the message says why."""


@dataclass
class PlayerHand:
    name: str
    starting: float
    net: float = 0.0
    """Chips won or lost (pokerkit payoffs, uncalled bets already returned)."""
    hole: tuple[int, int] | None = None
    """Our card ids, or None if unknown."""
    preflop_decisions: int = 0
    vpip: bool = False
    pfr: bool = False
    three_bet_chance: bool = False
    three_bet: bool = False
    folded_on: int | None = None
    """Street (0 preflop, 1 flop, 2 turn, 3 river) of a fold, or None."""
    saw_flop: bool = False
    showdown: bool = False
    won_at_showdown: bool = False
    received: float = 0.0
    """Chips received from pots; returned uncalled bets are not included."""
    first_preflop: str | None = None
    """"fold", "check", "call" or "raise": the first voluntary preflop action."""
    first_preflop_allin: bool = False
    """Whether that first action put all of the player's chips in."""
    preflop_committed: float = 0.0


@dataclass
class AllIn:
    """The first moment no more betting is possible with two or more players in."""

    board: tuple[int, ...]
    pots: list[tuple[float, tuple[int, ...]]]
    live: tuple[int, ...]


@dataclass
class HandRecord:
    source: str
    players: list[PlayerHand]
    big_blind: float
    blind_seats: tuple[int | None, int | None] = (None, None)
    """(small blind seat, big blind seat), from the posting operations."""
    board: tuple[int, ...] = ()
    allin: AllIn | None = None
    odd_chip: bool = False
    """Replayed stacks differ from the recorded ones only by an odd-chip split."""
    blind_posts: dict[int, float] = field(default_factory=dict)
    antes: list[float] = field(default_factory=list)
    """Each player's ante, in seat order (DECISIONS 58)."""
    preflop: list[tuple[int, str, float]] = field(default_factory=list)
    """Preflop actions in order: (player, fold/check/call/raise, the chips called or the
    raise-to total), DECISIONS 58."""


def card_id(card) -> int | None:
    rank, suit = card.rank.value, card.suit.value
    if rank == "?" or suit == "?":
        return None
    return parse_card(rank + suit)


def _hole(cards) -> tuple[int, int] | None:
    ids = [card_id(c) for c in cards]
    if len(ids) != 2 or any(i is None for i in ids):
        return None
    return (ids[0], ids[1])  # type: ignore[return-value]


def _board(state) -> tuple[int, ...]:
    """The first board's known cards (pokerkit keeps one list per card slot)."""
    out = []
    for slot in state.board_cards:
        card = slot[0] if isinstance(slot, list | tuple) else slot
        cid = card_id(card)
        if cid is not None:
            out.append(cid)
    return tuple(out)


def replay(hh: HandHistory, source: str) -> HandRecord:
    """Replay `hh`. Raises ReplayError if pokerkit cannot, or if stacks do not reconcile."""
    starting = [float(s) for s in hh.starting_stacks]
    n = len(starting)
    names = list(hh.players) if hh.players else [f"p{i + 1}" for i in range(n)]
    if len(set(names)) != n:
        raise ReplayError("player names are not unique")
    players = [PlayerHand(names[i], starting[i]) for i in range(n)]
    blinds = [float(b) for b in hh.blinds_or_straddles]
    big_blind = max(blinds[:2]) if blinds else 0.0
    if big_blind <= 0:
        raise ReplayError("no big blind")

    street = PREFLOP
    raises_preflop = 0
    last_raiser: int | None = None
    context: tuple[int, bool] | None = None  # (next actor, that decision is a 3-bet spot)
    seen = 0
    allin: AllIn | None = None
    posts: dict[int, float] = {}
    actions: list[tuple[int, str, float]] = []
    state = None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for state in hh:
                for op in state.operations[seen:]:
                    if isinstance(op, BoardDealing):
                        street += 1
                    elif isinstance(op, HoleDealing):
                        players[op.player_index].hole = _hole(op.cards)
                    elif isinstance(op, ChipsPushing):
                        for i, amount in enumerate(op.amounts):
                            players[i].received += float(amount)
                    elif isinstance(op, BlindOrStraddlePosting):
                        posts[op.player_index] = float(op.amount)
                        players[op.player_index].preflop_committed = float(op.amount)
                    elif isinstance(op, Folding | CheckingOrCalling | CompletionBettingOrRaisingTo):
                        p = players[op.player_index]
                        if isinstance(op, Folding):
                            p.folded_on = street
                        if street == PREFLOP:
                            spot = context is not None and context == (op.player_index, True)
                            kind = _preflop(p, op, spot)
                            amount = 0.0 if kind == "fold" else float(op.amount)
                            actions.append((op.player_index, kind, amount))
                            if isinstance(op, CompletionBettingOrRaisingTo):
                                raises_preflop += 1
                                last_raiser = op.player_index
                seen = len(state.operations)
                actor = state.actor_index
                if actor is None:
                    context = None
                else:
                    context = (
                        actor,
                        street == PREFLOP
                        and raises_preflop == 1
                        and last_raiser != actor
                        and not players[actor].three_bet_chance
                        and state.can_complete_bet_or_raise_to(),
                    )
                if (
                    allin is None
                    and state.all_in_status
                    and len(state.board_cards) < 5
                    and sum(state.statuses) >= 2
                ):
                    allin = AllIn(
                        board=_board(state),
                        pots=[(float(p.amount), tuple(p.player_indices)) for p in state.pots],
                        live=tuple(i for i, s in enumerate(state.statuses) if s),
                    )
    except Exception as error:  # pokerkit raises ValueError and others on bad histories
        raise ReplayError(f"pokerkit could not replay it: {error}") from None
    if state is None:
        raise ReplayError("no actions")

    final = [float(s) for s in state.stacks]
    odd_chip = False
    if hh.finishing_stacks is not None:
        recorded = [float(s) for s in hh.finishing_stacks]
        diffs = [a - b for a, b in zip(final, recorded, strict=True)]
        if any(d != 0 for d in diffs):
            if all(abs(d) < 1 for d in diffs) and math.isclose(sum(diffs), 0, abs_tol=1e-9):
                odd_chip = True
            else:
                raise ReplayError(f"replayed stacks {final} differ from recorded {recorded}")

    flop_dealt = street >= 1
    live = [i for i, p in enumerate(players) if p.folded_on is None]
    for i, p in enumerate(players):
        p.net = float(state.payoffs[i])
        p.saw_flop = flop_dealt and (p.folded_on is None or p.folded_on >= 1)
        p.showdown = len(live) >= 2 and i in live
        p.won_at_showdown = p.showdown and p.received > 0

    small = min(posts, key=lambda s: posts[s]) if len(posts) >= 2 else None
    big = max(posts, key=lambda s: posts[s]) if len(posts) >= 2 else None
    return HandRecord(
        source=source,
        players=players,
        big_blind=big_blind,
        blind_seats=(small, big),
        board=_board(state),
        allin=allin,
        odd_chip=odd_chip,
        blind_posts=posts,
        antes=[float(a) for a in state.antes],
        preflop=actions,
    )


def _preflop(p: PlayerHand, op, three_bet_spot: bool) -> str:
    p.preflop_decisions += 1
    if three_bet_spot:
        p.three_bet_chance = True
    if isinstance(op, Folding):
        kind = "fold"
    elif isinstance(op, CheckingOrCalling):
        kind = "call" if op.amount > 0 else "check"
        p.preflop_committed += float(op.amount)
        p.vpip = p.vpip or op.amount > 0
    else:
        kind = "raise"
        p.preflop_committed = float(op.amount)  # "raise to" is the street total
        p.vpip = p.pfr = True
        p.three_bet = p.three_bet or three_bet_spot
    if p.first_preflop is None:
        p.first_preflop = kind
        p.first_preflop_allin = kind in ("call", "raise") and p.preflop_committed >= p.starting
    return kind
