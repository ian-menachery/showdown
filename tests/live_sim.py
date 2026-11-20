"""Random heads-up hands played by pokerkit, for Gates R and T (DECISIONS 41, 42).

Stacks of 10 to 100 bb each, blinds 5/10 chips (0.1 bb a chip). Cards come from a seeded
shuffle, never pokerkit's own deck; actions are random and legal, with sizes drawn between
pokerkit's minimum and maximum.
"""

import random
import warnings

from pokerkit import Automation, HandHistory, NoLimitTexasHoldem

from showdown.equity.cards import card_str

AUTOMATIONS = (
    Automation.ANTE_POSTING,
    Automation.BET_COLLECTION,
    Automation.BLIND_OR_STRADDLE_POSTING,
    Automation.CARD_BURNING,
    Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
    Automation.HAND_KILLING,
    Automation.CHIPS_PUSHING,
    Automation.CHIPS_PULLING,
)


FOUR_X_OPENING = (25, 100, "cc")
"""Gate Q bar 6's 4x hands (DECISIONS 49's amendment): open to 2.5, 3-bet to 10, call."""


def play(rng: random.Random, chips: tuple[int, int] = (100, 1000), opening: tuple = ()):
    """(the finished pokerkit state, the starting stacks, the PHH actions without showdowns).

    `opening` forces the first actions: a raise-to in chips, or "cc". Without it, the hands
    are Gate R's and Gate V's.
    """
    stacks = (rng.randint(*chips), rng.randint(*chips))
    forced = list(opening)
    with warnings.catch_warnings():  # pokerkit warns that our seeded cards aren't its deck's
        warnings.simplefilter("ignore")
        state = NoLimitTexasHoldem.create_state(AUTOMATIONS, True, 0, (5, 10), 10, stacks, 2)
        deck = [card_str(c) for c in range(52)]
        rng.shuffle(deck)
        actions = []
        while state.status:
            if state.can_deal_hole():
                cards = deck.pop() + deck.pop()
                actions.append(f"d dh p{state.hole_dealee_index + 1} {cards}")
                state.deal_hole(cards)
            elif state.can_deal_board():
                cards = "".join(deck.pop() for _ in range(3 if not state.board_cards else 1))
                actions.append(f"d db {cards}")
                state.deal_board(cards)
            elif state.actor_index is not None:
                p = f"p{state.actor_index + 1}"
                if forced:
                    move = forced.pop(0)
                    if move == "cc":
                        state.check_or_call()
                        actions.append(f"{p} cc")
                    else:
                        state.complete_bet_or_raise_to(move)
                        actions.append(f"{p} cbr {move}")
                    continue
                r = rng.random()
                if state.checking_or_calling_amount > 0 and r < 0.15:
                    state.fold()
                    actions.append(f"{p} f")
                elif state.can_complete_bet_or_raise_to() and r > 0.7:
                    lo = state.min_completion_betting_or_raising_to_amount
                    hi = state.max_completion_betting_or_raising_to_amount
                    amount = lo + int((hi - lo) * rng.random() ** 3)
                    state.complete_bet_or_raise_to(amount)
                    actions.append(f"{p} cbr {amount}")
                else:
                    state.check_or_call()
                    actions.append(f"{p} cc")
            else:
                break
    return state, stacks, actions


def phh_text(stacks, actions) -> str:
    return (
        "variant = 'NT'\nante_trimming_status = true\nantes = [0, 0]\n"
        "blinds_or_straddles = [5, 10]\nmin_bet = 10\n"
        f"starting_stacks = [{stacks[0]}, {stacks[1]}]\nactions = {actions!r}\n"
    )


def full_history(state) -> HandHistory:
    """The finished hand with its showdown, as pokerkit records it."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        game = NoLimitTexasHoldem(AUTOMATIONS, True, 0, (5, 10), 10)
        hh = HandHistory.from_game_state(game, state)
    hh.players = ["Villain", "Hero"]
    hh.finishing_stacks = list(state.stacks)
    return hh
