# Plan: a six-max preflop trainer

**Goal.** A practical study tool for Ian's six-max cash games: tables with several
limpers, and sometimes an ante of the small blind from every player. It shows the
opponents' assumed profile and ranges, grades a decision as good, marginal or worth
reviewing, and finds recurring leaks in his completed hands.

**Scope.** Study and training only (SCOPE A12, A13; DECISIONS 29, 53). Never advice
during a hand, never screen reading, nothing for ClubWPT, nothing for a real-money table.
Everything runs between sessions, on spots typed in or on completed hands.

**Status (2026-11-22).** Step 1 is built as `showdown sixmax`. Gate M failed on bar 3
only: from the HJ and SB the engine opens wider than PokerStrategy's chart, because the
fitted blinds fold more (GATES.md). Bars 1 and 2 pass. What it can be trusted for is in
[`sixmax-preflop.md`](sixmax-preflop.md).

Ian chose (2026-11-22) to keep bar 3 as a documented limit. He also chose to add a
"standard" profile, whose blinds defend like a modern chart, before step 2.
- **The profile** is DECISIONS 54, with the BB fitted to VIP-Grinders' table.
- **Gate M2** also failed on its chart bar only. The SB still opens everything, and early
  seats have too few hands that keep their kind of action across the band.
- **Step 2,** the drill trainer, is DECISIONS 55, Gate K. It uses "standard" by default
  and grades the kind of action only.

| Step | What | State |
|---|---|---|
| 1 | The spot engine as a CLI | built; Gate M FAIL, bar 3 only |
| 1b | The "standard" profile | built; Gate M2 FAIL, bar 3 only |
| 2 | A drill trainer on the engine | built, `showdown sixmax drill`; Gate K PASS |
| 2b | R 0.75 out of position and standard's limpers from loose-passive | built (DECISIONS 57); Gate M4 FAIL, bar 3 only (7 stable classes at UTG, minimum 10) |
| 3 | Six-max hand review by spot | built, `showdown sixmax review` (DECISIONS 58); Gate W PASS |

**Steps 2b and 3 (2026-11-22).**
- **Gate M4.** With both fixes, the SB opens 78 classes instead of 169. Every hand stable
  across the band agrees with PokerStrategy at the HJ, CO and SB. UTG has only 7 stable
  hands. The record is in GATES.md.
- **Hand review** reads PHH and PokerStars text. Gate W ran it on the fixture and on
  Pluribus's 10,000 hands. The check on Ian's own hands waits for a file from an allowed
  source: a Poker Now log needs Phase 11's parser first.

**The plan is done** (Ian, 2026-11-22).
- **Gate M4's UTG count stays a documented limit.** The band is not narrowed.
- **Left for later, each needing its own entry:**
  - the limp EV floor, where a raise behind a limp counts as a fold. It makes premium
    limps look like leaks in review (`sixmax-preflop.md`, "Limping");
  - reviewing Ian's own hands, once he has an allowed file.

---

## Step 1: the spot engine as a CLI

`showdown sixmax SEAT HAND --limpers K --ante A --profile P` prints the assumed ranges,
each action's EV, the best action and a tier (clear, close or review).

**Reuses:**
- the exact 169×169 matrix (`equity/matrix.py`), for pots that go heads-up;
- eval7's `evaluate` and `multiway.py`'s split rule, for 3+ way pots;
- `live/jam.py`'s `jam_equity`, for the hero's equity against a re-raise range;
- `equity/ranges.py`, for range strings;
- DECISIONS 39's PHH zip and spike pattern, for the profiles;
- the "depends on R" flag (`preflop_model.py`) and `jam.py`'s `CLOSE` flag, as the model
  for the band.

**Changes:** a new module, `src/showdown/sixmax.py`; a `sixmax` subcommand; the profiles
in `data/sixmax_profiles.json`. Nothing in the heads-up tree, the live advisor or the
Poker Now path.

**How we'll tell it is useful:**
- Gate M passes: closed forms exact, the ante, limper and size directions hold, and
  unopened answers agree with PokerStrategy's opens on clear hands.
- The A5s example (BTN, 2 limpers, 0.5 ante, loose-passive) prints ranges, EVs and a
  tier.
- Ian runs it on five spots from his own games and finds the answers sensible, or names
  one that isn't. A named bad answer becomes a test.
- `docs/sixmax-preflop.md` says what it can and cannot be trusted for.

## Step 2: a drill trainer

Deal a random spot (seat, limpers, ante, profile, hand), show the profile and ranges,
ask for an action, then grade it and say why.

**Reuses:**
- `sixmax.chart`, precomputed for every spot. That is 102 charts of 169 classes, a few
  minutes on 12 cores, saved as data, so a drill answers instantly;
- the tier, for the grade:
  - **good:** the best action, or any action of the same kind when only the size is
    close;
  - **marginal:** an action that wins somewhere in the band;
  - **review:** anything else, with the bb it gives up;
- the push/fold trainer's page and server (`bot/server.py`, 127.0.0.1 only), or a plain
  CLI quiz first.

**Changes:** a chart cache file and its builder, a drill loop, and a session log of
answers (local, gitignored).

**How we'll tell it is useful:**
- Every graded answer equals the engine's chart for that spot (a gate bar).
- Over about 200 drills across a week, Ian's misses on clear spots fall. The session
  log shows it.
- Ian says the "why" line (the ranges and the deciding EVs) teaches him something in
  most drills he misses.

## Step 3: six-max hand review by spot

Read Ian's completed hands, find each preflop decision that fits an engine spot, grade
it, and group the misses into recurring leaks.

**Reuses:**
- the hand-history parsers (`hh/parse.py`: PHH and PokerStars text through pokerkit), and
  the Poker Now log parser once Phase 11 builds it;
- `hh/stats.py`, for the usual stats beside the review;
- the engine, for each decision's tier and the bb lost;
- the opponent model's playstyle labels (DECISIONS 50), to pick a profile per table.

**Changes:**
- a spot classifier: seat, limpers ahead, ante, unopened or limped. Raised pots are
  skipped and counted;
- a leak report: decisions by tier, bb lost on clear spots, and the top recurring
  patterns, such as "overlimps where an iso is clear" or "folds on the button behind
  limpers";
- the analyzer learns to keep the ante and each player's seat, which it counts today but
  drops.

**How we'll tell it is useful:**
- On a hand-labelled fixture, every covered decision is classified to the right spot (a
  gate bar).
- On Ian's own completed hands, most preflop decisions in unopened and limped pots are
  covered. Skips are counted by cause.
- The report names two or three leaks with their bb cost. Ian reviews five hands per leak
  and agrees they are real.

Hand files come only from allowed sources: play-money Poker Now logs, and never
ClubWPT except through a file the site itself lets him download (DECISIONS 13). Hand
histories are never committed.

---

## Decided without Ian

Each is the reversible option, logged as the brief asks:
- **The study-only rule** went in as a new amendment row, A13, because A12 had already
  been pushed. SCOPE allows only dated rows, not edits.
- **Up-front decisions.** Ian answered them directly in this session on 2026-11-22, all
  as recommended. The master session got the same list afterwards, for its record.
- **The CLI shape.**
  `showdown sixmax SEAT HAND [--limpers K] [--ante A] [--profile P] [--samples N] [--seed S]`.
- **Limpers** are non-blind seats. With the hero in the BB, the SB folded.
- **Hand strength** is equity against a random hand, so a limp range is the band below
  the open-raise range.
- **Gate M bar 1's limped pot** is the hero in the BB checking behind a fixed-range
  limper, which can be matched to 1e-9.
- **Seeds:** one deal per seat, limper count and profile, shared by both antes and all
  actions.
- **The drill grade** in step 2 is settled in DECISIONS 55. Ian approved it through the
  master session.
- **Building step 2 after Gate M2's FAIL.** Ian asked for drills next, and Gate K tests
  the trainer, not the profile. The SB caveat is shown in `sixmax-preflop.md`, and the
  fix for SB opens is left for Ian to pick.
