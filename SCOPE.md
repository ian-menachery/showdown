# SCOPE: showdown

Committed before any implementation. Change it only with a dated row in the
Amendments log at the bottom, never by a silent edit.

**Repo:** `ian-menachery/showdown` (private)
**Package:** `showdown`
**Started:** 2026-11-14
**Time box:** OPEN, see Open questions.

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
- Terminal play:
  - a push/fold trainer against the solved bot, in either seat, showing bb lost
    on each decision;
  - Leduc against the CFR bot.
- Hand-history analyzer. It parses PokerStars-format text (through pokerkit) and
  PHH files. It reports VPIP, PFR, 3-bet, WTSD, W$SD and bb/100, plus all-in
  EV-adjusted bb/100. It grades heads-up hands at 20 bb effective or less
  against push/fold Nash.
- One CLI, `showdown`, with subcommands `solve`, `equity`, `play` and `analyze`.

## Explicitly out of scope

This list is load-bearing. Anything on it is a scope amendment, not a good idea.

- **Anything that touches live play.** No HUD, overlay, table scraping, folder
  watcher during a session, or real-time advice. The analyzer reads completed
  hand histories only (DECISIONS 9).
- Connecting to any real-money site, and bots that play on any site.
- Full NLHE solving, postflop solving, any abstraction beyond push/fold, limp or
  min-raise options, antes, ICM.
- Three or more players in any solver.
- Neural networks, Deep CFR, reinforcement learning.
- Writing our own hand evaluator or NLHE rules engine.
- Site formats that pokerkit does not parse, GGPoker included.
- A browser UI in v1 (Open question 3).
- Performance rewrites (Cython, Numba, Rust) unless a gate fails on runtime.
  Even then, a DECISIONS entry comes first.
- Database, accounts, hosting.

## Done, defined as checks that pass or fail

1. `py gate.py` exits zero. That means ruff check passes, ruff format --check
   passes, pytest passes with coverage of at least 80% on `showdown`, the tree is
   clean, and HEAD is pushed.
2. Gates A to F below all PASS.
3. `showdown play pushfold` and `showdown play leduc` each run a full session in
   a fresh terminal.
4. `showdown analyze <file>` prints the stats table for a real hand-history file
   (Open question 2 decides which file).
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
- A scripted human seat completes 20 hands of each game through the CLI.

**Gate F: analyzer (Phase 6)**
- A hand-built fixture of at least 30 hands has every stat counted by hand, and
  every computed stat matches exactly.
- All-in EV adjustment on the fixture's all-in hands matches hand-computed values
  to 1e-6 bb.
- On the full real dataset (Open question 2), at least 99% of hands parse.
  Failures are counted and printed, never dropped silently.

---

## Phases, one per session, in order

| Phase | Work | Ends at |
|---|---|---|
| 0 | Scope, decisions, scaffold, private repo, dependency spike | 2026-11-14 |
| 1 | Game interface, Kuhn, CFR and CFR+, best response | Gate A |
| 2 | Leduc, OpenSpiel oracle adapter | Gate B |
| 3 | Equity engine, 169×169 matrix | Gate C |
| 4 | Push/fold game and charts | Gate D |
| 5 | pokerkit adapter, bot, terminal play | Gate E |
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

## Open questions, for Ian to settle before Phase 1

1. **Time box.** Hours, and a calendar limit.
2. **Hand histories.** Use your own (from which site?), or the public MIT
   [phh-dataset](https://github.com/uoftcprg/phh-dataset), which includes the
   10,000-hand Pluribus set and HandHQ online hands? pokerkit parses PokerStars,
   Full Tilt, iPoker, Ongame, PartyPoker and Absolute. It does not parse
   GGPoker.
3. **Bot surface.** Terminal only for v1, as currently planned, or a browser
   page?
4. **Push/fold reference chart** for Gate D: which published source?
5. **Going public.** Make the repo public at the end, and under which license?

---

## Amendments log

| Date | Change | Reason |
|---|---|---|
| | | |
