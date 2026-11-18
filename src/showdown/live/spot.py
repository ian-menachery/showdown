"""One heads-up decision as the advisor sees it (DECISIONS 32, 35).

Amounts are in big blinds. `pot_bb` is everything already in the middle,
including any bet the hero is facing. `to_call_bb` is 0 when the hero may check.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from showdown.equity.cards import Combo, cards_str, make_combo, parse_cards

SEATS = ("sb", "bb")
POT_TYPES = ("srp", "3bp")
DECISIONS: dict[str, tuple[str, str]] = {
    "sb_first": ("sb", ""),
    "bb_vs_raise": ("bb", "r"),
    "sb_vs_3bet": ("sb", "rr"),
    "bb_vs_4bet_jam": ("bb", "rrj"),
    "sb_vs_jam": ("sb", "rj"),
    "bb_vs_jam": ("bb", "j"),
}
"""Preflop decision -> (the seat that makes it, its node in the preflop model)."""
PREFLOP_SPOTS = (*DECISIONS, "other")
MODES = ("hint", "equity")


class SpotError(ValueError):
    """A spot that cannot be advised on as given."""


@dataclass(frozen=True)
class Legal:
    """What the hero may do now, by pokerkit's rules, in bb (DECISIONS 41).

    Bet and raise sizes are raise-to amounts: the hero's total bet on the street.
    """

    to_call_bb: float
    """0 when the hero may check. Folding is offered only when this is above 0."""
    raise_min_bb: float | None = None
    """The smallest bet or raise-to; None when no bet or raise is allowed."""
    raise_max_bb: float | None = None
    cap_bb: float | None = None
    """The most the opponent can match: their bet plus their stack."""

    @property
    def can_raise(self) -> bool:
        return self.raise_min_bb is not None


@dataclass(frozen=True)
class Spot:
    hero: Combo
    seat: str
    """The hero's seat: "sb" (button, in position after the flop) or "bb"."""
    effective_bb: float
    """The smaller stack before the blinds were posted."""
    board: tuple[int, ...] = ()
    pot_bb: float = 1.5
    to_call_bb: float = 0.0
    pot_type: str = "srp"
    """Postflop default ranges: "srp" (single-raised) or "3bp" (3-bet pot)."""
    preflop: str = "sb_first"
    """Preflop only: one of `DECISIONS`, or "other"."""
    villain_range: str | None = None
    """A custom range in showdown's syntax; overrides the default (DECISIONS 32)."""
    villain_top: float | None = None
    """A custom range as the top N% by equity against a random hand (DECISIONS 36)."""
    mode: str = "hint"
    history: tuple[str, ...] = ()
    """The hand's actions so far, from a replay (DECISIONS 41). Postflop, the villain's moves
    narrow its assumed range (DECISIONS 46)."""
    stack_behind_bb: float | None = None
    """The hero's remaining stack, from a replay."""
    legal: Legal | None = None
    """The legal actions, from a replay. When set, the advice is kept to them."""

    def __post_init__(self) -> None:
        cards = [*self.hero, *self.board]
        if len(set(cards)) != len(cards):
            raise SpotError("the hero's cards and the board share a card")
        if len(self.board) not in (0, 3, 4, 5):
            raise SpotError("the board has 0, 3, 4 or 5 cards")
        if self.seat not in SEATS:
            raise SpotError("seat must be sb or bb")
        if self.pot_type not in POT_TYPES:
            raise SpotError("pot type must be srp or 3bp")
        if self.preflop not in PREFLOP_SPOTS:
            raise SpotError("preflop spot must be one of " + ", ".join(PREFLOP_SPOTS))
        if self.mode not in MODES:
            raise SpotError("mode must be hint or equity")
        if self.villain_range and self.villain_top is not None:
            raise SpotError("give a villain range or a villain top %, not both")
        if self.villain_top is not None and not 0 < self.villain_top <= 100:
            raise SpotError("villain top % must be above 0 and at most 100")
        if self.effective_bb < 1 or self.pot_bb <= 0 or self.to_call_bb < 0:
            raise SpotError("need a stack of at least 1 bb, a positive pot and to-call >= 0")

    @classmethod
    def parse(cls, hero: str, board: str = "", **fields) -> Spot:
        a, b = parse_cards(hero)
        return cls(hero=make_combo(a, b), board=parse_cards(board) if board else (), **fields)

    @property
    def street(self) -> str:
        return {0: "preflop", 3: "flop", 4: "turn", 5: "river"}[len(self.board)]

    @property
    def raise_to_bb(self) -> float:
        """The villain's total bet: (pot + to call) / 2, since the pot holds both bets."""
        return (self.pot_bb + self.to_call_bb) / 2

    @property
    def has_villain_range(self) -> bool:
        return bool(self.villain_range) or self.villain_top is not None

    @property
    def villain_seat(self) -> str:
        return "bb" if self.seat == "sb" else "sb"

    def describe(self) -> dict:
        replayed = {}
        if self.legal is not None:
            replayed = {
                "history": list(self.history),
                "stack_behind_bb": self.stack_behind_bb,
                "legal": asdict(self.legal),
            }
        return replayed | {
            "hero": cards_str(self.hero),
            "seat": self.seat,
            "effective_bb": self.effective_bb,
            "board": cards_str(self.board),
            "pot_bb": self.pot_bb,
            "to_call_bb": self.to_call_bb,
            "pot_type": self.pot_type,
            "preflop": self.preflop,
            "villain_range": self.villain_range,
            "villain_top": self.villain_top,
            "mode": self.mode,
        }
