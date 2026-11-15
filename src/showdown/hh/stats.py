"""Per-player stats over replayed hands, with all-in EV adjustment (DECISIONS 25, 26)."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field

from showdown.hh.allin_ev import AllInAdjustment, allin_adjustment
from showdown.hh.replay import HandRecord


@dataclass
class PlayerStats:
    name: str
    hands: int = 0
    opportunities: int = 0
    vpip: int = 0
    pfr: int = 0
    three_bet_chances: int = 0
    three_bets: int = 0
    saw_flop: int = 0
    wtsd: int = 0
    won_at_showdown: int = 0
    net_bb: float = 0.0
    ev_net_bb: float = 0.0
    ev_se_bb_sq: float = 0.0
    """Sum of squared Monte Carlo SEs of the EV adjustments, in bb²."""

    @staticmethod
    def _pct(num: int, den: int) -> float:
        return 100.0 * num / den if den else math.nan

    @property
    def vpip_pct(self) -> float:
        return self._pct(self.vpip, self.opportunities)

    @property
    def pfr_pct(self) -> float:
        return self._pct(self.pfr, self.opportunities)

    @property
    def three_bet_pct(self) -> float:
        return self._pct(self.three_bets, self.three_bet_chances)

    @property
    def wtsd_pct(self) -> float:
        return self._pct(self.wtsd, self.saw_flop)

    @property
    def wsd_pct(self) -> float:
        return self._pct(self.won_at_showdown, self.wtsd)

    @property
    def bb_per_100(self) -> float:
        return 100.0 * self.net_bb / self.hands if self.hands else math.nan

    @property
    def ev_bb_per_100(self) -> float:
        return 100.0 * self.ev_net_bb / self.hands if self.hands else math.nan

    @property
    def ev_bb_per_100_se(self) -> float:
        return 100.0 * math.sqrt(self.ev_se_bb_sq) / self.hands if self.hands else math.nan


@dataclass
class Report:
    players: dict[str, PlayerStats] = field(default_factory=dict)
    hands: int = 0
    allin_hands: int = 0
    allin_exact: int = 0
    allin_monte_carlo: int = 0
    allin_multiway: int = 0
    allin_unknown_cards: int = 0
    odd_chip: int = 0


def analyze(
    records: Iterable[HandRecord], *, samples: int = 20_000, seed: int = 0
) -> tuple[Report, dict[str, AllInAdjustment]]:
    """Per-player stats over `records`, with all-in EV adjustment (DECISIONS 25, 26)."""
    report = Report()
    adjustments: dict[str, AllInAdjustment] = {}
    for record in records:
        report.hands += 1
        report.odd_chip += record.odd_chip
        adjustment = None
        if record.allin is not None:
            report.allin_hands += 1
            adjustment = allin_adjustment(record, samples=samples, seed=seed)
            if adjustment is None:
                report.allin_unknown_cards += 1
            else:
                adjustments[record.source] = adjustment
                report.allin_exact += adjustment.method == "exact"
                report.allin_monte_carlo += adjustment.method == "monte-carlo"
                report.allin_multiway += len(record.allin.live) > 2
        bb = record.big_blind
        for seat, p in enumerate(record.players):
            s = report.players.setdefault(p.name, PlayerStats(p.name))
            s.hands += 1
            if p.preflop_decisions:
                s.opportunities += 1
                s.vpip += p.vpip
                s.pfr += p.pfr
            s.three_bet_chances += p.three_bet_chance
            s.three_bets += p.three_bet
            s.saw_flop += p.saw_flop
            s.wtsd += p.showdown
            s.won_at_showdown += p.won_at_showdown
            s.net_bb += p.net / bb
            if adjustment is not None:
                s.ev_net_bb += adjustment.ev_net[seat] / bb
                s.ev_se_bb_sq += (adjustment.se[seat] / bb) ** 2
            else:
                s.ev_net_bb += p.net / bb
    return report, adjustments
