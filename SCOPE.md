# SCOPE: showdown

Committed before any implementation. Change it only with a dated row in the
Amendments log at the bottom, never by a silent edit.

**Repo:** `ian-menachery/showdown` (private)
**Package:** `showdown`
**Started:** 2026-11-14
**Time box:** about 40 hours as a soft target, with no hard stop (A1). The
gates still apply.

**One line:** A heads-up poker lab in Python. It has a CFR solver checked
against known answers, an equity engine, a push/fold bot you can play against,
and a hand-history analyzer. One game ties them together.

---

## The spine: heads-up push/fold

Four tools could easily become four unrelated toys. The thread that joins them
is the heads-up push/fold game: the small blind jams or folds, the big blind
calls or folds, at effective stacks of 1 to 20 big blinds.

- The **equity engine** builds the 169×169 preflop all-in equity matrix. That
  matrix is the game's payoff table.
- The **CFR solver** solves the game at each stack depth. Before that, it has to
  be proven on Kuhn and Leduc, where the right answers are known.
- The **bot** plays the solved strategy inside a real no-limit hold'em state
  machine. It grades your jam and call decisions in big blinds lost against Nash.
- The **hand-history analyzer** uses the equity engine for all-in EV adjustment.
  Where a hand fits the game, it applies the same grading.

Each part has its own correctness gate against an outside answer, so a bug in
one part cannot hide inside another.

## Borrow vs build

Use open-source code for the commodity parts. Build the parts that are the point.

| Part | Borrowed (pip, pinned) | Built here |
|---|---|---|
| NLHE rules and state machine | pokerkit 0.7.7 (MIT) | thin adapter, bot seat |
| 7-card hand evaluation | eval7 0.1.11 (MIT), `evaluate` only | none |
| Hand-history parsing | pokerkit parsers and the PHH format | stats, all-in EV, grading |
| Kuhn and Leduc rules | none (small, and owning the tree is the point) | both games, behind one interface |
| CFR, CFR+, best response, exploitability | none | all of it |
| Equity: combos, ranges, enumeration, 169×169 matrix | none | all of it |
| Push/fold game and charts | none | all of it |
| Reference answers for tests | OpenSpiel 2.0.2, phevaluator 0.6.0 (both Apache-2.0), dev only | none |

"Borrowed" means installed through pip at a pinned version. It does not mean
copying source files into this repo (DECISIONS 3).

---

## In scope

- A small extensive-form game interface, with Kuhn, Leduc and push/fold
  implemented on it.
- Vanilla CFR and CFR+, exact best response, exploitability.
- Equity: combo and range parsing, exact heads-up enumeration on any board,
  seeded Monte Carlo with a stated standard error, and the 169×169 preflop
  matrix cached as a data file.
- Push/fold solutions at 1 to 20 bb, printed as 13×13 charts.
- Browser play on a local page that `showdown play` serves on localhost only
  (A2):
  - a push/fold trainer against the solved bot, in either seat, showing bb lost
    on each decision;
  - Leduc against the CFR bot.
- Hand-history analyzer. It parses PHH files and PokerStars-format text (through
  pokerkit). It reports VPIP, PFR, 3-bet, WTSD, W$SD and bb/100, plus all-in
  EV-adjusted bb/100. It grades heads-up hands at 20 bb effective or less
  against push/fold Nash.
  - The primary dataset is the public phh-dataset (A3).
  - ClubWPT Gold hands are supported only through a file the site itself lets
    you download, or by hand transcription into PHH (A3, DECISIONS 13).
- One CLI, `showdown`, with subcommands `solve`, `equity`, `play` and `analyze`.

## Explicitly out of scope

This list is load-bearing. Anything on it is a scope amendment, not a good idea.

- **Anything that touches live play,** with one narrow exception (A6,
  DECISIONS 29): a suggest-only advisor for private play-money games where
  every player knows. Outside it, there is no HUD, overlay, table scraping,
  folder watcher during a session, or real-time advice, and the analyzer reads
  completed hand histories only (DECISIONS 9).
- Connecting to any real-money site, and bots that play on any site.
- Full NLHE solving, postflop solving, any abstraction beyond push/fold, limp or
  min-raise options, antes, ICM.
- Three or more players in any solver.
- Neural networks, Deep CFR, reinforcement learning.
- Writing our own hand evaluator or NLHE rules engine.
- Site formats that pokerkit does not parse, GGPoker included.
- Serving the play page anywhere except localhost, and any public deployment
  (A2).
- Scraping, screen-reading or OCR of any poker client, ClubWPT Gold included
  (A3).
- Performance rewrites (Cython, Numba, Rust) unless a gate fails on runtime.
  Even then, a DECISIONS entry comes first.
- Database, accounts, hosting.

## Done, defined as checks that pass or fail

1. `py gate.py` exits zero. That means ruff check passes, ruff format --check
   passes, pytest passes with coverage of at least 80% on `showdown`, the tree is
   clean, and HEAD is pushed.
2. Gates A to F below all PASS.
3. `showdown play` opens a local page. A full push/fold trainer session and a
   full Leduc session can each be played there in the browser (A2).
4. `showdown analyze <file>` prints the stats table for the phh-dataset Pluribus
   hands (A3).
5. The README states what is borrowed and under which license, what is built,
   every gate result, and the known limits.

---

## Pre-registered gates

These thresholds are set now, before any of the code exists. A gate failure
blocks the next phase: fix the code, don't move the bar. Changing a threshold
takes a dated amendment, and "it failed" is never a valid reason.

**Gate A: Kuhn (Phase 1)**
- Our exploitability for the uniform random policy matches OpenSpiel's to 1e-9.
  The spike measured 0.4583.
- After 1,000 CFR+ iterations, the average strategy's exploitability is below
  1e-3. In the spike, OpenSpiel's CFR+ reached 2.9e-4 after 200.
- Player 1's game value is within 1e-3 of -1/18.
- Player 1's strategy sits inside the known one-parameter equilibrium family,
  each probability within 0.02:
  - bet J with probability α, where α is between 0 and 1/3;
  - bet K with probability 3α;
  - with Q, call a bet with probability α + 1/3.

**Gate B: Leduc (Phase 2)**
- Our exploitability matches OpenSpiel's `exploitability` to 1e-9 on three
  policies: uniform, a seeded random policy, and a CFR+ iterate.
- Our CFR+ average-strategy exploitability at iteration 200 is no more than 1.10
  times that of OpenSpiel's `CFRPlusSolver` at iteration 200. The spike measured
  OpenSpiel's at 0.00496.
- Our 200 iterations run no slower than OpenSpiel's Python CFR+ on this laptop.
  The spike measured 101 s.

**Gate C: equity (Phase 3)**
- eval7 and phevaluator agree on the result (win, lose or tie) for 100,000
  random pairs of 7-card hands.
- Exact enumeration of AsAh vs KdKc gives win 0.81065, tie 0.00382, equity
  0.81255, to 1e-5. Both eval7 and phevaluator produced these figures in the
  spike.
- Exact enumeration on 20 more fixed matchups matches a phevaluator-based
  enumeration exactly, and matches pokerkit's `calculate_equities` within 3 SE.
- Monte Carlo calibration: across 200 seeded runs, the share of estimates within
  ±2 SE of the exact answer falls between 0.90 and 0.99. The expected share is
  0.954. This is the test that eval7's own Monte Carlo fails.
- 169×169 matrix: M[i,j] + M[j,i] = 1 within each cell's error, and every cell
  is exact or has SE ≤ 0.002.

**Gate D: push/fold (Phase 4)**
- At every stack depth, the solved strategy pair's exploitability is at most
  0.001 bb per hand, measured by our own best response on the push/fold game.
- At 1 bb effective, the SB jams all 169 hand classes.
- The solution matches a published reference chart on at least 95% of the 169
  classes at every depth checked. Classes the solver mixes are excluded and
  counted. The source is chosen and recorded in DECISIONS before the solver
  first runs (Open question 4).

**Gate E: bot and engine (Phase 5)**
- Over 20,000 bot-vs-bot push/fold hands at 10 bb, run through pokerkit's state
  machine, the realised SB result lands within 3 SE of the game value the solver
  reports. This proves that the bot, the engine adapter and the payoff model
  agree.
- A scripted human seat completes 20 hands of each game through the play page's
  HTTP API (A2).

**Gate F: analyzer (Phase 6)**
- A hand-built fixture of at least 30 hands has every stat counted by hand, and
  every computed stat matches exactly.
- All-in EV adjustment on the fixture's all-in hands matches hand-computed values
  to 1e-6 bb.
- On the phh-dataset Pluribus hands, at least 99% parse (A3). Failures are
  counted and printed, never dropped silently.

---

## Phases, one per session, in order

| Phase | Work | Ends at |
|---|---|---|
| 0 | Scope, decisions, scaffold, private repo, dependency spike | 2026-11-14 |
| 1 | Game interface, Kuhn, CFR and CFR+, best response | Gate A |
| 2 | Leduc, OpenSpiel oracle adapter | Gate B |
| 3 | Equity engine, 169×169 matrix | Gate C |
| 4 | Push/fold game and charts | Gate D |
| 5 | pokerkit adapter, bot, local browser play | Gate E |
| 6 | Hand-history analyzer | Gate F |
| 7 | README truth pass, decide whether to go public | Done 1 to 5 |

## Known risks, measured in the 2026-11-14 spike

The spike script and its output are in `spikes/2026-11-14-deps.py`.

- **eval7's Monte Carlo equity functions are wrong.** AsAh vs KK, 400,000
  samples each, run four times, returned 0.826, 0.857, 0.832 and 0.808. The
  sampling error is about ±0.001, and the true value is about 0.82. Its
  `evaluate` matches phevaluator exactly. We use only `evaluate` (DECISIONS 5).
- **Exact preflop enumeration in pure Python takes about 5 s per combo pair**
  (1,712,304 boards). A brute-force 169×169 matrix would take days. Phase 3
  picks a path, either seeded Monte Carlo with SE ≤ 0.002 per cell or a
  vectorised exact method, and records the choice in DECISIONS.
- **Leduc CFR in Python is slow.** OpenSpiel's Python CFR+ took 101 s for 200
  iterations.
- **eval7 ships Windows wheels only up to CPython 3.12.** The project is pinned
  to Python 3.11 and 3.12 (DECISIONS 10).
- **pokerkit's own evaluator is slow**, about 1.3 ms per equity sample. It is
  used only as an oracle in tests.

## Open questions

Questions 1 to 3 were settled on 2026-11-14 (amendments A1 to A3). Question 4
was settled on 2026-11-14 by DECISIONS 20 and 22. Question 5 was answered on
2026-11-14 for now. Question 6 is still open.

4. **Push/fold reference chart** for Gate D: which published source? *Settled:*
   HoldemResources.net's no-ante heads-up raw data (DECISIONS 20; research in
   `docs/gate-d-reference.md`). The depths and the scoring rule were fixed in
   DECISIONS 22 before the solver ran; Gate D passed.
5. **Going public.** Make the repo public at the end, and under which license?
   *Answered 2026-11-14:* stay private for now. Ian decides the visibility and
   adds a license himself. The README is written as if public, and no
   third-party data is committed (DECISIONS 20, 25).
   *Updated 2026-11-16:* Ian made the repo public under MIT, with
   `bridges/postflop/` staying AGPL-3.0-or-later.
6. **ClubWPT Gold.** Does the client let you download your own hand histories,
   and in what format? Is post-session analysis of them allowed? Their
   prohibited-tools page does not address it. Only support can answer the
   second question. Settle before any ClubWPT parser work.

---

## Amendments log

| # | Date | Change | Reason |
|---|---|---|---|
| A1 | 2026-11-14 | Time box set to about 40 hours as a soft target, with no hard stop. | Ian ticked both "~40 hours" and "No time box". Read as a budget to plan against, not a stop. |
| A2 | 2026-11-14 | Bot surface is a local browser page instead of the terminal. Done 3 and Gate E reworded to match. The browser-UI line moves from out of scope to in scope, limited to localhost. | Ian chose a browser page. The web framework gets its own DECISIONS entry in Phase 5. |
| A3 | 2026-11-14 | Analyzer data is the phh-dataset (Pluribus hands for Done 4 and Gate F), plus ClubWPT Gold under DECISIONS 13. Scraping, screen-reading and OCR of any client are out of scope. | Ian plays on ClubWPT Gold. pokerkit has no parser for it, no export format is documented, and the site bans tools that "scrape hand history data". |
| A4 | 2026-11-14 | Phases 1 to 3 run in a single session instead of one per session. | Ian asked for the early core phases to be built while he was away, with no questions. Calls that would have been his are recorded in DECISIONS 14 onward. The per-phase gates still apply. |
| A5 | 2026-11-14 | Phases 4 to 7 run as one autonomous stretch instead of one per session. Commits and pushes happen at each gate PASS. A gate failure gets one reproduce-and-fix; a second failure stops the run. No public actions, no new dependencies, and only one approved download (the phh-dataset Pluribus hands). | Ian asked for a long plan that could run without questions, and answered every open call up front (`docs/plan-phases-4-7.md`; design facts in `docs/design-review-phases-5-6.md`). Gates still apply. |
| A6 | 2026-11-15 | A narrow exception to DECISIONS 9 (DECISIONS 29). A suggest-only live advisor is in scope for private play-money games (Poker Now first) where every player knows. It never runs for real money, never on ClubWPT (DECISIONS 13), never clicks, and is never hidden from screen sharing. Postflop solving and serving beyond localhost stay out of scope until their own amendments. | Ian's live-advisor scope (2026-11-15); plan in `docs/plan-live-advisor.md`. |
| A7 | 2026-11-15 | A small heads-up preflop model above 20 bb comes into scope (DECISIONS 33): our own CFR solves fold / raise 2.5 / jam, 3-bet 3x / jam and calls, with postflop valued as equity x a realization factor R, not played. Its charts are labelled "model chart". Limps, min-raises and other sizes stay out. | Ian's D3, from spike S3 (`docs/preflop-source.md`): no licensed heads-up chart exists for 25 to 100 bb, and V1's equity helper needs preflop ranges above 20 bb. |
| A8 | 2026-11-15 | An exploitative answer, shown beside the Nash or model one, comes into scope for the jam-vs-range helper (DECISIONS 36): call or fold against an all-in, as the best response to a villain range Ian supplies, or to a labelled default where nothing else answers. It is Phase 12's first slice; the opponent model and the other parked items stay out until their own amendments. | Ian made exploiting opponents' deviations a headline feature on 2026-11-15, and chose this helper's design. |
| A9 | 2026-11-15 | D2: postflop solving comes into scope, ahead of time only (DECISIONS 40): exploit solves between sessions (`showdown postflop exploit`, one locked villain read) and an overnight flop library looked up live. The engine is b-inary's postflop-solver (AGPL-3.0), built locally from a pinned commit and run as a separate process through our AGPL bridge in `bridges/postflop/`. Its binary and source are never committed or distributed. Solving during live play stays out. | Gate S4: 0.5 to 2 minutes per flop, too slow for live play, and its node locking works. Ian chose exploit solves and a library, run overnight on AC. |
| A10 | 2026-11-19 | The preflop model (A7) gains a second 3-bet size, 4x the open, and its R is fitted per pot and depth from our own flop solves (DECISIONS 49), in place of one assumed 0.90. Limps, min-raises, other open sizes and 4-bets below all-in stay out. | The 2026-11-16 audit: with one R that discounts only called pots, the BB jams 21% over the open and never 3-bets at 50 bb. Ian chose the size and the fit. |
| A11 | 2026-11-19 | Phase 12's opponent model comes into scope (DECISIONS 50): per-friend reads from Ian's own logged hands, as ratios to the model, shrunk toward it or toward a playstyle label (Nit, TAG, LAG, Station) that Ian sets with overlay buttons. Reads apply as preflop and push/fold cutoffs, tilted stopgap curves, and villain locks in the live turn and river solves (lock support added to `streets.rs`). The overlay shows the exploit above the base answer, with its gain and risk. Names, labels and reads stay local and are never committed. Automatic player typing stays out. | Ian made exploiting opponents a headline feature (2026-11-15), picked the labels and their effects (DECISIONS 47), and chose this design. |
| A12 | 2026-11-22 | A six-max preflop spot engine comes into scope (DECISIONS 53, Gate M), as a study CLI, `showdown sixmax`. Spots: unopened pots and pots with 1 to 3 limpers, from each six-max seat, at 100 bb, blinds 0.5/1, with no ante or 0.5 bb from every player. Actions: fold, limp or overlimp, and a raise at three sizes. Opponents follow one of three profiles (tight, regular, loose-passive) fitted to the PHH 6-max hands. It is an EV calculator against assumed ranges, not a solver: postflop is valued as equity × R, and facing a re-raise the hero stacks off or folds. Three or more players in any solver, the live advisor, other stacks, 3-bet pots, ICM, six-max hand review and a drill trainer stay out until their own amendments. | Ian's games are six-max with limpers and sometimes an ante of the small blind from every player; the heads-up tools answer none of those spots. Ian chose this slice and its design on 2026-11-22. |
| A13 | 2026-11-22 | A12's six-max work is a study and training tool only, under DECISIONS 29: never live advice during a hand, never screen reading, nothing for ClubWPT, and nothing for any real-money table. It runs between sessions, on spots typed in or on completed hands. The roadmap is `docs/plan-sixmax-trainer.md`. | Ian's instruction of 2026-11-21, relayed by the master session after A12 was pushed. A12 ruled out the live advisor but did not state the study-only rule. |
| A14 | 2026-11-22 | A fourth six-max profile, "standard", comes into scope (DECISIONS 54, Gate M2). Its blinds and players behind defend like a modern 100 bb solver chart, by the raiser's seat, from assumed numbers labelled as such. Its limp ranges and limp responses are the fitted regular profile's. A profile may now carry per-seat rates. Study-only, as A13. | Gate M bar 3 failed because the 2009 blinds fold about 73% to a small open. Ian chose (2026-11-22, relayed by the master session) to add this profile before the drill trainer, so drills do not teach over-stealing. |
| A15 | 2026-11-22 | A six-max drill trainer comes into scope (DECISIONS 55, Gate K): `showdown sixmax drill` deals practice spots and hands, asks for the kind of action (fold, limp, raise), grades it good, marginal or review from `showdown sixmax`'s answer, and logs each drill locally (gitignored). Study-only, as A13. | Step 2 of `docs/plan-sixmax-trainer.md`. Ian approved the design through the master session and chose to build drills on 2026-11-22. |
| A16 | 2026-11-22 | The "standard" six-max profile's limpers (limp range, fold to an iso, limp-reraise, size slope) come from the fitted loose-passive profile, not regular, and R for an out-of-position raiser is 0.75 (DECISIONS 56, 57; Gate M4). The responses to a limp and the seat defence stay as A14 has them. | Ian, 2026-11-22, through the master session: 2009 regulars limp 2.9% of hands, unlike the limpers at his tables, and under "standard" the SB opened every hand at R 0.90. |
| A17 | 2026-11-22 | Six-max hand review comes into scope (DECISIONS 58, Gate W). `showdown sixmax review` reads completed hands (PHH, PokerStars text). It grades a named player's first preflop decision in unopened and limped six-handed pots by kind of action, with the engine, and reports leaks. The analyzer keeps each hand's antes and preflop action order. Study only, as A13. Hand histories are never committed. The Poker Now parser stays in Phase 11. | Step 3 of `docs/plan-sixmax-trainer.md`. Ian approved the design through the master session on 2026-11-22. |
| A18 | 2026-11-26 | The product becomes an exploit trainer and a leak finder (DECISIONS 59). A13 is amended: post-session review of hand files from sites whose terms let you download them (PokerStars-format exports first) is in scope. Never live, never during a hand, never a folder watched during a session; ClubWPT stays under DECISIONS 13. The live Poker Now path is parked: Phase 10's loop (`live/screen.py`) stays in the code, and spike S1, Gate H, the live goal and Phase 11 leave the roadmap. Hand histories are never committed. The roadmap is `docs/plan-sixmax-trainer.md`. | Ian, 2026-11-26: live play is out unless it can run on legit sites. He chose the trainer and leak finder, and approved this amendment in plan mode. |
| A19 | 2026-11-26 | Automatic play is a later item, only on venues that allow bots (bot-vs-bot APIs, a self-hosted play-money table). Until its own entry, nothing in showdown plays by itself anywhere. | Real-money sites ban bots in their terms. Ian's plan of 2026-11-26. |
| A20 | 2026-11-27 | The trainer's grade scale and player types come into scope (DECISIONS 60, Gate Y). Six-max answers are graded Best, Correct, Inaccuracy, Wrong or Blunder by EV lost as a % of the pot, with the band floor. Opponents are named types (Nit, TAG, LAG, Maniac, Weak-tight rec, Calling station, standard), fitted to the PHH hands: one type for the limpers, one for the table. Heads-up push/fold gets the same types as range widths, labelled tournament-style with no ICM. Study only, as A13 and A18. | Step 1 of `docs/plan-sixmax-trainer.md`. Ian's answers and up-front decisions of 2026-11-26. |
| A21 | 2026-11-27 | Six-max pots facing one open raise come into scope (DECISIONS 61, Gate Z): the hero folds, calls, 3-bets to 3× or 4× the open, or jams, against an opener of a named type and a table type behind. The opener 4-bets, calls or folds; a 4-bet means stack off or fold. Postflop is still R × equity × pot. Pots where the hero opened and faces a 3-bet stay out. Study only, as A13 and A18. | Step 2 of `docs/plan-sixmax-trainer.md`. Ian's up-front decisions 5 to 8 of 2026-11-26. |
