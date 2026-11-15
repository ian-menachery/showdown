"""All-in EV adjustment for one replayed hand (DECISIONS 26)."""

from __future__ import annotations

import zlib
from dataclasses import dataclass

from showdown.equity.multiway import pot_shares
from showdown.hh.replay import HandRecord


@dataclass(frozen=True)
class AllInAdjustment:
    ev_net: dict[int, float]
    """Seat -> EV-adjusted result in chips."""
    method: str
    """"exact" or "monte-carlo"."""
    se: dict[int, float]


def allin_adjustment(
    record: HandRecord, *, samples: int = 20_000, seed: int = 0
) -> AllInAdjustment | None:
    """EV-adjusted results for a qualifying all-in hand, or None (DECISIONS 26).

    EV net = actual net − chips actually received from the pots + expected
    share of the same pots. The pots are final at the all-in point, and
    returned uncalled bets never pass through them, so no contribution
    bookkeeping is needed.
    """
    allin = record.allin
    if allin is None:
        return None
    hands = {}
    for seat in allin.live:
        hole = record.players[seat].hole
        if hole is None:
            return None
        hands[seat] = hole
    hand_seed = seed ^ zlib.crc32(record.source.encode("utf-8"))
    shares = pot_shares(hands, allin.board, allin.pots, samples=samples, seed=hand_seed)
    ev = {}
    for seat, p in enumerate(record.players):
        expected = shares.expected.get(seat, 0.0)
        ev[seat] = p.net - p.received + expected
    se = {seat: shares.se.get(seat, 0.0) for seat in range(len(record.players))}
    return AllInAdjustment(ev, shares.method, se)
