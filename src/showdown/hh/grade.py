"""Grading real heads-up hands against push/fold Nash (DECISIONS 27)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from showdown.bot.policy import PushFoldStrategy
from showdown.equity.cards import class_of, make_combo
from showdown.hh.replay import HandRecord


@dataclass(frozen=True)
class Decision:
    seat: str
    """"sb" or "bb"."""
    player: str
    depth: int
    effective_bb: float
    hand_class: int
    allin: bool
    loss: float
    mistake: bool


@dataclass(frozen=True)
class GradeResult:
    decisions: tuple[Decision, ...]
    reason: str | None
    """Why the hand is not gradable, or None."""


def depth_for(effective_bb: float) -> int:
    """Nearest solved integer depth, halves rounding up, clamped to 1 to 20 (DECISIONS 27)."""
    return max(1, min(20, math.floor(effective_bb + 0.5)))


def grade_hand(record: HandRecord, strategy: PushFoldStrategy) -> GradeResult:
    """Grade a heads-up hand against push/fold Nash, if it fits the game (DECISIONS 27)."""
    if len(record.players) != 2:
        return GradeResult((), "not heads-up")
    sb_seat, bb_seat = record.blind_seats
    if sb_seat is None or bb_seat is None or sb_seat == bb_seat:
        return GradeResult((), "blinds not posted")
    sb, bb = record.players[sb_seat], record.players[bb_seat]
    effective = min(sb.starting, bb.starting) / record.big_blind
    if effective > 20:
        return GradeResult((), "deeper than 20 bb")
    depth = depth_for(effective)
    if sb.first_preflop not in ("fold", "call", "raise") or (
        sb.first_preflop != "fold" and not sb.first_preflop_allin
    ):
        return GradeResult((), "small blind did not fold or go all-in")
    if sb.hole is None:
        return GradeResult((), "small blind's cards unknown")
    jam = sb.first_preflop != "fold"
    decisions = [_decision(strategy, "sb", sb.name, depth, effective, sb.hole, jam)]
    if jam and bb.first_preflop in ("fold", "call") and bb.hole is not None:
        call = bb.first_preflop == "call"
        decisions.append(_decision(strategy, "bb", bb.name, depth, effective, bb.hole, call))
    return GradeResult(tuple(decisions), None)


def _decision(strategy, seat, player, depth, effective, hole, allin) -> Decision:
    cls = class_of(make_combo(*hole))
    grade = strategy.grade(depth, seat, cls, allin)
    return Decision(seat, player, depth, effective, cls, allin, grade.loss, grade.mistake)
