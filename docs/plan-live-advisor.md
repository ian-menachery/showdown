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

### Later, each needing its own amendment first
- **A self-hosted table for friends (Ian ticked this).** It means serving
  beyond 127.0.0.1, which DECISIONS 12 forbids. It would replace screen
  reading, because the game state would be ours.
- **Parked by Ian:** player typing from the hand log; an exploitative action
  next to the GTO one; multiway pots.
- **Auto-clicking (parked by Ian).** It would make the advisor a bot.

## Open decisions for Ian

| # | Decision | Recommendation |
|---|---|---|
| D1 | Read locally, or send screenshots to a cloud AI (Open Cluely) | Local: fast, free, and friends' names stay on this machine |
| D2 | Bring postflop solving into scope through TexasSolver | Decide after S2's numbers |
| D3 | Preflop source above 20 bb | Decide after S3 |
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
