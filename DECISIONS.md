# Decisions

One entry per settled decision, numbered and chronological. Each entry states
what was decided, why, and **what it rules out**. The last field is the point:
it stops a future session from reopening the question. Never edit an entry in
place. A reversal is a **new** entry that supersedes an older one by number.

---

### 1. A heads-up poker lab, joined by the push/fold game (2026-11-14)

**Decided:** Four components: CFR solver, equity engine, playable bot and
hand-history analyzer. Each feeds the heads-up push/fold game or is graded
against it (SCOPE, "The spine").

**Why:** Ian asked for all four. Built separately, they make four shallow demos.
Joined, the equity engine sets the solver's payoffs, the solver drives the bot,
and the analyzer grades real hands against the same solution. Kuhn and Leduc come
first because their right answers are known, so the solver is proven before it
gets near hold'em.

**Rules out:** Each component growing its own game. If a feature does not touch
Kuhn, Leduc or push/fold, it needs a scope amendment.

---

### 2. Its own git repo, `main`, private on GitHub (2026-11-14)

**Decided:** `git init` in `~/projects/showdown` on branch `main`. The remote is
the private repo `ian-menachery/showdown`. Commits go straight to `main`. The
git identity is set locally in the repo, as in rentroll, because there is no
global identity on this machine.

**Why:** `~` is an accidental git repo whose `.gitignore` is `*`, so nothing
under it is tracked by design. Private until Ian decides otherwise (SCOPE, Open
question 5).

**Rules out:** Tracking this work in the home repo, and making the repo public
before the Phase 7 decision.

---

### 3. Borrow commodity parts through pip, build the rest (2026-11-14)

**Decided:** The NLHE rules engine, the 7-card evaluator and site hand-history
parsing come from open-source libraries, installed through pip at pinned versions
in `pyproject.toml`. CFR, best response, equity aggregation, the push/fold game,
analyzer stats and the bot are written here.

**Why:** Ian's call: take starter code for the simpler parts. Evaluators and
rules engines are solved problems with tested libraries behind them. The solver
and the analysis are what the project is meant to show.

**Rules out:**
- Writing our own evaluator or NLHE state machine.
- Copying library source files into the repo. If copying ever becomes
  unavoidable, the file keeps its license header, a `NOTICE` file records it,
  and it gets its own DECISIONS entry first.

---

### 4. pokerkit for the game engine and hand-history parsing (2026-11-14)

**Decided:** pokerkit 0.7.7 (MIT, pure Python, Python 3.11 or later, released
2026-10-12). It provides the NLHE state machine, the PHH hand-history format,
and parsers for PokerStars, Full Tilt, iPoker, Ongame, PartyPoker and Absolute
(`pokerkit.notation`).

**Why:** It is the most complete maintained Python rules engine. Its parsers
already cover the hand-history input, and the authors publish a
[phh-dataset](https://github.com/uoftcprg/phh-dataset) (MIT) that includes the
Pluribus hands. That gives the analyzer real data even if Ian has no history
files of his own.

**Rules out:** GGPoker and any other format pokerkit does not parse, in v1.
pokerkit's evaluator and `calculate_equities` are too slow for anything except
test oracles (about 1.3 ms per sample in the spike).

---

### 5. eval7 for evaluation, and only its `evaluate` function (2026-11-14)

**Decided:** eval7 0.1.11 (MIT, compiled, with a cp312 win_amd64 wheel) supplies
`eval7.evaluate`. Nothing else in eval7 is used. All equity calculation, exact
and Monte Carlo, is written here on top of `evaluate`.

**Why:** The spike tested it against an independent evaluator.

- Exhaustive enumeration of AsAh vs KdKc over all 1,712,304 boards gives win
  0.81065 and tie 0.00382. eval7 and phevaluator produce identical results.
- eval7's own `py_hand_vs_range_monte_carlo` for AsAh vs KK, with 400,000
  samples, returned 0.826, 0.857, 0.832 and 0.808 on four runs. The sampling
  error is about ±0.001. An earlier 200,000-sample run returned 0.785. The
  function is broken, not just noisy.

treys is pure Python and its last release was in 2022. phevaluator is just as
fast but only evaluates; it has no range types.

**Rules out:** `eval7.py_hand_vs_range_monte_carlo`, `py_hand_vs_range_exact`,
`py_all_hands_vs_range`, and any other eval7 equity helper. Gate C's Monte Carlo
calibration test exists to catch this kind of failure in our own code.

---

### 6. Kuhn and Leduc built here; OpenSpiel and phevaluator as dev-only oracles (2026-11-14)

**Decided:** Kuhn, Leduc and push/fold are implemented behind one small game
interface in `showdown`. OpenSpiel 2.0.2 (Apache-2.0, with a cp312 win_amd64
wheel that the spike confirmed loads and solves Leduc) and phevaluator 0.6.0
(Apache-2.0) are `dev` extras, used only in tests as reference answers.

**Why:** The rules are small, and owning the game tree is what makes the solver
our own work. OpenSpiel's `exploitability` and `CFRPlusSolver` give an
independent check on Gates A and B. phevaluator gives one on Gate C.

**Rules out:**
- A runtime dependency on OpenSpiel.
- Running our CFR on OpenSpiel's game objects in place of our own games. An
  adapter for comparison is fine.
- A test that skips when an oracle is missing. Skips do not count toward a gate
  pass, and the gate installs the dev extras.

---

### 7. Exploitability follows OpenSpiel's convention (2026-11-14)

**Decided:** exploitability = NashConv / 2, the average over the two players of
what a best response gains. Kuhn and Leduc are measured in chips per hand
(ante 1). Push/fold is measured in big blinds per hand.

**Why:** Gate A and Gate B compare against OpenSpiel to 1e-9, so the definition
has to be identical, not merely equivalent.

**Rules out:** mbb/g, NashConv without halving, or mixing units across games in
one report.

---

### 8. The push/fold game, defined (2026-11-14)

**Decided:**
- Heads-up NLHE, blinds 0.5/1, no ante, effective stack S bb.
- The SB jams or folds. Facing a jam, the BB calls or folds.
- Hands are bucketed into the 169 strategic classes.
- Payoffs come from the 169×169 all-in equity matrix. Each cell averages over
  the class pair's non-conflicting combos, weighted by how many there are, so
  card removal is counted.
- Stack depths run from 1 to 20 bb in steps of 1.

**Why:** It is the smallest real hold'em game with a known, published Nash
solution. That makes Gate D checkable against outside answers rather than
against our own beliefs.

**Rules out:** SB limp or min-raise, BB raise sizes, antes, ICM and stacks above
20 bb, in v1.

---

### 9. No live-play assistance, ever (2026-11-14)

**Decided:** The analyzer reads completed hand-history files after the fact. The
bot plays only inside this program.

**Why:** Real-time assistance is banned by the terms of every major poker site,
and this is a study tool.

**Rules out:** HUDs, overlays, screen or table reading, a watcher that updates
stats while a session is running, and any connection to a poker site.

---

### 10. Python 3.11 to 3.12, in a repo-local `.venv`; `gate.py` uses it (2026-11-14)

**Decided:** `requires-python = ">=3.11,<3.13"`. Dependencies are installed into
`.venv` with `pip install -e ".[dev]"`. When `.venv` exists, `gate.py` runs its
tools with that interpreter, so `py gate.py` works from a plain shell.

**Why:**
- pokerkit needs Python 3.11 or later.
- eval7 0.1.11 has no wheel above cp312. It is Cython, so any newer Python would
  need a source build.
- `make` is not installed here, which is the same constraint as rentroll.

**Rules out:** Python 3.13 or later until eval7 ships a wheel for it, and global
pip installs.

---

### 11. Gates are pre-registered correctness checks (2026-11-14)

**Decided:** Gates A to F in SCOPE carry numeric thresholds set before any code
exists. A FAIL blocks the next phase. A threshold changes only through a dated
SCOPE amendment, and "it failed" is never the reason.

**Why:** It is the same discipline as bellwether and rentroll. Unlike those, a
FAIL here does not end the project: these gates test correctness, not a thesis.

**Rules out:** Loosening a tolerance to get a gate green, and starting phase N+1
while gate N fails.

---

### 12. Play happens in a browser page served on localhost (2026-11-14)

**Decided:** `showdown play` starts a local server bound to `127.0.0.1` and opens
a page with both games: the push/fold trainer and Leduc against the CFR bot. The
game logic stays in Python (pokerkit and our solver). The page is only a view
over a small HTTP API, and Gate E drives that API directly. The web framework is
chosen in Phase 5 and recorded as its own entry. The lightest option that works
is the default.

**Why:** Ian chose a browser page over the terminal (SCOPE A2). Keeping the
logic in Python means the bot the page shows is the same code the gates test.

**Rules out:**
- Binding to `0.0.0.0` and any hosted or public deployment.
- Porting game logic or strategies to JavaScript.
- Accounts, persistence beyond a session, multiplayer.

---

### 13. ClubWPT Gold: own exports only, offline only, never while the client is open (2026-11-14)

**Decided:** ClubWPT Gold hands enter the analyzer in one of two ways only:
- a file that the ClubWPT Gold client itself lets Ian download; or
- Ian transcribing chosen hands by hand into PHH.

A parser for an exported format is a scope amendment, written against one real
sample file. Until Ian has a sample, there is no ClubWPT code. The README tells
the user not to run showdown (equity, charts, trainer or analyzer) while a
ClubWPT Gold client is open.

**Why:** ClubWPT Gold's prohibited-tools page
(support.clubwptgold.com, "Prohibited Tools", read 2026-11-14) bans three
relevant things:
- "equity calculators, range simulators, or analytical software while the game
  client is open";
- reference material, including "charts or plots, range matrices";
- "Tools designed to scrape hand history data".

The page says nothing about offline review of your own hands after a session,
and it documents no export format. A PokerTracker forum post says the site does
not save local hand histories. Only ClubWPT support can say whether post-session
analysis is allowed (SCOPE, Open question 6).

**Rules out:**
- Scraping, screen capture, OCR or memory reading of the ClubWPT client.
- Pulling hand data from the site through anything except its own download.
- Any feature meant to be used during a ClubWPT session.

This tightens DECISIONS 9; it does not replace it.

---

### 14. Solvers run on a compiled, preorder-numbered tree (2026-11-14)

**Decided:** `compile_game` walks a game once and stores the result in flat
lists: player, children, chance probabilities, infoset id and terminal utility
per node. Nodes are numbered in preorder, so a forward loop sees parents first
and a reverse loop sees children first. A policy is a list of per-infoset
probability lists in `Tree.infoset_actions` order. Compiling also checks that:

- every terminal is zero-sum;
- chance probabilities sum to 1;
- every node sharing an infoset key has the same player and the same actions.

**Why:** OpenSpiel's Python CFR+ spends about 0.5 s per Leduc iteration walking
`pyspiel` state objects. On flat lists, a CFR pass is two loops with no
recursion and no object creation. Payoffs are stored only for player 0, which
is sound because the zero-sum check guarantees player 1's is the negation.

**Rules out:**
- Three or more players, and general-sum games. `compile_game` raises instead.
- Solvers that call `State` methods during iteration.

---

### 15. Our CFR has OpenSpiel's exact semantics, and is tested for equality (2026-11-14)

**Decided:** `CFRSolver` takes OpenSpiel's three flags (alternating updates,
linear averaging, regret matching+) and copies its update order:

- regrets are weighted by counterfactual reach, including chance;
- average-policy sums are weighted by own reach (times t when linear);
- after each pass, regrets are clipped (for RM+) and every infoset's current
  policy is recomputed;
- a node where both players' reach is 0 is skipped.

`cfr()` and `cfr_plus()` are OpenSpiel's `CFRSolver` and `CFRPlusSolver`.

**Why:** Gate B only requires our exploitability to be within 1.10× of
OpenSpiel's. With identical semantics, a much stronger test is possible: the
average and current policies match OpenSpiel's at fixed iterations to 1e-10.
That holds on Kuhn for all four flag combinations tested.

**Rules out:** Quietly swapping in a different CFR variant, such as discounted
CFR, delayed averaging or sampling, under the `cfr_plus` name. Other variants
get their own names and are compared against their own references.

---

### 16. Slow tests are gate evidence; GATES.md records every gate run (2026-11-14)

**Decided:** Tests that take more than about 10 s carry `@pytest.mark.slow`.
pyproject deselects them by default, and `py gate.py --full` runs them too.
Every gate run is written up in `GATES.md` with:

- the date;
- each measured number next to its pre-registered bar;
- PASS or FAIL;
- the command that reproduces it.

**Why:** Some gate checks are slow by nature. OpenSpiel's 200-iteration Leduc
reference alone takes 101 s, and exact preflop enumeration takes about 5 s per
matchup. Keeping them out of the default run keeps `py gate.py` quick enough to
run after every change. The slow checks still run before any gate is declared.

**Rules out:**
- Declaring a gate PASS from the fast suite when that gate has slow checks.
- Gate results that live only in a terminal scrollback.

---

### 17. Bit-identical to OpenSpiel: preorder updates and plain summation (2026-11-14)

**Decided:** This makes DECISIONS 15 more precise. "Same update order" is now
enforced down to float rounding, in two ways:

1. Regret and policy-sum updates run in a separate forward (preorder) loop,
   after the backward loop has computed values. Nodes in one infoset are then
   summed in the same order as OpenSpiel's recursion reaches them. They are
   never ancestor and descendant, so preorder equals recursion order.
2. Regret matching and the average-policy normalisation add floats left to
   right (`_plain_sum`), not with the built-in `sum`.

**Why:** The first Gate B run passed both bars but ended at exploitability
0.0050008, against OpenSpiel's 0.0049631. Investigation found two separate
1-ulp sources, and CFR+ amplifies a 1-ulp difference about 1.24× per iteration
(1e-16 at iteration 1, 1e-10 at 62, 0.03 by 200):

- the backward loop summed an infoset's nodes in reverse order, which put 226
  infosets 1 ulp apart after the first pass;
- Python 3.12's `sum` uses compensated (Neumaier) summation for exact floats,
  but OpenSpiel's regrets are `np.float64`, which `sum` adds plainly. Three-term
  sums such as 0.0667 + 0.0333 + 0.0194 then round differently. That is why Kuhn
  (2-action infosets) matched and Leduc (3-action infosets) did not.

With both fixed, all 200 iterations are equal entry for entry, and the
exploitability is the same double.

**Rules out:**
- Built-in `sum` over floats in the solver's update path.
- Folding the updates back into the backward loop for speed.
- Tolerance-based trajectory tests. Equality is the test now.
