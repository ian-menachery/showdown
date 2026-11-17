# Plan: a live advisor for disclosed play-money games (Phases 8 to 11)

Written 2026-11-15 from Ian's scope ("Poker Solver: Scope"), reconciled with
what showdown already has. Ian's answers to the open questions on 2026-11-15
are recorded in SCOPE A6 and DECISIONS 29. This plan sets direction. Each phase
still ends at a gate pre-registered here, with the same discipline as Gates A
to F (DECISIONS 11).

## Ian's scope, in one place

- **What it is.** It watches the screen during play-money Poker Now games with
  friends and suggests the best action.
- **Who knows.** The friends know. Never real money.
- **Success.** Fast, sensible suggestions in live play. Speed beats precision.
- **V1.**
  - An existing screen-reading tool rather than our own vision.
  - An open-source solver (e.g. TexasSolver).
  - Suggest-only.
  - Heads-up first.
  - Preflop charts plus a simplified flop solve that takes seconds.
  - Every hand logged.
- **Parked.** Player typing, an exploitative action next to the GTO one,
  multiway, and auto-clicking.

## Ian's answers (2026-11-15)

| Question | Answer | Where it lives |
|---|---|---|
| How V1 reads the game, given that Poker Now's terms forbid scraping without written permission | Read the screen anyway, at his account's risk; also a self-hosted table | DECISIONS 29 |
| Amend DECISIONS 9 | Yes, the narrow exception: private play-money, everyone knows, suggest-only, visible, never ClubWPT | SCOPE A6, DECISIONS 29 |
| Postflop solving in scope | **Not yet ticked.** Only the speed spike runs until he approves it | open decision D2 |
| Flop speed | Spike TexasSolver on small trees, with a speed gate set in advance | Phase 8 |
| V1 pieces now | Heads-up preflop charts, a hand log from day one, a suggestion overlay | Phases 9 and 10 |

## What already exists, and what each V1 item needs

| Ian's V1 item | Already in showdown | New work |
|---|---|---|
| Heads-up first | Everything is heads-up: the push/fold game, the pokerkit adapter, grading | none |
| Preflop charts | Push/fold Nash at 1 to 20 bb. It is checked against HoldemResources (Gate D), and `PushFoldStrategy.grade` already gives the EV of each action | Charts above 20 bb (open decision D3) |
| Suggest-only | The trainer already shows the Nash action and its EV for every decision | A live input path and an overlay |
| Fast flop solve | Nothing. Postflop solving is out of scope | A TexasSolver bridge (AGPL-3.0, run as a separate program); a speed spike first |
| Screen reading | Nothing. Live reading was banned until A6 | A local reader (recommended) or Open Cluely (open decision D1) |
| Every hand logged | The analyzer reads PHH and PokerStars files | A live JSONL log of each read, suggestion, action and timing; later, a parser for Poker Now's own game log |
| Overlay | The play page is a local web page | A small always-on-top window, or a browser side panel, fed by the local server |

## Recommendations behind the plan

- **Read locally, not through a cloud AI (decision D1, recommended).** Open
  Cluely-style tools screenshot the screen and ask a cloud model what is on
  it.
  - That costs 2 to 5 s and an API fee for every read.
  - It sends your friends' screen names to a third party.
  - Several clones are built to hide from screen sharing, which DECISIONS 29
    rules out.
  - Poker Now draws a fixed layout, so reading it locally is the fast and
    private route:
    - capture the table window;
    - read the text with Windows' built-in OCR (Windows.Media.Ocr, already on
      this machine);
    - read suits by colour, with Poker Now's four-colour deck turned on.
- **TexasSolver runs as its own program.** Calling its console binary keeps
  its AGPL-3.0 code out of showdown's source; it is not linked. If showdown
  ever goes public, the README must say where TexasSolver comes from. The
  repo would not ship it.
- **Speed comes from a small game tree.** The tree is the decisions the
  solver considers. TexasSolver's own full-size flop benchmark takes about 175
  s on 6 threads. A heads-up tree with one or two bet sizes, no donk bets and
  a loose accuracy target should take seconds on 16 cores. Phase 8 measures
  this before anything depends on it.

## Phases and pre-registered gates

### Phase 8: spikes and decisions; no product code
- **S1, screen reading.** Ian saves at least 50 screenshots of his own Poker
  Now table across different spots. A reader script must pull out:
  - his cards and the board;
  - every stack, bet and the pot;
  - the button, and whose turn it is.
  **Gate S1:** 100% of cards correct, at least 99% of numbers correct, and at
  most 300 ms per read.
- **S2, TexasSolver speed.** After Ian approves the download, fetch
  TexasSolver's Windows console release, pinned by version and SHA-256. Solve
  heads-up single-raised and 3-bet pots at 25, 50 and 100 bb, with one or two
  bet sizes, over a fixed set of 20 flops. **Gate S2:**
  - median at most 10 s, 95th percentile at most 20 s;
  - exploitability at most 2% of the pot, as TexasSolver reports it.
- **S3, preflop source above 20 bb (decision D3).** Compare the options and
  record the choice:
  1. a small heads-up preflop solve with our own CFR, using simplified sizes
     and postflop value approximated by all-in equity;
  2. charts transcribed from a published source, only if their licence
     allows it;
  3. push/fold only, with "no suggestion" above 20 bb.
- If S2 passes and Ian approves, a DECISIONS entry brings postflop solving
  into scope, through TexasSolver only (decision D2).

### Phase 9: the advisor core and the hand log
- **A game-state model for heads-up hands:** cards, board, stacks, pot, bets,
  position and the action so far. It replays through the pokerkit adapter, so
  impossible states are rejected.
- **Preflop suggestions:**
  - at 20 bb or less, the push/fold solution and its per-action EVs (reused
    from `PushFoldStrategy`);
  - above that, the source chosen in S3.
- **Flop suggestions** from TexasSolver, using the S2 tree. Ranges come from
  the preflop strategy. Results are cached by spot.
- **The hand log** is local JSONL, one line per decision: the state read,
  the suggestion and its EVs, the action taken, and how long each step took.
- **Gate G:**
  - every state in a fixture of at least 40 spots gets the expected
    suggestion;
  - preflop suggestions at 20 bb or less equal the push/fold solution;
  - flop suggestions equal TexasSolver's answer for the same tree;
  - every decision in a scripted session appears in the log.

### Phase 10: the live reader and the overlay
- **The reader** runs S1's method on a loop over the Poker Now window, only
  while Ian has the advisor switched on.
- **The overlay** is a small always-on-top window: the suggested action, its
  EV against the alternatives, and the hand's log line. It is visible to
  screen sharing (DECISIONS 29).
- Both are served by the existing 127.0.0.1 server pattern (DECISIONS 23).
- **Gate H, at least 100 hands** in a private play-money Poker Now game where
  every player knows:
  - 100% of cards read correctly, checked against the hand log;
  - median time from read to suggestion at most 2 s preflop and at most 15 s
    on the flop;
  - no crash that loses a hand from the log.

### Phase 11: Poker Now game logs into the analyzer
- Poker Now lets players download a game's log (to be confirmed for private
  games). A parser turns it into PHH, so `showdown analyze` can review
  sessions after the fact.
- It is written against one real downloaded log, as DECISIONS 13 requires for
  any site format.
- **Gate I:** at least 99% of a real session's hands parse and reconcile with
  the log's own stack counts.

### Phase 12 (proposed 2026-11-15): exploit opponents' deviations

Ian made this a headline feature on 2026-11-15: "exploit opponents' deviating
play by playing exploitative myself, and this should help me figure out how".
It promotes two items his scope had parked: player-type identification, and
an exploitative action shown beside the GTO one.

What already exists to build on:
- **Exact best response.** `pushfold.sb_action_values` and
  `bb_action_values` give the EV of every hand against any opponent strategy.
  `cfr.best_response` does the same on any game tree.
- **Per-player stats from hand logs.** VPIP, PFR, 3-bet, WTSD and W$SD
  (DECISIONS 25). The V1 hand log, and Poker Now's own game logs (Phase 11),
  supply the hands.
- **Custom villain ranges for each decision.** V1 already has them
  (DECISIONS 32), as the manual lever.

The design, for Ian's review:
1. **An opponent model.** For each opponent, estimate their tendencies from
   logged hands:
   - in push/fold spots: how often they jam, and how often they call a jam, by
     stack depth;
   - postflop: how often they fold to a bet, and how often they bet when
     checked to.
   Each estimate is **shrunk toward Nash**: a beta prior worth k
   pseudo-hands, so a handful of hands can't swing it. The stats carry their
   sample size.
2. **The deviation as a range.** An opponent who calls jams at f%, against
   Nash's g%, is modelled as calling the top f% in Nash's own calling order.
   Hand strength stays ordered; only the cutoff moves.
3. **The exploit suggestion.** Compute the best response to that modelled
   range. Show it beside the Nash action, with the EV gained, and with the
   risk if the read is wrong: the EV lost against a Nash opponent.
4. **Postflop.** Narrow the villain's range by their tendencies; for example,
   a player who rarely folds to bets gets a wider range when calling. Show the
   bluff and value thresholds that follow from their fold rate. Locking their
   tendencies into a solver ("node locking") arrives with option 1.
5. **A validation gate (to pre-register).** In pokerkit simulations against
   bots with known deviations (calling too wide, jamming too tight), the
   exploit strategy must:
   - win at least its predicted EV gain, within 3 SE;
   - stay within a pre-set loss bound against a Nash bot.

Decisions for Ian when this phase starts:
- its priority against S1 and the reader;
- the shrinkage strength k;
- which postflop tendencies to track first;
- how the overlay shows two actions.

#### Phase 12, slice 1: the jam-vs-range helper (planned 2026-11-15, DECISIONS 36)

Ian supplies the read; the helper gives the best response to it. It answers
call or fold against an all-in at `bb_vs_jam`, `sb_vs_jam` and
`bb_vs_4bet_jam`:
- with `--villain` or `--villain-top N`, at any depth, beside the Nash or
  model answer;
- without a range, only where nothing answers today, using a labelled default:
  the top 20% for a first-in jam, the top 8% for a 4-bet jam.

Its equity is exact and instant: the matrix, weighted by the combos left after
the hero's cards (DECISIONS 36 has the proof). Gate J holds it to a Nash and
model best response, to board enumeration, to hand-worked spots, and to the
300 ms bar.

Build steps, each checked before the next:
1. **`src/showdown/live/jam.py`:**
   - the class weights of a whole-class range, or an error for a partial one;
   - the exact equity E;
   - the price, the call or fold, the EV relative to folding, and the close
     flag.
2. **`Spot` and `Advisor`:**
   - `villain_top` and its checks;
   - the routing: a range from Ian, then Nash or the model, then the
     default, then no suggestion;
   - the note comparing the answer with Nash or the model;
   - `--villain-top` postflop.
3. **CLI:** `--villain-top`, and output that prints the EV against folding,
   "close" and the Nash or model note.
4. **Gate J tests:**
   - `tests/test_gate_j.py`, with bars 1, 3 and 4, and the fixture
     `tests/fixtures/live/jam_spots.toml`;
   - `tests/test_gate_j_slow.py`, with bar 2;
   - the two Gate G spots that move by design;
   - the latency script extended to the new spots.
5. **Record:** GATES.md, this plan's status, memory; commit, push, and
   `py gate.py --full`.

Later slices of Phase 12, unchanged above: the opponent model built from
logged hands, shrinking toward Nash, and the simulation gate.

### Phase 13 (planned 2026-11-15; steps 1–3 built, Gate X FAIL on X3): postflop solving ahead of time (D2, DECISIONS 40)

Gate S4 showed b-inary's postflop-solver takes 0.5 to 2 minutes per flop on
this laptop. That is too slow for live play, but fine between sessions and
overnight. Its node locking works. Ian chose two uses:
- **Exploit solves:**
  `showdown postflop exploit --pot-type srp --stack 50 --flop Kc7d6c --hero sb --read never-folds`
  gives the hero's flop strategy with and without one locked villain read
  (never folds, over-folds, never bets, always bets), with EVs. Gate X checks
  that the lock holds, that every solve converges, and that the strategy
  moves the right way on 10 flops.
- **An overnight flop library:**
  - 3-bet pots at 100 bb, and single-raised pots at 25, 50 and 100 bb;
  - all 1,755 suit-distinct flops, solved in coverage order;
  - started by Ian, on AC power, and resumable.

  `showdown advise` looks a flop decision up there when it can, and keeps the
  equity helper otherwise. Gate L checks accuracy, suit symmetry, stability,
  latency, and that no Gate G or Gate J answer moves.

Both use the preflop model's ranges, the model's open and 3-bet sizes, tree T1,
and a 2% target. The bridge is committed in `bridges/postflop/` under
AGPL-3.0. The solver and the binary stay gitignored.

Build order:
1. The bridge and `showdown postflop build`.
2. Exploit solves, then Gate X.
3. The library builder.
4. Ian starts the first overnight run (3BP100, about 15 hours over one or two
   nights).
5. The advisor lookup, then Gate L.

Rough compute, from S4's times:

| Spot | Per flop | 1,755 flops |
|---|---|---|
| 3BP100 | about 30 s | about 15 h |
| SRP25 | about 50 s | about 24 h |
| SRP50 | about 100 s | about 49 h |
| SRP100 | over 2 minutes, not yet measured | more than 60 h |

The single-raised libraries therefore grow over several nights. Coverage is
reported as the share of dealt flops solved.

Measured with the model's ranges, which are wider than S4's top-% ones:
- **3BP100:** the builder's first real flop (Qc8d3h) took 67 s. At that rate
  all 1,755 flops take about 33 h, or four or five 8-hour nights.
- **SRP50:** Gate X's 10 baselines had a median of 115 s, about 56 h in all.

Each flop's file is about 9 KB gzipped.

### Later, each needing its own amendment first
- **A self-hosted table for friends (Ian ticked this).** It means serving
  beyond 127.0.0.1, which DECISIONS 12 forbids. It would replace screen
  reading, because the game state would be ours.
- **Parked by Ian:** player typing from the hand log; an exploitative action
  next to the GTO one; multiway pots.
- **Auto-clicking (parked by Ian).** It would make the advisor a bot.

## Status, 2026-11-15

- **D1, D4 and D6 are decided** (DECISIONS 30): a local reader, TexasSolver
  downloaded and pinned, and practice hands from Poker Now self-play, the
  public datasets and PokerStars play money (after sessions only).
- **Gate S2 failed** (GATES.md). Single-raised pots never converged in 120 s,
  and 3-bet pots took 50 to 76 s.
- **Ian's fallback** (DECISIONS 31): V1 is preflop suggestions plus a
  postflop equity and pot-odds helper. A precomputed flop library, with live
  turn and river solves behind a new gate S2b, comes next.
- **Gate G passed** (GATES.md): the V1 advisor, `showdown advise`.
- **D3 is decided** (DECISIONS 33, 34; SCOPE A7): our own preflop model above
  20 bb, solved at R_oop 0.90, with a "depends on R" flag from R 0.85 and 0.95.
  **Gate P passed** (GATES.md).
- **The model is in the advisor** (DECISIONS 35; Gate G extended, PASS). Above
  20 bb, `showdown advise` answers the model's six preflop decisions with the
  mix, the R flag and a raise-size note. The model is never used where it reaches
  a decision in less than 0.1% of deals. The postflop helper defaults to the
  model's weighted ranges, and `--ranges fixed` restores the fixed ranges.
- **Phase 12, slice 1 is built** (DECISIONS 36; SCOPE A8; Gate J PASS): the
  jam-vs-range helper. `--villain` or `--villain-top N` gives the best
  response to Ian's read against any jam, beside the Nash or model answer.
  Labelled defaults fill the jams the model skips.
- **Push/fold exploit charts are built** (DECISIONS 37, PASS):
  `showdown pushfold exploit <stack> --villain-calls N | --villain-jams N`
  prints the best response to a read, its gain over Nash, and its risk if the
  read is wrong.
- **Gate S4 failed** (GATES.md). b-inary's postflop-solver is 4 to 10 times
  faster than TexasSolver: 3-bet-pot flops take 7 to 18 s. Single-raised pots
  still take 28 s to over 120 s. Its node locking works: against a BB who never
  folds, the solved SB value-bets more and bluffs less with S2's top-% ranges.
  With the model's ranges it does not (Gate X).
- **The PHH leak study is done** (DECISIONS 39, amended: the online hands have
  no stacks, so it has no jam measures). It covers 21.6 M hands from 2009
  (`docs/human-leaks.md`). The 3.1 M heads-up hands give priors for the
  opponent model:

  | VPIP | PFR | 3-bet | Flop c-bet | Fold to flop c-bet |
  |---|---|---|---|---|
  | 49% | 34% | 14% | 63% | 45% |

  About a fifth of the regulars at 6-max are loose (VPIP at least 40%).
- **D2 is decided** (DECISIONS 40; SCOPE A9): postflop solving ahead of time,
  as exploit solves and an overnight flop library (Phase 13).
- **Exploit solves are built** (Phase 13, build steps 1 and 2):
  - the AGPL bridge in `bridges/postflop/`, built by `showdown postflop build`;
  - `showdown postflop exploit`.

  **Gate X failed on X3 only** (GATES.md):
  - The lock holds, every solve converges (SRP50: median 115 s, max 508 s),
    and the hero bluffs more against `over-folds` on all 10 flops.
  - Against `never-folds`, the SB's weakest third bet less on only 3 of 10
    flops. With the model's ranges the SB already bets its 33% size with most
    of its range, and the lock also takes away the BB's raise.
  - The bridge reproduces S4's opposite result with S4's ranges, so this is
    not a bug.
- **The library builder is built** (step 3; DECISIONS 40 amended 2026-11-16
  on flop order, storage and power):
  - `showdown postflop library build --spot 3BP100 --until 07:00` and
    `showdown postflop library status`;
  - it is resumable, refuses to run on battery, and keeps the laptop awake;
  - nothing is in `data/library/` yet.

  Step 4, the first overnight 3BP100 run, starts only when Ian runs it.
- **The audit, and the plan to live play (2026-11-16).** A read-only audit
  found three things:
  - postflop advice is equity against the opponent's whole preflop range,
    unchanged by the bet faced;
  - there is no hand state;
  - the preflop model leans on jams.

  The plan's steps:
  1. replay a saved hand;
  2. the live tracker and overlay;
  3. range narrowing (the flop library, then S2b);
  4. a preflop re-solve;
  5. the opponent model.
- **Step 1 is built: Gate R PASS** (DECISIONS 41).
  - `showdown replay HAND.phh --hero sb|bb` gives the state and advice at
    each of the hero's decisions.
  - The hand state comes from pokerkit, and the advice keeps to legal
    actions and sizes. The audit's "BET 33.75 bb" with 2.5 bb behind is now
    "ALL-IN 2.5 bb".
  - The river trace confirms both betting lines still reach the equity
    calculation with the same range. Narrowing it is step 3.
- **Still open:**
  - S1, which waits for Ian's screenshots;
  - D5, the self-hosted table.

## Open decisions for Ian

| # | Decision | Recommendation |
|---|---|---|
| D1 | Read locally, or send screenshots to a cloud AI (Open Cluely) | Local: fast, free, and friends' names stay on this machine |
| D2 | Bring postflop solving into scope | Decided (DECISIONS 40, SCOPE A9): postflop-solver, ahead of time only; exploit solves and an overnight flop library |
| D3 | Preflop source above 20 bb | Decided: our own model at R 0.90 (DECISIONS 33, 34); Gate P PASS |
| D4 | Approve downloading the TexasSolver release (AGPL-3.0, from GitHub; the file and size will be stated before download) | Needed for S2 |
| D5 | A self-hosted table, and its amendment to DECISIONS 12 | Later. Screen reading comes first, as Ian chose |

## Risks

- **Poker Now could ban the account for scraping.** Ian accepted this. The
  reader only looks at his own screen and never touches Poker Now's network
  or code.
- **The reader is brittle.** A theme or layout change breaks it. S1 pins a
  layout and four-colour cards, and the reader refuses to suggest when a read
  is incomplete.
- **TexasSolver may not reach seconds.** If S2 fails, fall back to a
  precomputed flop library, or to preflop-only V1, and record the choice in
  DECISIONS.
- **The AGPL licence.** Running TexasSolver as a separate program is fine for
  private use. Going public (SCOPE Open question 5) needs the licence notes.
