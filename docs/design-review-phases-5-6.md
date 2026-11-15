# Design review: pokerkit facts and definitions for Phases 5 and 6

Written 2026-11-14 by a read-only review run before Phases 5 and 6 were built.
Every pokerkit claim was checked against pokerkit 0.7.7's source and against
small replays in `.venv` with `-W error`. DECISIONS 23 to 27 are built on this
note. Where an entry and this note disagree, the entry wins.

## pokerkit 0.7.7

**Seat roles in heads-up.** pokerkit swaps the blinds when there are two
players. In
`NoLimitTexasHoldem.create_state(automations, True, 0, (1, 2), 2, (2S, 2S), 2)`:
- player 0 is the **big blind** (`bets == [2, 1]`);
- player 1 is the **small blind and button**, and acts first preflop;
- the BB acts first after the flop.

PHH and the PokerStars parser use the same order:
- heads-up: p1 = BB, p2 = SB/BTN;
- 3 or more players: p1 = SB, p2 = BB, and the last seat is the button.

**Integer chips.**
- Scale by 2: blinds (1, 2), min_bet 2, stacks 2S, and bb = chips / 2.
- Replays reproduce DECISIONS 22 exactly:
  - SB folds: −1 chip.
  - BB folds to the jam: +2.
  - Call: ±2S, or 0 on a tie.
- The PokerStars parser returns cash amounts as `Decimal`. Convert them before
  any float arithmetic: `Decimal * float` raises.

**Dealing.**
- Automate ANTE_POSTING, BET_COLLECTION, BLIND_OR_STRADDLE_POSTING,
  HOLE_CARDS_SHOWING_OR_MUCKING, HAND_KILLING, CHIPS_PUSHING and CHIPS_PULLING.
  Keep `Mode.TOURNAMENT`, which has no runout-count step.
- Do **not** automate HOLE_DEALING, BOARD_DEALING or CARD_BURNING. pokerkit
  shuffles with the global `random`, and an automatic burn can take a card we
  later deal.
- Instead, draw the cards from our own `random.Random(seed)`:
  1. `deal_hole(cards, player)`.
  2. Then, street by street: `burn_card('??')` while `can_burn_card()`, then
     `deal_board(...)` with 3, 1 and 1 cards.

**Jam and call.**
- If `can_complete_bet_or_raise_to()`, call
  `complete_bet_or_raise_to(max_completion_betting_or_raising_to_amount)`.
  Otherwise call `check_or_call()`.
- At 1 bb the BB is all-in from posting its blind. The SB's jam is a call, and
  the BB never acts (`actor_index` is None).

**Replaying a HandHistory.**
- `iter(hh)` and `hh.state_actions` yield **the same mutable State object**
  every time. Read what you need at each yield; never store the states.
- After the replay, `state.operations` is a typed log:
  - `CheckingOrCalling.amount` is the extra chips put in;
  - `CompletionBettingOrRaisingTo.amount` is the total amount raised to;
  - `ChipsPushing.amounts` is what each player received.
- `state.payoffs` is the net result in chips, with uncalled bets already
  returned.
- Count streets by counting `BoardDealing` operations. `state.street_index`
  moves on before the closing call is yielded.
- Do not detect showdowns from `statuses`: a muck (`pN sm`) sets the status to
  False and logs no Folding.
- Do not use `ChipsPushing.board_index` either: HAND_KILLING makes it None.
- The all-in snapshot is the first yield where `state.all_in_status` is true and
  the board has fewer than 5 cards. At that moment `tuple(state.pots)` already
  includes dead money and excludes uncalled bets.
- Hole cards come from the `HoleDealing` operations.

**Missing show actions.** If a PHH lacks `sm` at showdown, the replay shows `()`
on its own: the cards become `??` and the pot splits silently. So a hand counts
as **parsed** only when the replayed stacks equal `finishing_stacks`. The
Pluribus files carry `players`, `finishing_stacks` and the `sm` actions.

**`HandHistory.from_pokerstars(text)`.**
- Pass the whole file, read with `read_text(encoding="utf-8-sig")`.
- Each hand starts with "PokerStars " at the start of a line, and hands are
  separated by at least 2 blank lines.
- Only "Hold'em No Limit" is supported. Antes and rake are not parsed.
- `winnings` is usually None.
- Only the hero's "Dealt to" line and "shows" lines give cards.
- It is a generator. Its `StopIteration.value` is the number of hands found. A
  bad hand prints a traceback and a warning and is skipped, so failures = hands
  found − hands yielded + replay errors.
- Every hand also raises a time-zone UserWarning.

## Definitions (for DECISIONS 25 to 27)

**General rules.**
- A raise is any `CompletionBettingOrRaisingTo`, short all-ins included.
- Posting a blind, ante or straddle is never voluntary.
- A preflop **opportunity** means the player took at least one preflop action.
  Walks and blind-posting all-ins with no decision are excluded.

**The stats.**
- **VPIP:** hands with a preflop call above 0 or a raise, over opportunities.
- **PFR:** hands with at least one preflop raise, over opportunities.
- **3-bet opportunity:** the player acts preflop facing exactly one raise, is
  not that raiser, and `can_complete_bet_or_raise_to()` is true. It counts at
  most once per hand, and a limp followed by facing the open counts. A 3-bet is
  made when the player raises at that decision.
- **Saw flop:** a flop was dealt and the player had not folded. All-in players
  count.
- **WTSD:** the hand ends with at least 2 players who never folded, and the
  player is one of them. Mucks count, and so do preflop all-ins that run out.
  WTSD% = WTSD hands / saw-flop hands.
- **W$SD:** WTSD hands where the player's `ChipsPushing` receipts total more
  than 0, over WTSD hands. Chops and side pots count; returned uncalled bets do
  not.
- **bb/100:** 100 × total payoffs / bb / hands dealt, walks included, with
  bb = `max(blinds_or_straddles[:2])`.

**All-in EV.**
- A hand qualifies when all four hold:
  - no more betting is possible (`all_in_status`);
  - at least 2 players have not folded;
  - the board has fewer than 5 cards;
  - every remaining hand is known.
- At that first moment, for each pot k (amount A_k, eligible set S_k):
  EV = Σ_k A_k·e_k − C.
  - e_k is the player's expected share of pot k over uniform runouts. A tie
    splits 1/m among the m best hands in S_k.
  - C is the player's total contribution after uncalled bets are returned.
- Only the hole cards of players still in the hand are removed. Folded cards
  stay in the deck, as on a site.
- Every player in a qualifying hand is adjusted (a folded player's EV equals
  their actual result). Other hands use the actual result.

**Heads-up grading.**
- Only 2-player hands with an effective stack of at most 20 bb. The effective
  stack is min(SB, BB starting stack) / bb, before the blinds.
- Depth = floor(eff + 0.5), clamped to 1 to 20.
- The SB is graded only if its first action is a fold or an all-in. The BB is
  graded only when it faces an SB jam of at least the effective stack.
  Everything else is counted as off-tree.
- EVs:
  - SB: EV(jam | i) = Σ_j w_ij [(1 − c_j) + c_j·S(2E_ij − 1)] / Σ_j w_ij,
    against EV(fold) = −0.5.
  - BB: weight by w_ij·p_i; EV(fold) = −1.
  - Loss = max EV − chosen EV.

## Risks and the tests that catch them

1. **Seats swapped, or chips left in pokerkit units.**
   - Why Gate E alone is weak here: at 10 bb the per-hand SD is about 4.5 bb,
     so 3 SE is about 0.1 bb. A seat swap moves the result by about 2.8 SE, and
     a factor-2 chip error by about 1.4 SE, so either could still pass.
   - Tests: assert `bets == [2, 1]` and that the first actor is seat 1; check
     every Gate E hand against the model's payoffs (−0.5, +1, ±S, 0); run a
     binomial test of jam and call rates per class.
2. **Silent showdown splits.**
   - Count a hand as parsed only when replayed stacks equal
     `finishing_stacks`.
3. **The mutable State, or the wrong signals.** Build fixture hands for:
   - a closing preflop call;
   - a muck;
   - a heads-up hand (p1 = BB);
   - a walk;
   - a limp, then a re-raise;
   - a short all-in;
   - an uncalled bet;
   - a 3-way side pot;
   - a chop;
   - a river all-in (no adjustment).

   Write each hand's expected flags before running the code.
4. **Monte Carlo cannot meet a 1e-6 bar.**
   - Put the fixture's multiway all-ins on the turn, where they are exact.
   - Test the Monte Carlo path separately: it must land within 3 SE of exact
     enumeration on a 3-way flop.
   - A heads-up exact preflop takes about 5 s, so cache by `canonical_pair`.
5. **Grading formula.**
   - The per-class best-response sums must reproduce
     `closed_form_exploitability`.
   - Every action that Nash plays purely must lose about 0.
6. **Edge cases.**
   - At 1 bb the BB has no decision.
   - Script hands at 1 and 2 bb in both seats.
   - Count decisions, not hands, in the session summary.
7. **Reproducibility and server safety.**
   - The same seed must give identical results, under
     `-W error::UserWarning`.
   - Keep a lock per session.
   - Reject requests whose Host is not 127.0.0.1 or localhost, and require a
     per-launch token on POSTs.
   - Never send the bot's cards before showdown.
   - Every fetch path in the page must have a route.
