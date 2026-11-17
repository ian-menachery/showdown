"""A saved heads-up hand replayed through pokerkit, with the state before every decision.

DECISIONS 41: the advisor gets the real hand state (the pot, the amount to call, both
stacks, the legal actions and the history) instead of numbers typed in. The preflop
decision and the pot type are read from the action, not given.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field, replace
from pathlib import Path

from pokerkit import (
    BlindOrStraddlePosting,
    BoardDealing,
    CheckingOrCalling,
    CompletionBettingOrRaisingTo,
    Folding,
    HandHistory,
    HoleDealing,
)

from showdown.equity.cards import Combo, make_combo
from showdown.hh.replay import ReplayError, card_id
from showdown.live.spot import DECISIONS, Legal, Spot

STREETS = ("preflop", "flop", "turn", "river")
SEATS = ("bb", "sb")
"""pokerkit's heads-up seat order: player 0 is the BB, player 1 the SB."""
LINE_DECISIONS = {node: name for name, (_, node) in DECISIONS.items()}
"""The preflop line so far -> the model's decision: "" sb_first, "r" bb_vs_raise, ..."""
LINE_POT_TYPES = {"rc": "srp", "rrc": "3bp"}


@dataclass(frozen=True)
class Move:
    street: str
    seat: str
    kind: str
    """fold, check, call, bet or raise."""
    to_bb: float
    """The player's total bet on the street after the move."""
    added_bb: float
    allin: bool

    def __str__(self) -> str:
        text = {
            "fold": "folds",
            "check": "checks",
            "call": f"calls {self.added_bb:g}",
            "bet": f"bets {self.to_bb:g}",
            "raise": f"raises to {self.to_bb:g}",
        }[self.kind]
        return f"{self.street} {self.seat.upper()} {text}" + (" (all-in)" if self.allin else "")


@dataclass(frozen=True)
class Decision:
    """The state just before one player's decision."""

    seat: str
    hole: Combo | None
    street: str
    board: tuple[int, ...]
    history: tuple[Move, ...]
    pot_bb: float
    """Everything in the middle, this street's bets included."""
    to_call_bb: float
    stacks_bb: dict[str, float]
    bets_bb: dict[str, float]
    effective_bb: float
    legal: Legal
    preflop_line: str
    """Voluntary preflop actions as codes: r raise, j raise to the effective stack, c call,
    k check, f fold."""
    taken: Move | None = None

    @property
    def preflop_decision(self) -> str:
        decision = LINE_DECISIONS.get(self.preflop_line, "other")
        return decision if DECISIONS.get(decision, (self.seat,))[0] == self.seat else "other"

    @property
    def pot_type(self) -> tuple[str, str | None]:
        """("srp" or "3bp", and a note when the line is not an open-call or a 3-bet-call)."""
        line = self.preflop_line
        if line in LINE_POT_TYPES:
            return LINE_POT_TYPES[line], None
        kind = "srp" if sum(c in "rj" for c in line) <= 1 else "3bp"
        return kind, f"preflop line {line!r} is not an open-call or a 3-bet-call: {kind} ranges"

    def spot(self) -> Spot:
        if self.hole is None:
            raise ReplayError(f"the {self.seat.upper()}'s cards are not in the hand history")
        preflop = self.street == "preflop"
        return Spot(
            hero=self.hole,
            seat=self.seat,
            effective_bb=self.effective_bb,
            board=self.board,
            pot_bb=self.pot_bb,
            to_call_bb=self.to_call_bb,
            pot_type="srp" if preflop else self.pot_type[0],
            preflop=self.preflop_decision if preflop else "sb_first",
            history=tuple(str(m) for m in self.history),
            stack_behind_bb=self.stacks_bb[self.seat],
            legal=self.legal,
        )


@dataclass(frozen=True)
class Step:
    """The pot and stacks right after one player action."""

    move: Move
    pot_bb: float
    stacks_bb: dict[str, float]


@dataclass
class HandReplay:
    source: str
    big_blind: float
    """In chips."""
    starting_bb: dict[str, float]
    holes: dict[str, Combo | None]
    decisions: list[Decision] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)

    @property
    def total_bb(self) -> float:
        return sum(self.starting_bb.values())


def load(path: str | Path) -> HandReplay:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with open(path, "rb") as f:
            hh = HandHistory.load(f)
    return replay_history(hh, str(path))


def replay_history(hh: HandHistory, source: str) -> HandReplay:
    """Replay a heads-up hand, recording every decision and the pot and stacks after each action."""
    n = len(hh.starting_stacks)
    if n != 2:
        raise ReplayError(f"heads-up only: {n} players dealt in")
    big_blind = float(max(hh.blinds_or_straddles[:2]))
    chips = [float(s) for s in hh.starting_stacks]
    bb = {SEATS[i]: chips[i] / big_blind for i in range(2)}
    out = HandReplay(source, big_blind, bb, {"bb": None, "sb": None})
    effective_chips = min(chips)
    street, board, history, line = 0, [], [], ""
    pending: Decision | None = None
    seen = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for state in hh:
            for op in state.operations[seen:]:
                if isinstance(op, HoleDealing):
                    ids = [card_id(c) for c in op.cards]
                    if None not in ids:
                        out.holes[SEATS[op.player_index]] = make_combo(*ids)
                elif isinstance(op, BoardDealing):
                    street += 1
                    board += [card_id(c) for c in op.cards]
                elif isinstance(op, BlindOrStraddlePosting):
                    continue
                elif isinstance(op, Folding | CheckingOrCalling | CompletionBettingOrRaisingTo):
                    if pending is None or SEATS[op.player_index] != pending.seat:
                        raise ReplayError(f"an action without a matching decision: {op}")
                    move, step = _apply(op, pending, big_blind, effective_chips)
                    if street == 0:
                        line += _code(move, effective_chips / big_blind)
                    history.append(move)
                    out.decisions.append(replace(pending, taken=move))
                    out.steps.append(step)
                    pending = None
            seen = len(state.operations)
            if state.actor_index is not None and (state.can_fold() or state.can_check_or_call()):
                pending = _decision(state, out, street, board, history, line, big_blind)
    return out


def _decision(state, out, street, board, history, line, big_blind) -> Decision:
    actor = state.actor_index
    seat = SEATS[actor]
    to_call = state.checking_or_calling_amount if state.can_check_or_call() else 0
    lo = hi = None
    if state.can_complete_bet_or_raise_to():
        lo = state.min_completion_betting_or_raising_to_amount / big_blind
        hi = state.max_completion_betting_or_raising_to_amount / big_blind
    other = 1 - actor
    cap = (state.bets[other] + state.stacks[other]) / big_blind
    return Decision(
        seat=seat,
        hole=out.holes[seat],
        street=STREETS[street],
        board=tuple(board),
        history=tuple(history),
        pot_bb=state.total_pot_amount / big_blind,
        to_call_bb=to_call / big_blind,
        stacks_bb={SEATS[i]: state.stacks[i] / big_blind for i in range(2)},
        bets_bb={SEATS[i]: state.bets[i] / big_blind for i in range(2)},
        effective_bb=min(out.starting_bb.values()),
        legal=Legal(to_call / big_blind, lo, hi, cap),
        preflop_line=line,
    )


def _apply(op, d: Decision, big_blind: float, effective_chips: float) -> tuple[Move, Step]:
    """The move, and the pot and stacks after it, from the state before it and the amount."""
    seat = d.seat
    bet = d.bets_bb[seat]
    if isinstance(op, Folding):
        kind, to = "fold", bet
    elif isinstance(op, CheckingOrCalling):
        added = float(op.amount) / big_blind
        kind, to = ("call", bet + added) if added > 0 else ("check", bet)
    else:
        to = float(op.amount) / big_blind
        kind = "raise" if max(d.bets_bb.values()) > 0 else "bet"
    added = to - bet
    stacks = dict(d.stacks_bb)
    stacks[seat] -= added
    move = Move(d.street, seat, kind, to, added, kind != "fold" and stacks[seat] <= 1e-9)
    return move, Step(move, d.pot_bb + added, stacks)


def _code(move: Move, effective_bb: float) -> str:
    if move.kind in ("bet", "raise"):
        return "j" if move.to_bb >= effective_bb - 1e-9 else "r"
    return {"call": "c", "check": "k", "fold": "f"}[move.kind]
