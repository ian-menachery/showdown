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

---

### 18. The 169×169 matrix is board-major Monte Carlo, committed as a data file (2026-11-14)

**Decided:** `showdown matrix build` samples random 5-card boards. On each board
it ranks every live combo once with eval7, compares all non-conflicting combo
pairs in numpy, and sums the results into class blocks. The run uses 64 batches,
each seeded with `SeedSequence(seed, spawn_key=(batch,))`, spread across worker
processes. The standard error comes from batch means. The result goes to
`data/preflop_169.npz`, which is committed:

- 147,200 boards (64 batches of 2,300);
- seed 20261114;
- the equity matrix, the SE matrix, and the exact card-removal pair counts.

**Why:**
- **Exact is not affordable.** An exact matrix needs 812,175 combo pairs at
  about 2 s each, which is days. A vectorised exact method would need our own
  lookup-table evaluator, which DECISIONS 3 rules out.
- **One board scores many pairs.** Board-major sampling scores about 580,000
  combo pairs per board for 1,081 evaluator calls. With 16 cores, a full build
  takes minutes.
- **The estimate is unbiased.** A uniform board that avoids a pair's cards is
  uniform over that pair's remaining 48 cards, and every pair is equally likely
  to be live. So the summed ratio estimates the equal-weight class average.
- **The data file is committed.** Phase 4 depends on it, and rebuilding is
  slow. It is reproducible from the seed by `showdown matrix build`.

**A gate bullet that is weaker than it looks:** under this method,
M[i,j] + M[j,i] = 1 holds exactly by construction. Every comparison scores both
orders at once. So Gate C's symmetry bullet can only catch aggregation bugs
such as a transposed class index. The independent check is in the slow suite:
three cells (AA vs KK, AKs vs QQ, T9s vs AKo) must sit within 3 SE of exact
class-vs-class enumeration. That enumeration shares work across suit-isomorphic
combo pairs, so AA vs KK takes 3 enumerations rather than 36.

**Rules out:**
- Rebuilding the matrix silently with a different seed or board count. A new
  matrix is a new commit, with its numbers in GATES.md.
- Any cell with SE above 0.002 (Gate C).
- Using eval7's equity helpers for any part of this (DECISIONS 5).

---

### 19. Range equity gives equal weight to every non-conflicting combo pair (2026-11-14)

**Decided:** Range-vs-range equity, exact and Monte Carlo alike, averages
per-pair equity over every (hero combo, villain combo) pair that shares no card
with the other or with the board. Ranges carry no weights in v1. In Monte Carlo,
each sample draws a pair uniformly and then a runout. Exact enumeration averages
each pair's exact equity. The push/fold game weights class pairs by the exact
pair counts stored with the matrix.

**Why:** It is the standard definition, and it is what pokerkit's sampling
implies for single combos. It also makes exact and Monte Carlo estimate the same
quantity, so Gate C's calibration test means something.

**Rules out:** Weighted ranges ("AKs:0.5") in v1. They are an amendment if Phase
4 or the analyzer needs them.

---

### 20. Gate D's reference is HoldemResources' no-ante raw data; third-party files stay out of git (2026-11-14)

**Decided:** Ian picked this on 2026-11-14, from the options in
`docs/gate-d-reference.md`, which settles SCOPE Open question 4.
- **The reference.** Gate D compares against HoldemResources.net's heads-up
  push/fold equilibrium, no ante, in its unsimplified raw form.
  - `holdemresources_hu_push.csv` and `holdemresources_hu_call.csv` come from
    `holdemresources_hu_equilibrium.zip`.
  - Each gives a play probability for all 169 classes at every stack from 1 to
    200 bb, in steps of 0.05 bb. Probabilities are rounded to 0.01.
  - Stacks are effective stacks in bb before the blinds are posted, which is our
    definition.
  - The public chart on the same page is the fallback, used only if the raw data
    proves unusable.
- **Downloads approved.** Ian also approved downloading b-inary/poker-cfr's
  exact equity table (`heads_up_pre_flop_equity.bin`, BSD-2-Clause, commit
  a534708). It serves as an exact reference for the 169×169 matrix.
- **Storage.** Both files live in the gitignored `data/external/` and are pinned
  by SHA-256:

| File | SHA-256 |
|---|---|
| `hrc/holdemresources_hu_equilibrium.zip` | `650da7525b35e12adbc03df26d6690c30b583ff4b7d930156c104012a040ec9d` |
| `hrc/raw/holdemresources_hu_push.csv` | `ed588eda85842704adeb233e7f2a22331aa6b83543b23fce838788ba55e32cc2` |
| `hrc/raw/holdemresources_hu_call.csv` | `fa99898839ca9da23bb6193bdfcb873632fecc95b34079b79ff27670426682d3` |
| `b-inary/heads_up_pre_flop_equity.bin` | `006404b36d257fc9455da0d0f0ab89aef3e80ece56c8f3e770bad926cfe5ec8a` |

**Why:**
- **Same game.** HoldemResources solves the same game we do: heads-up, no ante,
  chip EV, stacks measured before the blinds.
- **The raw data is an equilibrium, not a simplified chart.** So the comparison
  can be pure strategy against pure strategy, with mixed classes excluded on
  either side. That is what Gate D's wording describes.
- **It is the solution behind the chart.** The spike
  (`spikes/2026-11-14-reference-data.py`) confirmed this: 10 of 10 chart
  thresholds, including all three gapped hands, agree within 0.05 bb.
- **Mixing is rare.** At 2 to 20 bb the raw data mixes at most 3 classes per
  depth.
- **Why the files stay out of git.** Neither HoldemResources' page nor its
  Legal page grants a licence to redistribute the data. Keeping both files out
  of git also keeps Open question 5 (going public) clean.

**Not yet decided:** the depths checked and the exact scoring rule. The note
proposes them. Ian did not tick that box, so they are fixed in a later DECISIONS
entry before the push/fold solver first runs.

**Rules out:**
- Committing either file, or a transcription of the chart.
- Comparing against *Mathematics of Poker*'s tables.
- Comparing against Miltersen and Sørensen. They solve a multi-hand tournament,
  which is a different game.
- A Gate D test that skips when the reference file is missing. It must fail and
  say how to fetch the file.

---

### 21. Phase 4 solves on an exact 169×169 matrix, built from every board (2026-11-14)

**Decided:** Ian approved this on 2026-11-14. It amends DECISIONS 18.
- **What it is.** `showdown matrix build --exact` writes
  `data/preflop_169_exact.npz`, which is committed. It runs the same per-board
  step as the Monte Carlo build: rank the live combos, compare every pair, then
  sum into class blocks. But it runs that step on every 5-card board instead of
  a sample.
- **One board per class.** It scores one board from each class of boards that
  are the same up to relabelling suits. There are 134,459 such classes. Each
  board's integer sums of 2 × wins + ties are weighted by the number of boards
  its class contains (4, 12 or 24, for 2,598,960 in all).
- **Timing.** The build took 1,063 s on 16 cores.
- **What Phase 4 uses.** The push/fold game uses this exact matrix as its
  payoffs.
- **The Monte Carlo matrix stays.** `data/preflop_169.npz` is still committed,
  as Gate C's evidence.

**Why:**
- **It is exact for the same cost.** Relabelling suits maps every class to
  itself and keeps every hand's strength. So a board's class sums equal those of
  every relabelling of it, and 134,459 boards give the exact answer for about
  what the Monte Carlo build cost (147,200 boards). DECISIONS 18 assumed an
  exact matrix was out of reach, because it priced brute force at 5 s per combo
  pair. Enumerating board by board, over one board per suit class, removes that
  cost.
- **It removes a source of Gate D disagreement.** Against exact equity, the
  Monte Carlo matrix's largest cell error is 0.0046 (GATES.md, Gate C), which is
  about 0.09 bb per class pair at 10 bb. A class near indifference could land on
  the wrong side of HoldemResources' answer because of matrix noise alone. With
  exact payoffs, any Gate D disagreement is the solver's or the reference's.
- **It has an independent check.** Every cell equals the value built from
  b-inary/poker-cfr's exact combo-pair table, to the integer:
  `tests/test_matrix_exact_slow.py`, which needs `data/external/`
  (DECISIONS 20). Two separate programs, enumerating in different orders (combo
  pair first, against board first), give the same 28,561 integers.

**Rules out:**
- Using the Monte Carlo matrix as push/fold payoffs.
- Rebuilding the exact matrix with anything other than integer sums.
- Loading b-inary's table at runtime. It is a test oracle only, like OpenSpiel
  and phevaluator (DECISIONS 6).

---

### 22. Gate D's comparison rule and the pre-registered solve (2026-11-14)

**Decided:** Ian approved this rule on 2026-11-14. It is recorded before the
push/fold solver's first real run, and it completes DECISIONS 20.

- **Depths and seats.** Every integer depth from 1 to 20 bb (the grid in
  DECISIONS 8), for the pusher and for the caller: 40 comparisons.
- **Pure and mixed.**
  - A class with a play probability of at least 0.99 counts as playing.
  - At 0.01 or below, it counts as folding.
  - Anything in between is mixed. The same rule applies to our solution and to
    HoldemResources'.
  - A class that either side mixes is excluded from that comparison. The number
    excluded is printed with every result.
  - If more than 10% of classes are excluded at any depth, that is reported as
    a finding, not folded into the score.
- **Pass.** At least 95% agreement among the compared classes, in every one of
  the 40 comparisons.
- **The reference row.** The one whose stack equals d (`np.isclose`) in
  `holdemresources_hu_push.csv` or `holdemresources_hu_call.csv`.
- **Exploitability.** At most 0.001 bb per hand at every one of the 20 depths
  (SCOPE). It is measured by `showdown.cfr.exploitability` on the compiled
  push/fold tree.
- **The solve, fixed in advance.**
  - `cfr_plus`, exactly 1,000 iterations at every depth, average policy.
  - Payoffs come from `data/preflop_169_exact.npz` (DECISIONS 21).
  - No stopping early, no changing the iteration count per depth, and no
    re-running until the answer matches.
- **The stack (this pins DECISIONS 8).**
  - S is the effective stack *before* the blinds are posted. This is the
    definition HoldemResources and b-inary/poker-cfr use.
  - SB folds: the SB loses 0.5.
  - BB folds to a jam: the SB wins 1.
  - Call: the SB nets S·(2E − 1), where E is the class pair's exact equity.

**Disclosure.** Before this entry, a timing benchmark ran `cfr_plus` at 10 bb on
an in-memory copy of the game, to size the work. It printed speed,
exploitability and value only. Nothing was compared against the reference.
- **Speed:** 142,806 nodes and 338 infosets. Compiling took 0.3 s, and one
  iteration about 0.23 s.
- **Exploitability:** 6.0e-4 bb after 50 iterations, 4.4e-5 after 200, and
  7.3e-6 after 500.
- **SB value:** -0.0454 bb.

**Why:**
- **All 20 depths.** Checking every depth on the solve grid leaves no room to
  pick favourable ones.
- **Excluding mixed classes.** A mixed class has no right pure answer, so
  comparing it would score noise.
- **A fixed iteration count.** Setting it in advance means the solution cannot
  be tuned toward the reference.
- **The generic solver.** It was proven on Kuhn and Leduc against OpenSpiel, and
  the benchmark shows it is fast enough. There is no special push/fold solver
  and no performance work (SCOPE).

**Rules out:**
- Changing any number above after the solver's results are seen, except by a
  dated amendment.
- Comparing at other depths in place of these.
- Scoring a class that is mixed on either side.

---

### 23. `showdown play`: a stdlib server on 127.0.0.1 with a small JSON API (2026-11-14)

**Decided:** Ian chose this on 2026-11-14 (SCOPE A5), and it completes
DECISIONS 12.
- **The server.** `http.server.ThreadingHTTPServer` is bound to `127.0.0.1`
  only, on `--port` (default 0, so the OS picks a free port). Nothing else in
  the code can set the host.
- **Request checks.**
  - Any request whose `Host` header is not `127.0.0.1:<port>` or
    `localhost:<port>` gets 403.
  - Each launch makes a random token, written into the page. Every POST must
    carry it in `X-Showdown-Token`, or it gets 403.
- **Endpoints.** All take and return JSON.
  - `GET /` serves the page, which is packaged in `showdown/bot/static/`. There
    is no CDN and nothing loads from the network.
  - `POST /api/session` takes the game ("pushfold" or "leduc"), the seat ("sb",
    "bb" or "alternate"; for Leduc "first", "second" or "alternate"), the depth
    mode ("fixed" or "random") and the depth (1 to 20).
  - `POST /api/hand` deals the next hand and runs the bot until it is your
    turn.
  - `POST /api/act` applies your action, runs the bot, and finishes the hand
    when it is over.
  - `GET /api/summary?session=<id>`.
- **Sessions.** They live in memory, keyed by a random id, with one lock per
  session. There are no accounts and nothing is saved (DECISIONS 12).
- **Hidden information.** No response contains the bot's cards before the hand
  is over.
- **Random depth.** "random" draws an integer from 2 to 20 bb each hand.
- **Opening the page.** `showdown play` prints the URL and opens it with
  `webbrowser`, unless `--no-browser` is given.

**Why:**
- **No new dependencies.** The standard library is enough for one page and four
  endpoints, and DECISIONS 12 makes the lightest option the default.
- **The checks.** Checking the Host header blocks DNS-rebinding pages. The
  per-launch token stops other local pages from posting actions.

**Rules out:** binding to any other address, CORS headers, cookies, persistence,
and loading anything from the network into the page.

---

### 24. The pokerkit adapter, the bots, and how decisions are graded (2026-11-14)

**Decided:** These facts come from `docs/design-review-phases-5-6.md`, and the
first two were checked again first-hand.
- **Seats.** In pokerkit's heads-up state, player 0 is the **big blind** and
  player 1 is the **small blind** and button, who acts first preflop (pokerkit
  swaps the blinds when there are two players). `engine.pokerkit_adapter` pins
  `BB_SEAT = 0` and `SB_SEAT = 1`.
- **Chips.** They are integers scaled ×2: blinds (1, 2), `min_bet` 2, stacks
  2S. Payoffs are divided by 2 to give bb. A replay checked every case: SB fold
  −0.5, BB fold +1, called jams ±S, a split 0, and at 1 bb no BB decision.
- **Dealing.** Our own `random.Random(seed)` draws 9 cards. Hole and board
  dealing are explicit and never automated, because pokerkit's own shuffle uses
  the global `random`.
- **The push/fold bot** plays the committed `data/pushfold.json` at the hand's
  depth. It jams or calls when `rng.random()` is below its probability for its
  class.
- **The Leduc bot** plays `data/leduc_cfr_plus.json`: `cfr_plus` with 1,000
  iterations, written by `showdown solve leduc --iterations 1000 --out ...`.
  Leduc hands run on our own `games/leduc.py`, because pokerkit has no Leduc
  state machine.
- **Grading** is per decision, at the class level, against the opponent's Nash
  strategy at that depth, using the exact matrix:
  - **SB with class i:** EV(fold) = −0.5. EV(jam) is the pair-weighted average
    over j of (1 − c_j)·1 + c_j·S(2E_ij − 1).
  - **BB with class j, facing a jam:** EV(fold) = −1. EV(call) is the average
    of −S(2E_ij − 1) over i, weighted by w_ij·p_i.
  - **bb lost** = max(EV) − EV(chosen). A decision is a **mistake** when it
    loses more than 0.001 bb.
  - The session summary counts decisions, not hands, because at 1 bb the BB has
    no decision. It shows bb lost (total and per decision), the mistakes, and
    the realised result in bb.
- **Leduc** is played but not graded. SCOPE asks only for a session against
  the CFR bot.

**Why:**
- **Class level.** It is the abstraction the solution is defined on, so a
  grade means the same thing as the chart.
- **Grading against the opponent's Nash strategy.** It measures the gap to
  equilibrium play, which is what a trainer teaches.
- **Gate E's backstops.** Gate E's 3 SE test alone is too weak to catch a seat
  swap or a chip-unit error (the design review, risk 1). So Gate E also checks
  every simulated hand's payoff against the model, and the overall jam and call
  rates against the solution.

**Rules out:** grading by the actual combo's equity (the solution is
class-level), grading Leduc, and letting pokerkit draw any card.

---

### 25. Analyzer input and stat definitions (2026-11-14)

**Decided:** Ian approved the data on 2026-11-14 (SCOPE A5). The definitions
follow `docs/design-review-phases-5-6.md`, which checked them against
pokerkit 0.7.7.

**Data.**
- The Pluribus hands come from `uoftcprg/phh-dataset` (MIT), commit
  `e47fbd5816372360bade4de5d712346fe1bb70f6`, only `data/pluribus`.
- They were sparse-cloned into the gitignored `data/external/phh/repo/`:
  10,000 `.phh` files.
- They are pinned by a manifest hash: the SHA-256 of the lines
  "`<path relative to data/pluribus> <file SHA-256>`", sorted by path. Its
  value is `9903a6146e6939470e9fec1a3e9984306d8980bcea70f1cef36182151f88e58d`.
- They are read as data and never executed.

**Input.**
- PHH files go through `HandHistory.load`.
- PokerStars text goes through `pokerkit.PokerStarsParser`. Files are read as
  UTF-8 with an optional byte-order mark, and CRLF becomes LF. pokerkit
  supports only "Hold'em No Limit" and ignores antes and rake.

**When a hand counts as parsed.** pokerkit replays it, and the replayed stacks
equal the recorded `finishing_stacks` when the file has them.
- pokerkit splits a pot by whole chips. A source that records half chips on a
  chop differs by less than one chip per player, with the differences summing
  to 0. Such a hand counts as parsed, is flagged **odd chip**, and the count is
  printed. 8 of the 10,000 Pluribus hands are like this.
- Any other difference is a failure with its reason. Every failure is counted
  and printed (Gate F).
- This check exists because pokerkit splits a showdown pot silently when a
  history lacks its show actions.

**Definitions.** All are per player, per hand.
- **Raises and blinds.** A raise is any `CompletionBettingOrRaisingTo`, short
  all-ins included. Posting a blind is never voluntary.
- **Opportunity.** The player took at least one preflop action. Walks and
  blinds that are all-in from posting have none.
- **VPIP.** A preflop call of more than 0, or any preflop raise, out of
  opportunities. A big blind's check is not VPIP.
- **PFR.** At least one preflop raise, out of opportunities.
- **3-bet chance.** The first preflop decision where the player faces exactly
  one raise, did not make it, and pokerkit allows a raise
  (`can_complete_bet_or_raise_to()`). It counts at most once per hand, and a
  limper facing the open counts. A **3-bet** is a raise at that decision.
- **Saw flop.** A flop was dealt and the player had not folded before it.
  Players who are all-in count.
- **WTSD.** The hand ends with at least two players who never folded, and the
  player is one of them. Mucks count, and so do all-ins that run out.
  WTSD% = WTSD / saw flop.
- **W$SD.** WTSD hands in which the player received chips from a pot
  (`ChipsPushing`), out of WTSD hands. Chops and side pots count. Returned
  uncalled bets never pass through `ChipsPushing`, so they do not count.
- **bb/100.** 100 × Σ(payoff / big blind) / hands dealt, walks included. The
  big blind is `max(blinds_or_straddles[:2])`.

**Rules out:** HUD-style stats beyond these seven in v1, and any stat that
needs to know who the hero is, except through `--player`.

---

### 26. All-in EV adjustment (2026-11-14)

**Decided:** This includes multiway pots and side pots, as Ian asked on
2026-11-14.

**Which hands qualify.** At the first replay step where all four hold:
- no more betting is possible (`all_in_status`);
- at least two players have not folded;
- the board has fewer than five cards;
- every remaining player's hole cards are known.

If a remaining hand is unknown, the hand is counted as "not adjusted" and uses
its actual result.

**The adjustment.** For every player in a qualifying hand:
EV net = actual net − chips actually received + expected chips from the pots
at that moment.
- The pots are final at that point, because no more betting is possible.
- Returned uncalled bets never pass through the pots.
- So a folded player's EV equals their actual result, and the adjustments sum
  to 0.

**Expected chips** come from `equity.multiway.pot_shares`, over uniform
runouts:
- Each pot is split equally among the best hands of its eligible players.
- Only live hole cards and the board are removed from the deck. Folded cards
  stay in it, as they would on a site.
- The method:
  - **Exact enumeration** when at most two board cards are to come (at most
    1,081 runouts).
  - **Exact** for a heads-up hand with five cards to come, through
    `exact.hand_vs_hand`, with suit-isomorphic pairs sharing one enumeration.
  - **Seeded Monte Carlo** otherwise (three or more players preflop). It
    defaults to 20,000 runouts per hand. The seed is the run seed XOR the
    CRC-32 of the hand's source, so a hand's result does not depend on the
    files around it. The standard error is reported.

**Rules out:**
- Removing folded players' cards.
- Adjusting river all-ins (nothing is left to come).
- Monte Carlo where exact enumeration is cheap.

---

### 27. Grading real hands against push/fold Nash (2026-11-14)

**Decided:** A hand is graded only when it fits the push/fold game:
- it is heads-up (two players dealt in);
- the effective stack, min(SB, BB starting stack) / big blind before the
  blinds, is at most 20 bb;
- the small blind's first action is a fold or puts all of its chips in.

**The depth** is floor(effective + 0.5), clamped to 1 to 20 bb. That is the
nearest solved depth with halves rounded up (Ian chose the nearest depth), and
it is printed with every grade.

**The big blind** is graded only when it faces that jam and calls or folds. At
1 bb it has no decision.

**How a decision is graded.** It is the same class-level grade as the trainer
(DECISIONS 24), against the opponent's Nash strategy at that depth. A combo
with unknown cards is not graded.

**Hands that don't fit** are counted by reason: "not heads-up", "deeper than
20 bb", "small blind did not fold or go all-in", and "small blind's cards
unknown".

**Rules out:** interpolating between depths, and grading limps, min-raises or
multiway pots, which are not in the game.

---

### 28. pokerkit as a test oracle runs with a fixed hash seed (2026-11-14)

**What happened.** The final `py gate.py --full` of the autonomous run failed
on one case: `test_gate_c_slow.py::test_exact_within_3_se_of_pokerkit[JdTd-9c9s-]`.
All the other 288 tests passed, and every earlier full run had passed that
case.

**Reproduced first** (the gate-failure rule, SCOPE A5):
- **Alone, it passes.** Run five times on its own, the case passed.
- **The cause is the deck order.** pokerkit samples with the global `random`
  module from a deck whose order depends on Python's per-process string
  hashing. So the test's `random.seed(...)`, despite its comment, never made
  the oracle reproducible.
- **The proof.** Run under eight values of `PYTHONHASHSEED`, the same case gave
  z = −0.04, +0.68, +0.84, +0.41, +1.89, +0.20, −1.19 and −1.02.
- **Our side is not in question.** Our exact value for the same matchup equals
  phevaluator's enumeration exactly, in a test that passed in the same run.
- **The failure was a tail draw.** It was a draw beyond 3 SE in a test that had
  silently been random all along. With 20 cases at 3 SE, about 5% of full runs
  fail somewhere even when both sides are right.

**Decided:** `tests/pokerkit_oracle.py` runs pokerkit's `calculate_equities` in
a subprocess:
- `PYTHONHASHSEED=0` is fixed in advance, before any result under it was
  seen.
- `random` is seeded per case, as before.

Gate C's pokerkit check and the 3-way test in `tests/test_multiway.py` both use
it. **The 3 SE bar does not change.** The oracle is now one fixed,
reproducible draw. Two separate runs gave identical results, and all 20 Gate C
cases pass: max |z| 2.14 over the 17 cases with an equity strictly between 0
and 1, and the 3 locked cases agree exactly.

**Rules out:**
- Choosing a different hash seed after seeing results.
- Widening the 3 SE bar.
- Any test oracle whose randomness is not reproducible from the test itself.

---

### 29. A narrow exception to DECISIONS 9: a suggest-only advisor for disclosed play-money games (2026-11-15)

**Decided:** Ian approved this on 2026-11-15 (SCOPE A6), from his live-advisor
scope.
- **The exception.** Live, suggest-only advice is allowed only in **private
  play-money games where every player knows** the advisor is running. Poker
  Now is first.
- **The advisor shows; it never acts.** No auto-clicking or any other
  automated action. Ian parked auto-clicking for later, and it would need its
  own amendment, because it would make the advisor a bot.
- **It is visible.** It is never hidden from screen sharing or recording. No
  stealth or overlay-hiding features, including those in "Open Cluely"-style
  tools.
- **Never with real money, and never on ClubWPT Gold.** DECISIONS 13 stands
  unchanged. The README warning stands too.
- **Reading Poker Now.**
  - Poker Now's Terms of Service (effective 2024-11-01, read 2026-11-15)
    forbid using "an automatic device (such as a robot or spider) or manual
    process to copy or 'scrape' the Services ... without our express written
    permission".
  - They also forbid harvesting data, network monitoring and reverse
    engineering.
  - Ian chose to read the screen anyway, at his own account's risk.
  - The reader looks only at his own display: screen capture of the table
    window. It never touches Poker Now's network traffic, its code or its
    servers.

**Why:** Ian wants fast, sensible suggestions in friendly games where everyone
knows, with speed over precision. DECISIONS 9 existed to keep the project clear
of sites and games where assistance is cheating. This exception keeps that
protection everywhere else.

**Still out of scope until their own amendments:**
- Postflop solving: the TexasSolver spike may run, because it only measures.
- Serving a table beyond localhost (DECISIONS 12): the self-hosted table.

**Rules out:**
- Real-money tables, ClubWPT, and any site whose terms ban assistance
  outright.
- Auto-action and stealth.

**Not decided here:** whether captured screens may go to a cloud AI (Open
Cluely's design). The plan recommends against it, for speed and for friends'
privacy, and leaves the choice to Ian.

---

### 30. Phase 8 decisions, and Gate S2 pre-registered (2026-11-15)

**Decided:** Ian decided these on 2026-11-15.
- **D1: a local reader.** The live reader captures the Poker Now window and
  reads it on this machine. It does not send screenshots to Open Cluely's
  cloud AI. Friends' names never leave the laptop.
- **D4: TexasSolver download approved.** The file is
  `TexasSolver-v0.2.0-Windows.zip` from
  github.com/bupticybee/TexasSolver/releases: 41,415,352 bytes, AGPL-3.0,
  published 2021-11-04. It goes in the gitignored
  `data/external/texassolver/`, is pinned by SHA-256 (recorded below once
  downloaded), and runs only as a separate program. It is never linked or
  committed.
- **Capture and OCR packages approved.** `mss`, `Pillow` and Windows' OCR
  bindings go in an optional `live` extra in `pyproject.toml`. They are
  pinned, but installed only when spike S1 starts, and their exact versions
  are recorded then.
- **D6: where practice hands come from.**
  - Poker Now self-play: both seats, in two browser windows.
  - The public phh-dataset: HandHQ hands, and the heads-up bot-competition
    hands on Zenodo. Each download's size is stated before fetching.
  - PokerStars play-money hand-history files, for review after a session
    only. The advisor never runs on PokerStars, whose terms ban assistance
    (DECISIONS 29).
- **Phase 8 order.** S2 (TexasSolver speed) and S3 (preflop source above
  20 bb) run first. S1 (screen reading) waits for at least 50 of Ian's
  screenshots.

**Gate S2: fixed before the first solve.**

- **The grid:** 5 spots on 20 flops, 100 solves. Chips are in half big
  blinds; effective stacks count from before the blinds.

  | Spot | Preflop | Pot | Effective stack | Ranges (IP = SB, OOP = BB) |
  |---|---|---|---|---|
  | SRP25 | SB opens 2 bb, BB calls | 8 | 46 | IP: top 75% of combos; OOP: top 55% |
  | SRP50 | SB opens 2.5 bb, BB calls | 10 | 95 | the same |
  | SRP100 | SB opens 2.5 bb, BB calls | 10 | 195 | the same |
  | 3BP50 | BB 3-bets to 7 bb, SB calls | 28 | 86 | OOP: top 15%; IP: top 30% |
  | 3BP100 | BB 3-bets to 9 bb, SB calls | 36 | 182 | the same |

- **The ranges are for timing only, not a strategy.** "Top X%" ranks the 169
  classes by equity against a random hand. That equity comes from
  `data/preflop_169_exact.npz`, weighted by `pair_counts`. Whole classes are
  taken in that order until X% of 1,326 combos is reached, and the last class
  is partly weighted.
- **The 20 flops,** drawn with `random.Random(20261115)` from the 1,755
  suit-distinct flops (sorted descending):
  Kc7d6c, AcKd4h, JdJc6h, 9c6d3d, 8c4d4c, 9c4d3h, Tc2h2d, 6c4c2d, Tc8d7d,
  Ac6d2h, QcJhJd, Ac4d2h, 9c7c2c, 9c6d4c, 7d7c3h, 7c5c2c, Qc6c2c, Tc7c5d,
  KdKc6c, 8c7d2d.
- **Tree T1,** one size per street, for both players:
  - flop bet 33% of the pot, turn 66%, river 75%;
  - raises 60%, plus all-in on every street;
  - donk bets only on the river, at 75%;
  - `set_allin_threshold 0.67`.
- **Settings:** `set_thread_num 16`, `set_accuracy 2` (percent of the pot),
  `set_max_iteration 300`, `set_use_isomorphism 1`.
- **Pass needs all three:**
  - median wall time per solve at most 10 s, including the tree build;
  - 95th percentile at most 20 s;
  - every solve ends with TexasSolver's reported exploitability at most 2% of
    the pot.
- **If it fails:** the result is recorded as it is. The tree, the ranges and
  the bar are never retuned afterwards. Ian chooses between a precomputed flop
  library and a preflop-only V1.

**Why:** These spots cover the stacks Ian's friendly games will see. One size
per street is the "speed beats precision" tree from his scope. Fixing the
flops and ranges in advance means the gate measures the solver, not choices
made after seeing results.

**Gate S2 run details, fixed before the first S2 solve (2026-11-15).**
- **The download:** `TexasSolver-v0.2.0-Windows.zip`, SHA-256
  `0a9122fa0cd9384e6c1cbe0492e8a3b8ac7809890c649e1a53f77a59d6d50a7c`. It has
  4,790 members, none with an absolute or `..` path. The binary is
  `console_solver.exe`, run as
  `--input_file F --resource_dir resources --mode holdem`.
- **A sanity run.** The bundled sample (pot 4, stack 10) ran 10 iterations in
  11.6 s on 16 threads and wrote its JSON. The JSON has the flop root's
  actions and per-hand strategy, with bet sizes in absolute chips. Player 1
  is out of position.
- **Fixed now:**
  - `set_print_interval 10`, the solver's default. TexasSolver checks the
    accuracy target only when it prints.
  - `set_dump_rounds 1`: only the flop decision is dumped.
  - The reported exploitability is the last "Total exploitability" line in
    the log.
  - Each solve has a 120 s timeout. A solve that times out counts as over
    both time bars and as failing the exploitability bar.
- **The order.** Solves run flop by flop. For each flop, the spots go SRP25,
  SRP50, SRP100, 3BP50, 3BP100.
- **The stop-early rule.** After at least the first two flops (10 solves, one
  per spot per flop), the run stops as soon as FAIL is certain:
  - more than 50 of the 100 solves already over 10 s (the median cannot
    pass);
  - or more than 5 over 20 s (the 95th percentile cannot pass);
  - or any solve above 2% of the pot.
  
  Stopping early only saves time. It cannot turn a FAIL into a PASS.

---

### 31. After S2 failed: V1 is preflop suggestions plus a postflop equity helper; a flop library comes next (2026-11-15)

**Decided:** Ian chose "go with 2 now then 1" on 2026-11-15, from the
fallbacks offered when Gate S2 failed (GATES.md: single-raised pots never
converged in 120 s, and 3-bet pots took 50 to 76 s).

1. **Now (V1).**
   - **Preflop suggestions:** push/fold Nash at 20 bb or less (Gate D). Above
     20 bb, the source Ian picks in D3 after spike S3.
   - **A postflop helper, not a solver:**
     - the hero's equity against the villain's range on the current board;
     - the pot odds;
     - a call/fold (and bet/check) hint from simple, stated rules.
   - The helper's rules and its Gate G are pre-registered in a later DECISIONS
     entry, after Ian approves them.
2. **Next (option 1).**
   - **The flop library:** solve the common heads-up flop spots offline, in
     overnight runs, and look them up during play.
   - **The turn and river:** solve them live, only once a new pre-registered
     speed gate (S2b) passes on those smaller trees.
   - Bringing postflop solving into scope (decision D2) still needs its own
     amendment when option 1 starts.

**Why:** V1 is useful within days, and "speed beats precision" (Ian's
scope). S2 showed that live flop solves are minutes, not seconds, on this
laptop.

**Rules out:**
- Shrinking S2's tree or loosening its bar after the fact (DECISIONS 30).
- Calling the helper's hints "GTO". They are labelled as equity heuristics on
  screen and in the log.

---

### 32. V1 helper rules and Gate G, pre-registered before any helper code (2026-11-15)

**Decided:** Ian approved these on 2026-11-15, and they implement DECISIONS 31.

**Preflop: push/fold Nash at 20 bb effective or less.**
- It covers two decisions: the SB's first decision, and the BB facing an SB
  jam.
- The hand is graded at `depth_for(effective)`, the nearest solved depth
  (DECISIONS 27), with `PushFoldStrategy.grade`. The suggestion is the
  higher-EV action, shown with both EVs.
- Every other preflop decision gets "no suggestion" until Ian decides D3.

**Postflop: an equity helper, labelled "heuristic, not GTO".**
- **Equity** is the hero's against the villain's range, with combos that share
  a card with the hero or the board removed:
  - river and turn: exact (`exact.range_vs_range`);
  - flop: seeded Monte Carlo (`montecarlo.monte_carlo`), 20,000 samples, with
    its standard error. A pre-check measured 148 ms, while exact took 370 ms.
- **Facing a bet:** call if equity ≥ to call / (pot + to call) + 0.05,
  otherwise fold. Here "pot" includes the villain's bet. V1 never suggests a
  raise.
- **Free to check or bet,** in one of two modes. Ian ticked both, so it is a
  switch:
  - **hint**, the default: bet if equity ≥ 0.60, otherwise check. The bet size
    is 33% of the pot on the flop, 66% on the turn and 75% on the river, the
    same as S2's tree.
  - **equity:** no hint, just the numbers.

**The villain's range.**
- A **custom range for each decision**, in showdown's range syntax
  (`ranges.parse_range`), takes priority. Ian asked for custom ranges.
- Otherwise the **default**, shown on screen as an assumption, comes from the
  pot type and the villain's seat. These are the spike ranges from DECISIONS
  30:
  - single-raised pot: an SB villain holds the top 75%, a BB villain the top
    55%;
  - 3-bet pot: a BB villain (the 3-bettor) holds the top 15%, an SB villain
    (the caller) the top 30%.
- Node locking, meaning fixing the villain's strategy at a decision, needs a
  solver. It moves to option 1, and TexasSolver's support for it is checked
  then.

**The hand log** is one JSON line per suggestion in the gitignored
`data/live/advice.jsonl`: the spot, the suggestion, the numbers and the time
taken. The reader adds the action Ian actually took in Phase 10.

**Gate G**, with bars as Ian approved them:
- At least 40 fixture spots (`tests/fixtures/live/spots.toml`) get the
  expected suggestion.
- Preflop suggestions at 20 bb or less equal the push/fold solution's pure
  actions.
- River and turn equity equal the hand-counted outs exactly.
- Flop Monte Carlo lands within 3 SE of exact enumeration on 10 spots.
- The 95th-percentile time per suggestion over the fixture is at most 300 ms.
- Every suggestion appears in the log.

**How Gate G's latency is measured (added 2026-11-15, before the gate was
recorded).**
- **What happened.** Inside the full pytest run, the latency test measured a
  95th percentile of 937 ms, against 128 ms when the module ran on its own.
- **Reproduced.** The same code measured:
  - 879 ms with coverage tracing on;
  - 519 ms without it, while a parallel session's CFR spike held the CPU at
    93%;
  - 1,264 ms in a clean subprocess under that same load.

  Two artifacts, then: pytest-cov's tracer, and other heavy work on the
  machine. Neither is the advisor's speed in use.
- **Decided.** The latency is timed in a separate Python process with
  coverage tracing stripped (`test_latency_without_coverage_tracing`), on an
  otherwise idle machine. **The 300 ms bar does not change.** A gate run with
  other heavy work on the machine does not count; it is repeated.

---

### 33. D3: the preflop source above 20 bb is our own model at R_oop = 0.9, after an R sweep (2026-11-15)

**Decided:** Ian chose this on 2026-11-15, from spike S3 (`docs/preflop-source.md`).
SCOPE amendment A7 brings the model into scope.
- **The model.** S3's heads-up preflop game:
  - SB: fold, raise to 2.5, or jam;
  - BB facing the raise: fold, call, 3-bet 3×, or jam;
  - SB facing the 3-bet: fold, call, or jam;
  - calls or folds against every jam.
  
  It is solved by our CFR+. A pot that reaches the flop is valued as
  c(2·share − 1), with share = 1 − R_oop·(1 − E); the flop is not played.
- **R_oop = 0.9 is the default.** R_oop is the share of its equity the
  out-of-position player realizes after the flop.
- **The sweep comes first.** R_oop runs over 0.80, 0.85, 0.90, 0.95 and 1.00
  at 25, 50 and 100 bb, to show how much the advice depends on R before it is
  fixed. The sweep is a measurement. It runs only after Gate G's latency
  check, so that check gets an idle machine.
- **Labelling.** The charts appear as "model chart" on screen and in the hand
  log, next to push/fold's "Nash" label.
- **Below 20 bb nothing changes.** Push/fold still answers at 20 bb or less
  (Gate D). The overlay names which source answered, because the advice
  changes at 20 bb (S3 measured the jump).

**Still to be fixed before the product solve:** Gate P, pre-registered after
the sweep. It covers:
- the stack grid and the rule for stacks in between;
- the iteration count and an exploitability bar;
- continuity (the jam-only 20 bb game reproduces `data/pushfold.json`, which
  S3 has already shown);
- the sanity bound at 20 bb;
- an independent payoff check.

S3 suggested all of these; Ian sets the numbers.

**Why:** No licensed heads-up chart exists for 25 to 100 bb (S3's survey). V1's
equity helper, and the flop library after it, need preflop ranges above 20
bb. R = 1 plays unlike heads-up poker: the BB never folds to a raise.

**Rules out:**
- Presenting model charts as Nash, or as checked against an outside answer.
- Limps, min-raises and other sizes in v1 (SCOPE).
- Fixing R before the sweep.

---

### 34. The preflop model: R = 0.90 with an R-sensitivity flag, and Gate P pre-registered (2026-11-15)

**Decided:** Ian set these on 2026-11-15, after the R sweep (`docs/preflop-source.md`,
"The R sweep").

**The game, unchanged from spike S3.**
- SB first in: fold, raise to 2.5, or jam.
- BB facing the raise: fold, call, 3-bet to 7.5, or jam.
- SB facing the 3-bet: fold, call, or jam.
- Calls or folds against every jam.
- A called raise or 3-bet is valued at c(2·share − 1) for the SB, with
  share = 1 − R_oop·(1 − E). A called all-in nets S(2E − 1).
- E comes from the exact matrix.

**R.**
- **The product solution uses R_oop = 0.90.**
- The same grid is also solved at R_oop = 0.85 and 0.95. A suggestion is
  flagged **"depends on R"** when the class's most likely action at that node
  differs between the 0.85 and 0.95 solutions.

**The grid and lookup.**
- The grid is 25, 30, 40, 50, 60, 70, 80, 90 and 100 bb. Ian approved
  25/30/40/50/60/80/100; 70 and 90 are added so that "nearest" never jumps
  20 bb.
- **Lookup rule:** an effective stack of 20 bb or less uses push/fold
  (DECISIONS 32). Above 20 bb, it uses the nearest grid depth, with ties going
  to the smaller stack; above 100 bb, it uses 100 bb. The depth used is printed
  with every suggestion.

**The solve.** `cfr_plus`, exactly 1,000 iterations, average policy, payoffs
from `data/preflop_169_exact.npz`. No early stopping and no re-running until
the answer matches. 27 solves in all (9 depths × 3 R values), stored in the
committed `data/preflop_model.json`.

**Gate P: all four bars must pass.**
1. **Exploitability:** at most 0.001 bb/hand at every depth, for all three R
   values, measured by `showdown.cfr.exploitability` on the compiled tree.
2. **Continuity:** the jam-only game at 20 bb (no raise) reproduces
   `data/pushfold.json` exactly, every probability equal, after 1,000
   iterations.
3. **Sanity:** at 20 bb with R 0.90, the full game's SB value is at least
   push/fold's 20 bb value, minus both games' exploitabilities.
4. **Payoffs:** a separate closed-form function, written from the rules above
   and not from the game's code, gives every terminal payoff for every class
   pair. It must match every terminal utility in the compiled tree to 1e-12,
   at 25 and 100 bb, for all three R values.

**Fixed now:** the 9 × 3 grid, 1,000 iterations, and the four bars.
**Rules out:** changing any of them after results are seen, except by a dated
amendment.

Wiring the model into the advisor (preflop suggestions above 20 bb, and the
helper's villain ranges) is a separate step. It needs its own entry and an
extension of Gate G, after Ian's OK.

---

### 35. The preflop model in the advisor, and Gate G extended (2026-11-15)

**Decided:** Ian approved the wiring and these choices on 2026-11-15. It
uses the Gate P model (DECISIONS 34) at R_oop = 0.90.

**Preflop above 20 bb: the model answers its six decisions.**

| `--facing` | Decision | Model node |
|---|---|---|
| `sb_first` | SB first in | `""` |
| `bb_vs_raise` | BB facing the open | `r` |
| `sb_vs_3bet` | SB facing the BB's 3-bet | `rr` |
| `bb_vs_4bet_jam` | BB facing the SB's jam over the 3-bet | `rrj` |
| `sb_vs_jam` | SB facing the BB's jam over the open | `rj` |
| `bb_vs_jam` | BB facing the SB's first-in jam | `j` |

- **The depth** follows DECISIONS 34's lookup rule and is printed.
- **The suggestion** is the class's most likely action at that node. Ties go
  to the earlier action in fold, call, raise, all-in order.
- **What is shown with it:**
  - every action's frequency (the mix);
  - "depends on R" when DECISIONS 34's flag is set;
  - the source, "model chart, R 0.90, D bb", never "Nash".
- **Names.** The model's "all-in" is shown as "jam". A raise carries its size:
  2.5 bb for the SB's open, and 3× the open faced for the BB's 3-bet (the
  model's ratio).
- **20 bb or less is unchanged** (DECISIONS 32). Push/fold answers `sb_first`
  and `bb_vs_jam`. The other four decisions, and `other` at any depth, get
  "no suggestion".

**Raise sizes: map and flag** (Ian's choice).
- For `bb_vs_raise` and `sb_vs_3bet`, the villain's raise-to is read from
  the spot as (pot + to call) / 2, so these spots need a to-call above 0.
- The model's answer is given at any size. When the raise-to differs from the
  model's (2.5 or 7.5 bb) by more than 0.05 bb, the suggestion says so, for
  example "model assumes a 2.5 bb open; you face 3.5 bb".

**A reach rule (added with this entry, after measuring the model).**
- **The problem.** The model's strategy at a decision it almost never reaches
  is not advice. At 50 bb, for example, the BB never 3-bets to 7.5, so:
  - the stored answer to a 3-bet has the SB calling with 72o 84% of the time;
  - the BB's answer to a 4-bet jam is an untouched 50/50.
- **The measurement.** It was taken before this rule was written. The figure
  is the percentage of deals that reach each node at R 0.90:

  | Depth | `r` | `rr` | `rrj` | `rj` | `j` |
  |---|---|---|---|---|---|
  | 25 | 56.9 | 0.000 | 0.000 | 16.2 | 2.25 |
  | 30 | 61.2 | 0.000 | 0.000 | 16.2 | 1.72 |
  | 40 | 70.4 | 0.001 | 0.000 | 15.9 | 0.001 |
  | 50 | 72.5 | 0.004 | 0.000 | 15.3 | 0.001 |
  | 60 | 77.3 | 0.642 | 0.049 | 14.0 | 0.001 |
  | 70 | 80.9 | 1.87 | 0.124 | 12.6 | 0.001 |
  | 80 | 82.8 | 5.36 | 0.350 | 9.67 | 0.001 |
  | 90 | 84.4 | 7.00 | 0.412 | 6.98 | 0.001 |
  | 100 | 84.5 | 9.32 | 0.512 | 5.04 | 0.002 |

- **The rule.** A decision is answered from the model only if the model
  reaches its node in at least **0.1% of deals** at the looked-up depth.
  Otherwise the advisor gives "no suggestion: the model almost never reaches
  this decision at D bb".
  - The bar sits in clear gaps for `rr` and `j`.
  - Of `rrj`, it excludes only 60 bb (0.049%).
- **What this costs.** A first-in jam at 40 bb or more, and a 3-bet to about
  7.5 bb at 50 bb or less, get no suggestion. Answering an opponent who
  deviates from the model like that is Phase 12's job (exploiting).

**Postflop: the model's ranges, weighted** (Ian's choice).
- **The default villain range** comes from the model at the looked-up depth,
  with 25 bb for every stack of 25 bb or less. A class's weight is the product
  of the villain's own action frequencies along the line:

  | Pot | Villain | Weight |
  |---|---|---|
  | single-raised, `rc` | SB | P(raise first in) |
  | single-raised, `rc` | BB | P(call the open) |
  | 3-bet, `rrc` | BB | P(3-bet the open) |
  | 3-bet, `rrc` | SB | P(raise first in) × P(call the 3-bet) |

  Each combo carries its class's weight. A custom `--villain` range still
  overrides it (DECISIONS 32).
- **The same reach rule applies.** When the model reaches the pot (`rc` or
  `rrc`) in less than 0.1% of deals, the helper uses the fixed top-%
  default from DECISIONS 32, labelled as such. That covers 3-bet pots at 50 bb
  and below.
- **Fixed defaults stay selectable.** `showdown advise --ranges fixed` gives
  DECISIONS 32's behaviour.
- **Weighted equity.**
  - `exact.range_vs_range` and `montecarlo.monte_carlo` take optional
    villain combo weights. A pair's weight is its villain combo's.
  - With no weights, both run their current code unchanged. Gate C's results
    cannot move.

**Gate G, extended.** All of these must pass, along with Gate G's existing
bars (DECISIONS 32):
1. **New spots.** A new fixture has at least 30 preflop spots above 20 bb:
   - at least 4 for each of the six decisions, at depths where the model
     reaches it;
   - at least 4 that must get "no suggestion" (unreached decisions, the four
     non-push/fold decisions at 20 bb or less, and `other`).

   The depth, decision, action and R flag of each spot are written by hand
   from `showdown preflop chart`. Its mix must equal the stored model to
   1e-12.
2. **Sizes.** At least 2 spots face a non-model raise size. Each gets the
   size note and the model's answer. A suggested 3-bet is 3× the open faced.
3. **Model ranges.**
   - At 100 bb, for 3 classes in each of the four ranges, the weights equal
     the stored frequencies multiplied by hand.
   - At least 4 turn or river spots against a model range match a separate
     weighted brute-force count with phevaluator, to 1e-12.
   - At least 2 flop spots land within 3 SE of exact weighted enumeration.
   - A 3-bet pot at 50 bb uses the fixed default, with its label.
4. **The old fixture.** 42 of the 43 old spots keep their answers, run with
   `--ranges fixed`. The 43rd is AsKd as the SB first in at 40 bb. Its answer
   was "no suggestion until D3 picks a source", so it now expects the model's
   answer, by design.
5. **Latency.** The 95th percentile over old and new spots is at most
   300 ms, measured as DECISIONS 32 sets out.
6. **The log.** Every suggestion is logged, with its mix and notes.

**Rules out:**
- Calling the model's answers Nash.
- Answering from a node below the reach bar.
- Moving any bar after results are seen, except by a dated amendment.

---

### 36. The jam-vs-range helper, Phase 12's first slice, and Gate J pre-registered (2026-11-15)

**Decided:** Ian chose these on 2026-11-15. SCOPE amendment A8 brings an
exploitative answer, shown beside the Nash or model one, into scope for this
helper. It is the first, manual slice of Phase 12 (`docs/plan-live-advisor.md`):
Ian supplies the read; the opponent model comes later.

**What it answers:** call or fold against an all-in, at three decisions:

| Decision | The jam | Pot | To call |
|---|---|---|---|
| `bb_vs_jam` | the SB's first-in jam | S + 1 | S − 1 |
| `sb_vs_jam` | the BB's jam over the open | S + 2.5 | S − 2.5 |
| `bb_vs_4bet_jam` | the SB's jam over the 3-bet | S + 7.5 | S − 7.5 |

The pot and to-call come from the spot (`--pot`, `--to-call`). The table shows
them at the model's sizes, with S the effective stack. A jam decision without
a to-call above 0 is an error.

**When it runs** (Ian ticked both):
- **With a range from Ian** (`--villain` or `--villain-top N`), it answers
  every one of the three decisions, at any depth, including 20 bb or less.
  This is the exploit view.
  - Its answer is the suggestion.
  - The Nash (push/fold) or model answer is shown beside it, when one
    exists. The note says whether they agree, and what the helper's choice
    gains against that range, in bb.
- **Without a range,** it fills the jams that get no answer today:
  - `bb_vs_jam` above 20 bb where the model's reach rule skips it (40 bb and
    deeper): the labelled default is the **top 20%**;
  - `bb_vs_4bet_jam` at 60 bb or less, which push/fold has no 3-bet for and
    the model skips: the labelled default is the **top 8%**;
  - `sb_vs_jam` at 20 bb or less: no default was set, so it stays "no
    suggestion: give --villain or --villain-top".
- **Every other case is unchanged.** Push/fold answers `bb_vs_jam` at 20 bb
  or less, and the model answers jams it reaches (DECISIONS 32, 35).

**The range.**
- `--villain-top N` (0 < N ≤ 100) is the top N% by equity against a random
  hand, in whole classes, as `top_range` builds the postflop defaults. The
  label gives the share it actually covers.
- It is also accepted wherever `--villain` is, postflop included.
- `--villain` and `--villain-top` together are an error.
- **Preflop, a range must be whole hand classes** (`AKs`, not `AhKh`), or the
  spot is an error. Whole classes are what make the equity exact.
- A preflop `--villain` on a decision that isn't one of the three jams is an
  error, rather than being silently ignored.

**The equity, exact and instant.**
- Hero hand h is in class i. The villain's class j carries weight w_j: 1 for
  Ian's range, or the solution's frequency in the bar 1 checks.
- n_j counts the combos of class j that share no card with h.
- M is the exact 169 × 169 matrix (DECISIONS 21).
- Then E = Σ_j w_j · n_j · M[i, j] / Σ_j w_j · n_j.

This is exact for the specific hand h. Every combo of class i is a suit
relabelling of h, and every class j is closed under relabelling, so h's
average equity against class j equals the class average M[i, j]. Bar 2 checks
this against board enumeration.

**The call rule** (Ian's choice: pot odds, flag close calls).
- **Call** if E ≥ to call / (pot + to call). There is no margin, because no
  later street can waste the equity.
- **The EV is shown relative to folding:** E · (pot + to call) − to call, in
  bb.
- **"close"** is flagged when |E − price| < 0.02.
- The source reads "jam vs range: exact equity", and the range is labelled as
  custom, as `--villain-top`, or as the assumed default.
- Ian did not choose the break-even-width readout, so it is not built.

**Gate J.** All of these must pass, and every existing gate must still pass:
1. **It reproduces Nash and the model.** The villain range is the solution's
   own jam range, weighted by its frequencies, and the call rule is the one
   above.
   - Push/fold: the BB facing the SB's jam, at every depth from 1 to 20 bb.
   - The model, at the decisions it reaches:
     - `j` at 25 and 30 bb;
     - `rj` at every grid depth;
     - `rrj` at 70 to 100 bb.

   The helper's call or fold must equal the solution's for every class the
   solution plays purely (≥ 0.99). The exception is a class whose EV of
   calling, relative to folding, is within 0.001 bb of zero. It counts as
   indifferent, and the number of such classes is reported.
2. **The equity is exact.** On at least 5 spots of a specific hand against a
   small whole-class range, the matrix equity equals exact board enumeration
   over every villain combo (`hand_vs_hand`), to 1e-9. These run in the slow
   suite.
3. **Hand-worked spots.** A fixture of at least 10 spots, each with its
   price, call or fold, and EV worked out by hand from `showdown matrix show`
   values. It covers:
   - at least 2 close calls;
   - the exploit view at 20 bb or less, beside Nash;
   - both defaults;
   - `--villain-top`;
   - the errors (a partial class, a missing to-call, both range flags).
4. **Latency.** The 95th percentile over every Gate G and Gate J spot is at
   most 300 ms, by DECISIONS 32's method.

**Changes to Gate G's fixture, by design.**
- Two of the extended fixture's "no suggestion" spots now get the default
  answer:
  - KhKd facing a first-in jam at 50 bb;
  - AhAd facing a 4-bet jam at 60 bb.
- They move to Gate J's fixture. No other Gate G spot changes.

**Rules out:**
- Calling the helper's answer Nash.
- A margin on the call rule.
- Partial-class ranges preflop.
- Moving any bar after results are seen, except by a dated amendment.

---

### 37. Push/fold exploit charts (2026-11-15)

**Decided:** Ian chose this on 2026-11-15, after the exploit-potential
measurement. It is a second, manual slice of Phase 12 under SCOPE A8: Ian
gives a read, and showdown gives the best response, what it gains, and what
it risks.

**The command.**
```
showdown pushfold exploit <stack> --villain-calls N   # you are the SB; the BB calls the top N%
showdown pushfold exploit <stack> --villain-jams N    # you are the BB; the SB jams the top N%
```
- **The stack** uses push/fold's nearest solved depth (DECISIONS 27), from 1
  to 20 bb.
- **The read** is the top N% by equity against a random hand, in whole
  classes (`top_range`), the same ordering as `--villain-top`
  (DECISIONS 36). Phase 12's other ordering, "Nash's own calling order", is
  left for the opponent model.
- **The best response** is pure, class by class: jam (or call) when that
  action's EV against the read is strictly above folding's. It uses
  `sb_action_values` and `bb_action_values`.

**What it prints,** in bb per hand in the hero's seat:
- the game value (Nash against Nash);
- Nash's EV against the read, and the best response's EV against the read,
  each also shown as an edge over the game value;
- the gain, best response minus Nash. It is also given as bb/100 over a
  heads-up session, which is the gain × 50, because the hero holds that seat
  in half the hands;
- **the risk:** the best response's EV against a Nash opponent, minus the game
  value. It is never positive, and shows what the exploit costs if the read is
  wrong;
- the best-response chart, as `pushfold chart` draws it: 100 or ".".

**Bars,** all in the fast suite:
1. **Independent EVs.** The command's best-response and Nash EVs equal the
   compiled push/fold tree's own computation, to 1e-9: `cfr.best_response`
   for the best response, and `cfr.policy_value` for Nash against the read.
   This is checked at 5 and 15 bb, for both seats, at two reads each.
2. **The measured numbers.** At 10 bb, against a BB who calls the top 15%,
   the best response is +0.427 and Nash +0.133 over the game value, to
   1e-3. Against an SB who jams any hand at 20 bb (`--villain-jams 100`), the
   gain is +0.747 bb/hand.
3. **The risk** is at most 1e-5, the solution's exploitability, at every
   depth from 1 to 20 bb, for both seats, with reads of 15%, 50% and 100%.
4. **The chart** is the per-class argmax of the two action values.

**Rules out:**
- Presenting a best response as safe. The risk line is always printed.
- Moving a bar after results are seen.

---

### 38. Spike S4: b-inary's postflop-solver as the postflop engine, and Gate S4 pre-registered (2026-11-15)

**Decided:** Ian chose this spike on 2026-11-15, after the open-source survey,
and approved the downloads:
- `rustup-init.exe` (x86_64-pc-windows-gnu, 14,862,151 bytes, SHA-256
  `f6289656ce42e1099f3cbc6f10ef6321dfde54773faf599dd36fd3b1f07d9103`, which
  matches static.rust-lang.org's published checksum);
- stable Rust 1.100.0, minimal profile (149,991,448 bytes compressed),
  installed with `--no-modify-path`;
- b-inary/postflop-solver at commit `9d1509fe5077d019825f833eed04b16d342dfda1`
  (2023-10-01, AGPL-3.0-or-later);
- its crates from crates.io.

**Why.** S2 failed: TexasSolver took 50 to 76 s on 3-bet-pot flops, and never
converged on single-raised pots within 120 s. The survey found postflop-solver
to be the fastest open engine. It uses discounted CFR, combines isomorphic
runouts, and has node locking (`lock_current_strategy`). Its author reports
it faster than PioSOLVER. Development stopped in October 2023.

**The separate-process boundary** (DECISIONS 29) stays.
- The spike writes a small Rust bridge, our own code, into
  `data/external/postflop-solver/bridge/` (gitignored). The bridge depends on
  the pinned solver.
- The bridge reads one spot as JSON and writes one result as JSON. Python calls
  it with `subprocess`.
- The compiled binary links AGPL code. It is never committed, linked into
  showdown, or distributed.

**The grid, the same as S2's** (DECISIONS 30). S2's code is reused.
- The same 5 spots (SRP25, SRP50, SRP100, 3BP50, 3BP100), with the same pots
  and stacks, in half-big-blind chips.
- The same 20 flops, run in the same flop-by-flop order.
- S2's ranges, the top N% by equity against a random hand. The last class
  carries its fractional weight, which postflop-solver's `AA:0.5` syntax
  takes as is.

**The tree, T1, as postflop-solver expresses it:**

| Street | Bets | Raises |
|---|---|---|
| flop | "33%, a" | "60%, a" |
| turn | "66%, a" | "60%, a" |
| river | "75%, a" | "60%, a" |

- Donk bets: none on the turn (an empty list), and "75%" on the river.
- The all-in thresholds (`add_allin_threshold` 1.5, `force_allin_threshold`
  0.15, `merging_threshold` 0.1) are the library's defaults. TexasSolver's
  0.67 all-in threshold has no exact equivalent, so the two trees can differ
  slightly near all-in. The spike prints each tree's node count.

**Settings.**
- Threads: rayon's default, all 16 logical cores.
- The target is 2% of the starting pot, measured as `compute_exploitability`
  (the mean of the two players' best-response gains, in chips; NashConv/2,
  the same convention as DECISIONS 7), at most 300 iterations.
- 32-bit storage. Any spot whose uncompressed tree needs more than 10 GB of
  this laptop's 15.7 GB uses the solver's 16-bit compression, and the spike
  says so.
- Each solve has a 120 s timeout. The time counts from process start to
  result, so it includes building the tree and allocating memory.

**Gate S4,** with S2's bars:
- the median wall time per solve is at most 10 s;
- the 95th percentile is at most 20 s;
- every solve ends with exploitability at most 2% of the pot.

S2's stop-early rule applies: a run stops only once its FAIL is certain.

**Reported, not gated:**
- **The model ranges.** A second pass replaces the top-% ranges with the
  preflop model's ranges (DECISIONS 35) on the first 5 flops.
- **Node locking.** On SRP50 and the first flop, the BB (out of position)
  is locked to never fold to the SB's 33% flop bet. The spike compares the
  SB's flop betting frequency, overall and with its weakest third of hands,
  with and without the lock.
- Memory per spot, and iterations to target.

**What follows from the result.**
- **If S4 passes,** D2 (postflop solving in scope) goes to Ian, with a SCOPE
  amendment. It would unlock option 1 (DECISIONS 31) and Phase 12's postflop
  exploits.
- **If it fails,** it is recorded as such, and the equity helper stays.

**Rules out:**
- Changing the tree, ranges, threads or bars after the first solve.
- Building any other solver without asking.

---

### 39. The PHH dataset and a human-leak measurement (2026-11-15)

**Decided:** Ian approved the download on 2026-11-15:
- **The file:** `poker-hand-histories.zip`, 20,289,230,983 bytes, the only
  file in Zenodo record 17136841.
- **The record:** "A Dataset of Poker Hand Histories", Juho Kim, published
  2025-09-16, DOI 10.5281/zenodo.17136841, CC BY 4.0.
- **Checks:** it must match Zenodo's md5 `5a49377ab4ea30db3aa887c8e0ce580f`.
  Its SHA-256 is then pinned in `tests/external_data.py`.
- **Where it lives:** `data/external/phh-zenodo/` (gitignored). Its members
  are listed and checked for absolute or `..` paths before anything is
  extracted, and only the online no-limit hands are extracted.
- **Nothing from it is committed.**
- **Timing:** the download started before this entry was committed. Nothing
  was opened or measured before it.

**What is measured** (spike `spikes/2026-11-15-phh-leaks.py`, note
`docs/human-leaks.md`):
- **Which hands:** every online no-limit hold'em hand that `hh/parse.py`
  replays to its recorded finishing stacks (DECISIONS 25's rule).
- **Grouping:** by table size (heads-up, 3 to 6 players, more) and by stake.
- **Per player:**
  - VPIP, PFR and 3-bet;
  - fold to a flop continuation bet, and flop continuation-bet frequency;
  - for spots at 20 bb effective or less: how often players jam first in,
    and how often they call a jam.

  The sample size goes with every figure.
- **Purpose.** These are candidate starting points for Phase 12's opponent
  model: the prior a read shrinks toward. They are not exploit
  recommendations.
- **Caveat.** These hands are 2009 real-money online play, mostly 6-max, so
  heads-up play-money friends will differ. The note says so on its first
  line.

**Rules out:**
- Committing third-party data.
- Treating these rates as facts about Ian's friends.

**Amendment to DECISIONS 39 (2026-11-15), after the first look at the file
format and before any measurement.**
- **What the data turned out to be.** The download matches Zenodo's size and
  md5. Its online hands are `data/handhq/`: 21,782 `.phhs` files, 16.3 GB,
  in 27 site-and-stake folders from July 2009. These hands record:
  - no stacks (`starting_stacks = [inf, ...]`);
  - no winnings;
  - hidden hole cards for most players.
- **Two parts of the entry can't be done:**
  - `hh/parse.py`'s filter, which replays each hand to its finishing stacks,
    has nothing to reconcile.
  - The 20 bb-or-less jam measures need effective stacks and all-ins, which
    are unknown here. They are dropped.
- **Instead, the hands are read from the zip directly,** with no extraction
  at all. Each hand's PHH action list is parsed by the spike.
  - A hand counts if its variant is no-limit hold'em (`NT`), it has two or more
    players, and every action parses and belongs to a dealt-in player.
  - Every other hand is counted, with its reason.
- **The measures, from the action lists:**
  - **VPIP:** the player's first voluntary preflop action is a call (`cc`
    with chips owed) or a raise (`cbr`). The big blind checking is not VPIP.
  - **PFR:** the player raises preflop.
  - **3-bet:** the player acts preflop facing exactly one raise: a chance.
    Raising then is a 3-bet.
  - **Flop continuation bet:** the last preflop raiser sees the flop and
    acts before anyone bets: a chance. Betting then is a continuation bet.
  - **Fold to a continuation bet:** a player's first action facing that bet,
    before any raise of it, is a fold.
- **The figures:**
  - **Grouping:** by table size (heads-up, 3 to 6, 7 or more) and by stake.
  - **Spread across players:** for players with at least 500 hands, the
    quartiles of VPIP and PFR, and the shares of players with VPIP at least
    40% and at most 15%.
  - **Sample sizes:** with every figure.
- **The SHA-256 of the 20 GB zip** is computed in chunks by the spike and
  pinned in `tests/external_data.py`. `require()` reads whole files, so no
  test reads this one.

---

### 40. D2: postflop solving comes in, for exploit solves between sessions and an overnight flop library; Gates X and L pre-registered (2026-11-15)

**Decided:** Ian chose these on 2026-11-15, after Gate S4. SCOPE amendment A9
brings postflop solving into scope, for use ahead of time only.

**Why.** S4 measured b-inary's postflop-solver at 0.5 to 2 minutes per
flop. That is too slow for live play, but fine between sessions and
overnight. Its node locking works: a BB locked to never fold makes the
solved SB value-bet more and bluff less. That makes it the tool for Ian's
headline goal, exploiting deviations.

**Common to both uses.**
- **The engine:**
  - postflop-solver at `9d1509fe5077d019825f833eed04b16d342dfda1`;
  - Rust 1.100.0, `x86_64-pc-windows-gnu`, with only the `rayon` feature
    and `-A dangerous_implicit_autorefs`, as built for S4.
- **The bridge:** our own Rust program, in `bridges/postflop/`, committed
  with an AGPL-3.0-or-later notice because it links the solver.
  - The solver checkout and the compiled binary stay in the gitignored
    `data/external/postflop-solver/`. They are never distributed.
  - showdown calls the binary as a separate process (DECISIONS 29).
  - `showdown postflop build` builds it.
- **The ranges** are the preflop model's weighted ranges (DECISIONS 35):
  - single-raised pots use the `rc` line;
  - 3-bet pots use the `rrc` line.
- **The pot sizes** are the model's: 5 bb after an open and call, 15 bb after
  a 3-bet and call. The stack behind is S − 2.5 or S − 7.5 bb. Chips are
  0.1 bb, so bet sizes round finely.
- **The tree is T1,** as S4 built it: 33% / 66% / 75% bets plus all-in, 60%
  raises plus all-in, no turn donk bets, and a 75% river donk.
- **The target** is 2% of the pot (`compute_exploitability`), with at most
  1,000 iterations.

**1. Exploit solves: `showdown postflop exploit`.**
- **Input:** a pot type (`srp` or `3bp`), an effective stack, a flop, the
  hero's seat, and one read about the villain's first flop decision:

  | Read | The villain's lock |
  |---|---|
  | `never-folds` | Facing the hero's flop bet, calls with every hand, never folds or raises |
  | `over-folds` | Facing the hero's flop bet, folds its weakest 70% of hands by flop equity, calls the rest |
  | `never-bets` | When checked to, or first to act, always checks |
  | `always-bets` | When checked to, or first to act, always makes its 33% bet |

  The lock covers that one flop decision. Turn and river play stays solved.
- **The output:**
  - the hero's flop strategy with and without the lock: action frequencies
    overall, and for the strongest, middle and weakest thirds of its hands
    by equity;
  - the hero's EV in each solve;
  - each solve's exploitability.

  The EV change includes the villain's own loss from the leak, so it is not
  labelled as "gain from adapting".
- **Gate X.** Its test set is SRP50, with the hero as the SB, on 10 flops
  drawn with seed 20261116 from the 1,755 suit-distinct flops, written into
  the test.
  1. **The lock holds:** at the locked node, the villain's solved strategy
     equals the lock for every hand, to 1e-6.
  2. **Convergence:** every test solve reaches 2% of the pot within
     10 minutes.
  3. **Direction against `never-folds`:** the hero's betting with its weakest
     third falls on at least 8 of the 10 flops.
  4. **Direction against `over-folds`:** the hero's betting with its weakest
     third rises on at least 8 of the 10 flops.
  5. **The command** prints both strategies and both EVs. A CLI test checks
     this.

**2. The overnight flop library.**
- **Spots:**
  - 3-bet pots at 100 bb, the depth the model reaches;
  - single-raised pots at 25, 50 and 100 bb.
- **Flops.** All 1,755 suit-distinct flops are solved, in coverage order:
  - suit patterns that are dealt most often (rainbow, then two-tone, then
    monotone and paired) come first;
  - ties are broken with seed 20261116.

  So the library is useful early and grows each night.
- **What is stored, per flop:** each player's per-hand action frequencies
  at the flop's first decisions:
  - the OOP first to act;
  - the IP after a check;
  - the IP facing an OOP bet;
  - the OOP facing an IP bet after a check.

  Frequencies are whole percentages. Each flop's exploitability, iterations
  and solve time go into a manifest.
- **Where it lives:** `data/library/` (gitignored; the library could exceed
  100 MB). The manifest's summary is committed with each gate record.
- **Runs** (Ian's choice: overnight, on AC):
  - `showdown postflop library build --spot 3BP100 --until 07:00` runs only
    when Ian starts it;
  - it refuses to start on battery;
  - it resumes where it stopped, one flop per process;
  - each solve has a 30-minute safety timeout.
- **Live use.** `showdown advise` answers a flop decision from the library
  when every one of these holds:
  1. the spot uses the default (model) ranges, not a custom `--villain`;
  2. the pot type has a library at the depth nearest the effective stack
     (single-raised pots: 25, 50, 100 bb; 3-bet pots: 100 bb for stacks of 60
     bb and more);
  3. the flop, up to suit symmetry, is solved;
  4. the decision is one of the stored four.

  The suggestion is the hand's most likely action, shown with its mix and
  labelled "flop library, R 0.90, D bb". A bet size the tree doesn't use gets
  a size note, as preflop does. Everything else keeps the equity helper.
- **Gate L,** run once a spot's library has at least 100 flops:
  1. **Accuracy:** every stored flop's exploitability is at most 2% of the
     pot.
  2. **Suit symmetry:** for 1,000 random (flop, hand, suit permutation)
     triples, the lookup on the permuted flop and hand equals the stored
     canonical entry exactly.
  3. **Stability:** 10 random stored flops, solved again from scratch, give
     root frequencies within 0.02 of the stored ones, by mean absolute
     difference over hands and actions.
  4. **Latency:** the 95th percentile over every Gate G and Gate J spot,
     plus 20 library lookups, is at most 300 ms (DECISIONS 32's method).
  5. **Nothing else moves:** every Gate G and Gate J spot keeps its answer.
     Their flop spots use custom ranges or fixed ranges, which never touch the
     library.

**Rules out:**
- Solving during live play.
- Approximating an unsolved flop by a "similar" one. That would need its own
  decision.
- Committing AGPL binaries or the solver's source.
- Moving any bar after results are seen, except by a dated amendment.

**Build order:**
1. The bridge and `showdown postflop build`.
2. `showdown postflop exploit`, then Gate X.
3. The library builder.
4. Ian starts the 3BP100 run, overnight.
5. The advisor lookup, then Gate L.

**Amendment to DECISIONS 40 (2026-11-16), while building the library and
before any library run.**
- **Coverage order means per flop.** Flops are sorted by how many of the
  22,100 dealt flops each one stands for, most first. Ties are broken by a
  shuffle with seed 20261116.

  | Weight | Flops |
  |---|---|
  | 24 | the 286 rainbow flops |
  | 12 | the 858 two-tone flops and the 312 paired flops, interleaved |
  | 4 | the 286 monotone flops and the 13 trips flops |

  The list above put paired flops with monotone ones. Per flop, though, a
  paired flop is dealt as often as a two-tone one, so this order maximises
  coverage for each flop solved.
- **Storage:**
  - one gzipped JSON file per flop, holding the four nodes;
  - a line in `manifest.jsonl` once that file is written;
  - hands are keyed as showdown writes them, high card first.

  A run resumes from the manifest. It refuses to mix bridge binaries in one
  spot's library.
- **Power:**
  - it checks AC power before every flop, not only at the start;
  - it asks Windows to keep the system awake while it runs.
- **A failed flop** (a bridge error or the 30-minute timeout) is logged and
  left out of the manifest, so the next run retries it.

---

### 41. Milestone 1: replay a saved heads-up hand, with advice at each hero decision from the real hand state; Gate R pre-registered (2026-11-16)

**Decided:** Ian asked for this on 2026-11-16, after a read-only audit of the
advisor. The audit found that `showdown advise` has no hand state. It is one
stateless call per decision, and `Spot` holds neither the action so far nor
the stack behind. So a river spot at 25 bb with 2.5 bb behind was told
"BET 33.75 bb". This is step 1 of the plan to live play. The live tracker
(step 2), range narrowing (step 3) and the preflop fix (step 4) each get
their own entries.

**Scope:** replaying saved hands and keeping recommendations legal. The
decision rules (DECISIONS 32, 35 and 36) do not change.
- **Not in scope:**
  - narrowing the opponent's range by the action;
  - the screen reader and the overlay;
  - hands with three or more players, which get "no suggestion".

**Hand state:** `src/showdown/live/hand.py`.
- **How it is built.** A PHH hand replays through pokerkit one operation at
  a time, as `hh/replay.py` does. pokerkit's seat order holds: player 0 is
  the BB, player 1 the SB.
- **Before every player decision it records:**
  - the street and the board;
  - the action history so far;
  - the pot (everything in the middle, including this street's bets);
  - the amount to call;
  - both players' remaining stacks;
  - the legal actions:
    - fold, only when facing a bet;
    - check or call, with the amount;
    - bet or raise, with pokerkit's smallest and largest raise-to.
- **After every action** it records the pot and both stacks, for
  reconciliation.
- **What it derives from the history,** which `showdown advise` makes Ian
  type:
  - **The preflop decision.** The voluntary preflop actions so far, written
    as `r` (a raise), `j` (a raise to at least the effective stack) and `c`
    (a call), map to DECISIONS 35's nodes:

    | Line so far | Decision |
    |---|---|
    | (nothing) | `sb_first` |
    | `r` | `bb_vs_raise` |
    | `rr` | `sb_vs_3bet` |
    | `rrj` | `bb_vs_4bet_jam` |
    | `rj` | `sb_vs_jam` |
    | `j` | `bb_vs_jam` |
    | anything else, such as a limp | `other`, which gives no suggestion |

  - **The pot type after the flop:**
    - `rc` is `srp`;
    - `rrc` is `3bp`;
    - any other line uses the closer of the two, with a printed note: a
      limped pot uses `srp`, a 4-bet pot uses `3bp`.
- **Heads-up only.** A hand with more than two players dealt in raises an
  error naming the count.

**`Spot` and `Advisor`:** reused, not rewritten.
- **`Spot` gains three optional fields:**
  - `history`, the action lines;
  - `stack_behind_bb`, the hero's remaining stack;
  - `legal`, the legal actions.

  With these unset, every `showdown advise` output is unchanged.
- **`Advisor.suggest` ends with a legal-action check whenever `legal` is
  set:**
  - It never shows an action that isn't legal:
    - "fold" with nothing to call becomes "check";
    - a bet or raise with no raise allowed becomes "call" when facing a bet,
      or "check" otherwise.
  - Bet and raise sizes are raise-to amounts, as pokerkit's are.
  - Each size is held within pokerkit's smallest and largest raise-to. It is
    also capped at the most the opponent can match: their bet plus their
    stack.
  - A size that reaches that cap is shown as "all-in N bb". A "jam" gets its
    size.
  - It adds a note when it changes anything, and when a call puts the hero
    all-in.

**Command:** `showdown replay HAND.phh --hero sb|bb`.
- At each hero decision it prints:
  - the street and the history;
  - the pot, the amount to call, and both stacks;
  - the legal actions;
  - the advice, as `showdown advise` prints it;
  - any notes.
- `--trace` also prints what reaches the equity calculation: the opponent
  range's label, its number of combos, its total weight, and a fingerprint
  of its combos and weights.

**Saved hands:** in `tests/fixtures/live/hands/`, written by hand, with
blinds of 5 and 10 chips (0.1 bb a chip):
1. `hu_full_hand.phh`: 50 bb, hero SB with AhKd, a hero decision on every
   street, and the river facing a third-of-pot bet.
2. `hu_river_shove.phh`: the same hand to the river, where the BB shoves
   instead.
3. `hu_short_stack_river.phh`: the audit's spot. 25 bb, KhKs, 22.5 bb each in
   by the river, and the BB checks to the hero with 2.5 bb behind.

**Gate R:**
1. **A full hand.** `hu_full_hand.phh` replays from preflop to the river. Each
   of the hero's decisions (at least one on every street) has a state and a
   suggestion.
2. **Reconciliation.** After every player action in every saved hand, and in
   every simulated hand of bar 3:
   - pot plus both stacks equals the starting chips;
   - the pot and the stacks equal an independent tally from the PHH action
     list, to 1e-9 bb.
3. **Legality.** 500 seeded heads-up hands are simulated by pokerkit with
   random legal actions:
   - effective stacks from 10 to 100 bb;
   - cards dealt from a seeded shuffle;
   - sizes drawn between pokerkit's minimum and maximum.

   They are replayed, and every decision is advised for the player to act.
   - Every suggestion must be a legal action.
   - Every bet or raise size must lie within pokerkit's minimum and maximum.
   - None may exceed the opponent's bet plus their stack.

   The flop's Monte Carlo sample count may be lowered for speed, since it
   does not affect legality. This bar runs in the slow suite.
4. **Regression.** In `hu_short_stack_river.phh`, the river suggestion is
   "all-in 2.5 bb" or "check". No size above 2.5 bb appears.
5. **Nothing else moves.** Every Gate G, J and P test, with its fixture,
   passes unchanged.

**Reported, not gated:** `showdown replay --trace` on
`hu_full_hand.phh` and `hu_river_shove.phh`. It shows what each river
decision knows, and whether the two lines reach the equity calculation with
the same range. Until range narrowing (step 3) exists, they will, and the
record says so.

**Rules out:**
- Changing any decision rule or threshold.
- Inferring anything from a hand with three or more players.
- Moving any bar after results are seen, except by a dated amendment.

---

### 42. Step 2: the live tracker and the overlay, from table frames; Gate T pre-registered (2026-11-16)

**Decided:** step 2 of the plan to live play, which Ian set on 2026-11-16 and
told to continue. The screen reader (S1) still waits for Ian's screenshots.
So this step fixes what the reader must deliver, as a contract, and builds
everything downstream of it. That is the tracker, the overlay, and a replay
of recorded frames. It uses DECISIONS 41's hand state and legal-action check
unchanged.

**The frame contract,** `src/showdown/live/table.py`. A `TableState` is one
read of the table:
- **Per seat:**
  - the player's name;
  - the stack behind and the bet in front this street, in chips;
  - whether the player still holds cards;
  - their hole cards, when visible. Ian's are always visible; others' only
    at a showdown.
- **For the table:**
  - which seat is Ian's;
  - the button seat;
  - whose turn it is, or none;
  - the board;
  - the big blind in chips (from the game's settings);
  - `ended`: the hand's result is showing, so the stacks are final.
- **Optional:** the pot as shown. When present, it is checked against the
  tracker's own count, and a mismatch is reported as a reading error.

This amends S1 (`docs/plan-live-advisor.md`, Phase 8). S1 must also read
names, who still holds cards, shown cards, and the end-of-hand frame. Its
bars are unchanged.

**The tracker,** `src/showdown/live/tracker.py`. It takes frames one by one.
- **A new hand** starts when Ian's cards change, or when the board empties
  after it held cards.
- **With more than two players dealt in,** it gives "no suggestion: N
  players dealt in" and ignores the hand.
- **For a heads-up hand** it keeps a pokerkit state:
  - Ian's cards are dealt; the opponent's are unknown until shown;
  - the button is the SB.
- **Between frames** it searches for the shortest sequence of legal actions
  that turns the last state into one matching the new frame. The new frame's
  board supplies the cards dealt.
  - A raise-to amount is taken from the frame: the raiser's bet in front, or,
    after the street has closed, their total for that street.
  - A frame that no legal sequence of up to six actions explains is reported
    as a reading error. The hand is then abandoned, with no suggestion.
- **At each of Ian's turns** it builds DECISIONS 41's `Decision` from its
  pokerkit state, and asks `Advisor.suggest`.
- **At the end frame** it writes the hand as PHH to `data/live/hands/`, which
  is gitignored.
  - **If Ian bet and the opponent folded** with no frame between, the bet's
    size cannot be read. The final stacks do not depend on it. Such a bet is
    written at the smallest legal size, with a comment saying so.

**The overlay,** `src/showdown/live/overlay.py`:
- a small tkinter window, kept on top (`-topmost`) and visible to screen
  share;
- it shows the advice, the mix or EVs, the notes, the source, and the state
  line (street, pot, to call, stacks);
- it shows "no suggestion" with the reason when there is none.

**Command:** `showdown live --replay FRAMES.jsonl`, with one frame per
line.
- It feeds the frames to the tracker, prints each suggestion, and shows the
  overlay.
- With `--no-window`, it prints only.

This is the demo and test path until the reader exists.

**Gate T.** The test hands are 200 heads-up hands from Gate R's simulator,
seed 20261117, written as frames from the SB's view or the BB's, alternating
by hand.
1. **Hero-turn frames.** Given only a frame at each of Ian's turns, plus the
   end frame, the tracker's `Decision` at every one of Ian's turns equals
   step 1's replay of the same hand. That covers the street, board, history,
   pot, amount to call, stacks, bets, legal actions and preflop line, to
   1e-9 bb.
2. **Every-change frames.** Given a frame after every action and every card
   dealt:
   - the tracker's betting actions and board cards equal the hand's own.
     Show and muck lines are excluded: whether Ian shows a losing hand never
     changes the result;
   - its PHH replays through `hh/parse` and reconciles.
3. **Minimal frames.** For the hands in bar 1, every written PHH reconciles.
   Bets written at an unseen size are counted and reported.
4. **3+ handed.** 20 frames from three-handed hands give "no suggestion"
   and write no PHH.
5. **Latency.** From a frame arriving to a suggestion, the 95th percentile
   is at most 300 ms, by DECISIONS 32's method: a separate process, no
   coverage.
6. **The overlay.** A test opens the window, shows one suggestion and one
   "no suggestion", reads the labels back, and closes it.

**Rules out:**
- Reading the screen. That is S1 and Phase 10, which wait for Ian's
  screenshots.
- Clicking anything.
- Hiding the window from screen share.
- Changing any decision rule.
- Moving any bar after results are seen, except by a dated amendment.

**Amendment to DECISIONS 42 (2026-11-17), after Gate T's first evidence run
failed and before the second.**
- **The failures:**
  - **bar 2:** chip counts were written as `68.0`;
  - **bar 5:** 306 ms, but measured while another full-suite run was going,
    so the measurement was invalid.
- **A sweep of the 200 hands then showed tracker bugs.** Each was reproduced
  on a named hand and fixed. Four of them change how the tracker reads
  frames, so they are recorded here:
  - **Bets are swept into the pot only when the frame shows it.** The table
    can show a closed street's bets for a moment, as after an all-in call
    before the uncalled part comes back. pokerkit's automatic bet collection
    is therefore off in the tracker.
  - **The search's pruning:**
    - a player's chips outside the pot (stack plus bet) never rise, since an
      uncalled bet goes back to the stack;
    - an open street's bets never fall.
  - **Showing:**
    - the opponent's cards are shown as soon as a frame shows them;
    - Ian's, always on his screen, and any muck, wait for the run-out or the
      result;
    - pokerkit needs both hands shown before it deals an all-in run-out.
  - **A second kind of unseen size.** A raise called all-in for less than a
    legal raise is written at the smallest legal size and counted as unseen.
    The excess came back, so its real size cannot be read.

  The other two fixes are implementation details: whole chip counts are kept
  whole, and the search's pruning is the rule above.
- **No bar changed.**

---

### 43. The portfolio site shows exported push/fold results, not a port (2026-11-17)

**Decided:** Ian's portfolio site (`ian-menachery/site`) has a push/fold
explorer and trainer built from a one-time export. The site's
`scripts/export_pushfold.py` calls this repo's own code
(`PushFoldSolution.load`, `sb_action_values`, `bb_action_values`,
`PushFoldStrategy.grade`, `depth_for`) and writes each depth's push and call
frequencies and action EVs to JSON. The page only looks those numbers up and
subtracts. Its tests check 122 cases graded by `PushFoldStrategy.grade`, within
1e-6.

**Why:** DECISIONS 12 keeps game logic in Python so that what a page shows is
what the gates test. Publishing the gated solution as data keeps that true
without hosting this program. Ian chose this over a JavaScript port.

**Rules out:**
- Porting the solver, the EV formulas or the bot to JavaScript.
- Hosting `showdown play` anywhere.
- Putting anything on the site beyond push/fold at 1–20 bb.
- Any HoldemResources data on the site.

DECISIONS 12 is otherwise unchanged.

---

### 44. Spike S2b: live turn and river solves, and Gate S2b pre-registered (2026-11-17)

**Decided:** step 3 of the plan to live play (range narrowing), part 3b. Ian
set the bars on 2026-11-16. The plan doc called this entry DECISIONS 43, but
43 went to the portfolio site, so the preflop re-solve and the opponent model
move to 45 and 46.

**Why.** Postflop, `advisor.villain` passes the opponent's whole preflop range
to `range_vs_range`, whatever the betting. Gate R's river trace showed a
third-pot bet and a shove reaching it with the same range (c70a1aad9e1e) and
the same 92.2%. Narrowing the range needs the opponent's strategy along the
line. The flop library (DECISIONS 40) gives the flop's; S2b measures whether
the turn and river can be solved live, from ranges narrowed by the flop line.

**The engine** is DECISIONS 40's: postflop-solver at 9d1509f, Rust 1.100.0
(gnu), only `rayon`, `-A dangerous_implicit_autorefs`.

**A second bridge binary:** `bridges/postflop/src/bin/streets.rs`, AGPL-3.0-or-later
like the first.
- `showdown postflop build` builds it beside the first, since cargo builds
  every binary in the package.
- `src/main.rs` does not change. After the build, the spike checks that the
  first binary's SHA-256 is still c45af752…, so Gate X's cache and the
  library's one-binary rule still hold. If it changed, the spike stops before
  any solve and says so.
- **Input:** one JSON spot:
  - each player's range as 1,326 raw weights in the solver's combo order
    (`Range::from_raw_data`);
  - a board of 4 cards (a turn start) or 5 (a river start);
  - the pot and the stack in chips (0.1 bb);
  - T1's turn and river sizes;
  - optionally, the OOP's own turn bet sizes;
  - the target, the iteration cap, and the paths to report.
- **Output:** what the first binary gives, without locks: build and solve
  times, iterations, exploitability, memory, root EVs, and each reported
  node's per-hand strategy, weights and equity.

**The grid.**
- **Spots:** 3BP100 and SRP50, with the preflop model's ranges at 100 and
  50 bb (DECISIONS 40's `rrc` and `rc` lines). Flop pots of 15 and 5 bb;
  stacks behind of 92.5 and 47.5 bb.
- **Boards:** 10 per spot. Each is five cards dealt from a deck shuffled with
  seed 20261117 (one shuffle per board, 3BP100's ten first). The flop is put
  in the library's canonical suits (`flops.canonical`), and the turn and river
  are relabelled with the same suit map.
- **Each board gives two timed solves:** a turn start (flop and turn) and a
  river start (all five cards). That is 40 solves: 20 turn, 20 river.
- **Flop lines,** in turn by board (board *i* takes line *i* mod 3):
  1. check-check;
  2. bet-call: the OOP bets 33%, the IP calls;
  3. check-bet-call: the OOP checks, the IP bets 33%, the OOP calls.

  If either player's narrowed range weighs less than 5 combos, the board
  takes the next line, and the report says so.
- **The river starts** assume the turn checked through. The river then starts
  with the flop line's pot, and with ranges narrowed by the flop line only.
  Any turn action would narrow the ranges further and grow the pot, so this is
  the widest, deepest river after each flop line: the slow case.

**Narrowing.** Each combo's weight is its preflop weight times its frequency
of each action on the flop line.
- **The preflop weight** is its class's weight in the model range the flop
  solve used: `spot.model_range`, with its rounding.
- **The frequencies** come from the library's four stored nodes, as whole
  percentages.
  - A flop already in the library is read with `library.load`.
  - Otherwise (the library is empty today) the spike solves the flop itself,
    with the library's exact spec (`FlopSpot.spec(report=NODES)`) and the
    first binary, and builds the entry with `library.entry`. These solves are
    cached in the gitignored `data/external/postflop-solver/cache/s2b`, are
    not timed, and are not written to `data/library/`.
- **The bet** on a line is the node's smallest bet (33%), never the all-in.
  The pot and stack after the line use that bet's chip amount.

**The tree** is T1's turn and river:

| Street | Bets | Raises |
|---|---|---|
| turn | "66%, a" | "60%, a" |
| river | "75%, a" | "60%, a" |

- River donk "75%". The all-in thresholds are DECISIONS 38's (1.5, 0.15,
  0.1).
- **After check-bet-call,** the OOP gets no turn bet sizes. In T1's flop tree
  the OOP has no turn lead after calling a flop bet (the empty turn donk
  list), but keeps the all-in when the threshold adds it. An empty OOP turn
  bet list gives the same subtree.

**Settings.**
- All 16 threads (rayon's default) and 32-bit storage, compressed only if a
  tree needs more than 10 GB.
- The target is 2% of the street's starting pot, at most 1,000 iterations.
  Exploitability is checked every 10 iterations, as the first binary does.
- **Timing.** Wall time in Python, from process start to the parsed result,
  so it includes building the tree and allocating memory. The timed solves
  run one at a time, after every flop solve is done, with no other solver or
  test run on the laptop. The order is 3BP100's boards, then SRP50's; each
  board's turn, then its river.
- **Timeout:** 120 s. A timeout counts as 120 s and fails bar 3.

**Gate S2b:**
1. **River:** the median wall time is at most 3 s. The 95th percentile is at
   most 6 s and at most double the measured median.
2. **Turn:** the median is at most 15 s. The 95th percentile is at most 30 s
   and at most double the measured median.
3. **Accuracy:** every one of the 40 solves ends with exploitability at most
   2% of its starting pot.

The 95th percentile is numpy's linear one, as in S4. Ian's bar is "the 95th
percentile at most double". S2 and S4 doubled the median bar; read against the
measured median it is stricter. Both readings must hold. All 40 solves run,
with no early stop.

**Reported, not gated:**
- times, iterations and memory by spot, street and flop line;
- each player's combos and total weight, before and after narrowing.

**What follows from the result.**
- **If S2b passes,** Ian chooses how the solves feed `advisor.villain` and the
  postflop actions (step 3c). That gets its own entry and gate.
- **If it fails,** the failure is recorded, and the stopgap proposed to Ian is
  a labelled range model that narrows by the line and the bet size.

**Rules out:**
- Changing the grid, the tree, the narrowing, the settings or the bars after
  the first timed solve.
- Changing `bridges/postflop/src/main.rs`.
- Starting a library run, or writing to `data/library/`.
- Any download.

---

### 45. Spike S2c: S2b again on new boards, with absolute tail bars; Gate S2c pre-registered (2026-11-18)

**Decided:** Ian chose this on 2026-11-18, after Gate S2b failed on one
reading of one bar. DECISIONS 44 required each street's 95th percentile to be
within double the median bar and within double the measured median. The turn
passed the first (0.90 s against 30 s) and failed the second (0.90 s against
0.60 s). S2b stays a FAIL in GATES.md. S2c is a new run with new boards, not
a rerun of S2b's.

**Everything is DECISIONS 44's** except:
- **The seed is 20261118.** It draws 10 new boards per spot, the same way.
- **The tail bars are absolute only:** the 95th percentile is at most 6 s on
  the river and at most 30 s on the turn. The ratio to the measured median is
  reported, not gated.
- **The flop solves** are cached beside S2b's, under the same spec and the
  same flop binary.

**Gate S2c:**
1. **River:** the median is at most 3 s; the 95th percentile at most 6 s.
2. **Turn:** the median is at most 15 s; the 95th percentile at most 30 s.
3. **Accuracy:** every one of the 40 solves ends with exploitability at most
   2% of its starting pot.

**What follows.** If S2c passes, step 3c (wiring live solves into
`advisor.villain` and the postflop actions) can be planned on it. That gets
its own entry and gate. Either way, the stopgap range model (DECISIONS 46)
goes ahead. Ian chose that too.

The preflop re-solve and the opponent model move to DECISIONS 47 and 48, or
the next free numbers.

**Rules out:** what DECISIONS 44 rules out, and changing any of S2c's bars
after its first timed solve.

---

### 46. The stopgap range model: the villain's range narrowed by its moves, with curves fitted to the solver; Gate N pre-registered (2026-11-18)

**Decided:** Ian chose this on 2026-11-18, after Gate S2b, as the stopgap
DECISIONS 44 names. He ticked each piece:
- narrowing by the villain's moves;
- equity against a random hand as the strength measure;
- soft weights;
- the bet and call rules fitted to the solver, not set by formula;
- two bars.

It works without the flop library. Step 3c (DECISIONS 45) can replace it with
live solves where those exist.

**Where it applies.** `advisor.villain` narrows the range when the spot has a
history with at least one postflop move by the villain, and the range is not
Ian's own (`--villain` or `--villain-top`).
- Typed `showdown advise` spots have no history, so they do not change.
- The label says "range model (assumed, not solved)", the number of villain
  moves used, and "fitted to S2b/S2c solves".

**Strength.** Each combo's equity against a random hand on that street's
board. Card removal between the two hands is ignored.
- **On a full five-card runout,** a combo's score is the share of the other
  live combos it beats, counting ties as half. Live combos are those that
  don't touch the runout.
- **The score is averaged over runouts:**
  - on the river, the board itself;
  - on the turn, every river card that touches neither the board nor the
    combo;
  - on the flop, 45 (turn, river) pairs, drawn once per board with
    `random.Random(<board string>)`. Each combo averages over the pairs it
    doesn't touch.

  Each board's scores are computed once and cached.
- **A combo's percentile** within the villain's current weighted range is
  (weight scoring below it + half the weight scoring equal) / total weight.
- **Its band** is the percentile's decile, 0 to 9.

**Narrowing.** The villain's postflop moves are read from the history in
order, and each one multiplies every combo's weight by a multiplier for its
band. The hero's moves narrow nothing.
- **Each move gets a node:**
  - `first`: the villain acts first on the street;
  - `after_check`: the villain acts after a check;
  - `facing_bet`: the villain faces a bet or a raise;
  - `facing_allin`: the villain faces an all-in.
- **Its position** is OOP for the BB and IP for the SB.
- **The size** of a bet is f = bet / pot. For a raise,
  f = (raise − to call) / (pot + to call). The pot is rebuilt from the
  history, starting from the blinds.
- **The curve** comes from `data/range_model.json`, keyed by pot type, street,
  position, node and action:
  - a check uses the Check curve;
  - a bet interpolates between the Bet and AllIn curves, linearly in f between
    their mean sizes and clamped outside them;
  - a raise does the same between Raise and AllIn;
  - a call interpolates between the `facing_bet` and `facing_allin` Call
    curves, by the size faced.
- **Each curve's shape** is its per-band frequency divided by its largest
  band's.
- **The multiplier** is max(shape, floor):
  - the floor is 0.25 for a check, so traps keep a quarter;
  - otherwise it is 0.10, since friends mix and misplay.
- **With no curve,** the move narrows nothing, and the label says so.
- **The pot type** (srp or 3bp) picks the curves. They are fitted at 50 bb
  and 100 bb, and used at every depth.

**The fit:** `showdown postflop fit-ranges` writes `data/range_model.json`,
run once.
- **The flops** are S2b's and S2c's 40, 20 per pot type. Their curves come
  from the cached flop entries' four nodes. Reach weights come from the
  preflop weights and the strategy before the node.
- **The turns and rivers:**
  - for each flop and each flop line that leaves at least 5 combos to both
    players, 2 turn cards, and one river after each;
  - drawn with seed 20261119, one shuffle per (flop, line);
  - started as S2b's spots were: narrowed by the flop line, with the turn
    checked through for the river starts;
  - at most 480 solves with the streets binary, tree T1 and the 2% target.

  Each reports six nodes: `[]`, `[Check]`, `[Bet]`, `[Check, Bet]`,
  `[AllIn]` and `[Check, AllIn]`. On the flop there is no facing-all-in
  node, so those moves use the turn's curves.
- **Each band's frequency** for each action is the reach-weighted mean over
  that key's nodes. Each action's mean f is recorded beside it.
- **The file holds frequencies,** which are solver output, not solver code.
  It is small and committed. The fit is our code, and runs the AGPL bridge as
  a separate process.

**Gate N:**
1. **Gate R's trace differs.** In `hu_full_hand.phh` (a third-pot river bet)
   and `hu_river_shove.phh` (a shove), the river decision reaches the equity
   calculation with different ranges: different fingerprints. The report
   shows both ranges and both equities.
2. **Hand-worked weights.** On at least 5 hand-built spots with small ranges
   and a small curve table written in the test, the model's weights equal a
   hand calculation of the rules above, to 1e-9.

**Reported, not gated:**
- a summary of the fitted curves;
- latency, by DECISIONS 32's method;
- every change to the replay and live advice in Gate R's and Gate T's hands.

`test_the_river_lines_differ_only_in_the_bet` asserted the same range for
both lines ("step 3 is not built"). That assertion is replaced by bar 1.

**Rules out:**
- Changing the rules, floors, bands, fit set or seeds after the fit's first
  solve, or after Gate R's trace is seen.
- Narrowing a range Ian gave.
- Any download, a library run, or writing to `data/library/`.

---

### 47. Step 3c: live turn and river solves in the advice; playstyle marking goes to step 5; Gate V pre-registered (2026-11-18)

**Decided:** Ian picked the pieces and the four bars on 2026-11-18 (plan doc,
Phase 13, "Step 3c"), after Gate S2c showed turn solves take about 1 s and
river solves about 0.05 s. The preflop re-solve and the opponent model move to
DECISIONS 48 and 49.

**Playstyle marking goes to step 5, not 3c.** Ian's picks, 2026-11-18:
- **Labels:** Nit, TAG, LAG and Station. An unmarked villain keeps the model's
  ranges.
- **Effects:** all four he was offered. The label is shown and logged with
  each hand, it sets the width of the villain's preflop range, it locks nodes
  in the live solves (as Gate X does on the flop), and it tilts the stopgap's
  curves.
- **Input:** buttons on the overlay.

Step 5's entry designs and gates it. 3c builds none of it. Locks in live solves
would need lock support in `streets.rs`.

**Where a live solve answers.** At a turn or river decision, when all of these
hold:
- the spot comes from a replay or the tracker, so it has a history;
- the preflop line is an open and a call (`rc`) or a 3-bet and a call
  (`rrc`), the model's two pot lines;
- the model reaches that pot at the nearest depth for both seats (DECISIONS
  35's 0.1% rule);
- `--ranges model`, and Ian gave no range;
- the streets binary is built.

Otherwise the equity helper answers against the stopgap's range, as now. On the
turn and river of a spot with a history, its source then adds "no live solve:"
and the reason. Typed `showdown advise` spots and flop spots do not change.

**The solve's inputs:**
- **Board:** the street's cards.
- **Pot and stack:** the hand's real ones, rebuilt from the history. The pot is
  everything in the middle when the street starts. The stack is the effective
  stack (the smaller starting stack) less what each player has put in. Both
  are in chips of 0.1 bb, rounded.
- **Ranges:** each seat's model weights along the pot's line at the nearest
  depth (the advisor's `model_range`), narrowed by every earlier street:
  - **the flop:** the stopgap's curves (DECISIONS 46) narrow both players, each
    by its own flop moves, labelled "range model (assumed)". The flop library
    is empty and its lookup is Gate L's, so 3c reads no library entry;
  - **the turn,** for a river solve: the turn solve's per-hand frequency of
    each move along the line. If the turn has no solve, or its line left the
    tree, the stopgap's turn curves narrow instead, labelled.
- **Ian's hand** gets at least 0.001 of weight in his own range, so the solver
  always gives it a strategy.
- **The tree** is T1's turn and river sizes for both players. The OOP keeps its
  turn bets after every flop line, because a real BB can lead; S2b took them
  away after check-bet-call. River donk 75%; DECISIONS 38's all-in thresholds.
- **Settings:** S2b's: all 16 threads, a target of 2% of the street's starting
  pot, at most 1,000 iterations.
- **Timeouts:** 6 s on the turn and 3 s on the river, twice bar 4's limits. A
  river solve that must first run its turn solve gets both.
- **No range under 1 combo:** if either range weighs less than one combo at
  the start of a street, nothing is solved there.

**When it starts.** The tracker starts a solve in a background thread on the
frame that first shows the turn or river card. In a replay, or with frames only
at Ian's turns, it starts at Ian's first decision on that street. Solves are
cached by their inputs.

**The node.** The street's moves so far are mapped onto the tree, in order.
- **Checks and calls** map to themselves.
- **A bet or raise** maps to the node's Bet, Raise or AllIn whose size is
  nearest. Size is DECISIONS 46's f: bet / pot, or for a raise
  (raise − to call) / (pot + to call). An all-in maps to AllIn.
- **Off-tree sizes** get a note: "BB's turn bet of 4 bb (25% of the pot) solved
  as the tree's 66% bet". Ian chose this over adding the size and re-solving.
- **A move with nothing to map to** means the line has left the tree. Nothing
  is solved for the rest of that street; the fallback answers.
- **The binary is unchanged** (`streets.exe`, SHA-256 ef5ab1cf…). Each solve
  asks it for every decision node on its street: Check, Bet or AllIn first;
  after a check, Bet or AllIn; after a bet or raise, Raise or AllIn; at most
  8 moves. Paths the tree lacks come back unreached.

**The villain's range** at the node is its street-start range times its
per-hand frequency of each of its own moves along the line. Ian's moves narrow
his range the same way, for the next street. These replace the stopgap's
curves on solved streets. The advice shows exact equity against that range, for
reference only.

**Ian's action** is his hand's row at the node: the most likely action (ties go
to the earlier one), with the mix.
- **A bet or raise keeps the tree's f,** applied to the real pot by the same
  formulas. Where nothing was mapped, that is the tree's own size.
- **An all-in stays all-in.**
- **Then DECISIONS 41's legality rule,** unchanged. It notes anything it
  changes.

**Labels.**
- The source says "live solve", the street, the solve time and the
  exploitability.
- The range label names how each street was narrowed: "range model (assumed)"
  or "solved".

**Latency and the overlay.** While a solve Ian needs is still running, the
tracker sends a "solving…" event first; the overlay shows it and then the
answer. DECISIONS 32's 300 ms bar keeps covering equity-helper answers. Solver
answers get bar 4.

**Gate V:**
1. **Gate R's two river hands, with solver-narrowed ranges.** In
   `hu_full_hand.phh` (a third-pot river bet) and `hu_river_shove.phh` (a
   shove), the SB's river decision is answered by a live solve. The villain's
   ranges at the node differ (different fingerprints). `showdown replay
   --trace` shows both ranges and both answers.
2. **Legal over 500 hands.** Gate R bar 3's 500 simulated hands (seed
   20261116), advised for both players as there. Every suggestion from a live
   solve is a legal action. Its size is within pokerkit's limits and within
   the opponent's bet plus stack. Fewer than 100 solver answers means the bar
   is not measured, which is a FAIL.
3. **The bridge's own strategy.** The first 40 decisions answered by a live
   solve in bar 2's hands, in hand order. For each, the test runs the streets
   binary itself on the spec the advisor sent, reports the node the advisor
   read, and takes the row of the deciding player's hand. The advice's mix
   equals that row for every action, to 1e-6. Its action is the row's most
   likely action, unless DECISIONS 41's legality rule changed it, which its
   note then says. Three runs of one turn spec gave bit-identical strategies,
   so a second run is a fair reference.
4. **Latency.** Bar 2's 500 hands as every-change frames through the tracker.
   Ian is the SB in even hands and the BB in odd ones. The run is a separate
   process, without coverage, on an idle laptop (DECISIONS 32), with the flop's
   full 20,000 samples.
   - **The time** is from feeding the frame that first shows the street's card
     to the answer, for each of Ian's turn and river decisions where a live
     solve was started. Timeouts and failures count at their full time.
   - **The bars:** turn 95th percentile ≤ 3 s, river ≤ 1 s, numpy's linear
     percentile.
   - **The sample:** at least 30 per street, or the bar is not measured, which
     is a FAIL.

**Existing tests that change, decided here:**
- **Gate T bar 5** (300 ms) covers equity-helper answers only (plan item 7).
- **Gate T bar 6's overlay test** uses an advisor with live solves off. It
  tests the window, and its recorded text stays.
- **`showdown replay --trace`** prints the range the advice used: the solved
  one where a solve answered. Gate N's bar 1 test, which calls
  `advisor.villain`, still reads the stopgap's range.

**Reported, not gated:**
- solver answers against fallbacks, by reason; legality fixes; off-tree
  mappings;
- how the advice changed from the stopgap in Gate R's and Gate T's hands, such
  as raises and bluffs;
- solve times by street;
- Gate T's 300 ms bar, over equity-helper answers.

**Rules out:**
- changing the bars, the tree, the settings, the timeouts, the floor or the
  samples after the first evidence run;
- changing either bridge binary;
- reading or writing `data/library/`, a library run, or any download;
- playstyle code (step 5).

**Amendment (2026-11-19): a floor on solver narrowing; Gate V bar 5
pre-registered.** Ian chose this after Gate V passed. Its reading showed the
problem. In `hu_full_hand.phh` the solved BB checks the turn 98.9% of the time,
so its real turn lead left 1.9 combos of weight, and 0.38 by the river.
- **The rule.** On a solved street, each move multiplies the mover's hands by
  max(the solver's frequency for that move, the floor), where it was the
  frequency alone.
- **The floor** is DECISIONS 46's: 0.25 for a check, so traps keep a quarter,
  and 0.10 for any other move.
- **Both players get it:**
  - the villain, in its range at Ian's node and in the next street's solve;
  - Ian, in his own range in the next street's solve.
- **Only hands in the node's range get the floor.** Hands the solver does not
  report (no weight, or touching the board) stay at 0.
- **Ian's action on the current street does not change:** it still comes from
  the solve as it is. An off-strategy lead can't be re-weighted inside a solve
  without solving again.

**Gate V bar 5: hand-worked floors.** At least 5 hand-built walks over small
hand-made nodes. The multipliers and the narrowed weights equal a hand
calculation of the rule above, to 1e-9. The walks cover:
- a check below the 0.25 floor, and one above it;
- a bet below the 0.10 floor;
- a call;
- an off-tree raise mapped to the tree;
- both players' multipliers on one line;
- a hand outside the node's range, which stays at 0.

**What stays.** Gate V's first run stays the record for bars 1 to 4; Ian chose
not to re-measure them. Gate R's river trace is reported again, not gated.

**Rules out** changing the floors or bar 5 after its first run.

---

### 48. Heads-up push/fold with a 10% ante, for the site's chart; Gate PA pre-registered (2026-11-19)

**Decided.** Ian chose this on 2026-11-19, after the portfolio site session
handed over his request for more push/fold settings.
- **What he picked:** heads-up with an ante, at 10% of the big blind, with
  three checks (below).
- **What he did not pick:** 3+ players (a new 3-way equity table and a
  3-player game), and ICM. Heads-up, tournament equity is linear in chips, so
  a heads-up tournament plays as chip EV. A tournament differs only by its
  ante, which this covers.

**The game.** It is the push/fold game of DECISIONS 8 and 22 with one change:
each player posts an ante of 0.1 bb.
- **S** is the effective stack before the blinds and antes are posted.
- **The SB folds:** it loses 0.6.
- **The BB folds to the jam:** the SB wins 1.1.
- **The BB calls:** both are all-in for S, and the SB nets S·(2E − 1), as
  before.
- **Chip EV.**

The ante is a parameter, 0 by default, of the push/fold game, the solve and
the closed forms in `pushfold.py`. The solver is the same: `cfr_plus`, 1,000
iterations at each of 1 to 20 bb, average policy, the exact matrix.

**Gate PA,** recorded before the solve:
1. **Exploitability:** at most 1e-5 bb at every depth from 1 to 20 bb, ante
   0.1, by our best response on the compiled tree.
2. **Ante 0 reproduces today:**
   - all 20 depths re-solved with the ante set to 0;
   - push, call, exploitability and SB value equal `data/pushfold.json`
     exactly.
3. **HoldemResources, "Ante 10%."** The reference is the "Ante 10%" pusher
   and caller charts on HoldemResources' heads-up Nash page.
   - **The file:** `data/external/holdemresources/hune.html`, 35,053 bytes,
     SHA-256 `432658557afbb34c97db823daeb627cfa5d7e316ba29ccbdece6ff7607196d87`.
     It was saved on 2026-11-19 with Ian's approval, is gitignored, and is
     never committed.
   - **The chart:** per class, the largest effective stack at which it pushes
     or calls. The resolution is 0.1 bb, capped at "20+".
   - **The comparison:**
     - at depth d, the chart pushes (or calls) a class when its value is at
       least d;
     - a class is excluded when we mix it (0.01 < p < 0.99), or when its
       chart value is within 0.1 bb of d;
     - at least 95% of compared classes must agree at every depth, for the
       pusher and the caller, as in Gate D;
     - more than 17 exclusions at a depth is reported as a finding;
     - every disagreement is listed.
   - **Not stated by the page:** whether 10% means 0.1 bb per player, or how
     its stacks count the ante. Our convention is above. A failure here may
     mean the conventions differ; it is recorded as a FAIL all the same.
4. **Closed forms.** With the ante:
   - the tree's value and exploitability equal the closed-form sums to 1e-12,
     on random and pure strategies;
   - the action values give fold EVs of −0.6 (SB) and −1.1 (BB).
5. **The export.** `data/pushfold_ante10.json` has `data/pushfold.json`'s
   format plus `"ante": 0.1`. `PushFoldSolution.load` reads the ante, with 0
   for files that lack it. The site's export reads it through
   `sb_action_values` and `bb_action_values` with `ante=`.

**Rules out:**
- 3+ player push/fold and ICM, which need their own decision.
- Calling it "GTO" on the site.
- Moving any bar after results are seen, except by a dated amendment.

**Amendment to DECISIONS 48 (2026-11-19, while coding, before any solve).**
No one loses more than their stack.
- At 1 bb with the 0.1 ante, the BB cannot post a 1 bb blind on top of its
  ante. Folding to the jam costs it its whole 1 bb, not 1.1.
- So both fold payoffs are capped at S: the SB's loss is min(0.6, S), and the
  BB's is min(1.1, S).
- This changes only the 1 bb game.
- With no ante the cap never binds, since S is at least 1. So bar 2 still
  compares like with like.

---

### 49. Step 4: the preflop re-solve, with a 4× 3-bet and R fitted to our flop solves; Gate Q pre-registered (2026-11-19)

**Decided:** Ian picked these on 2026-11-19. DECISIONS 48 went to the
push/fold ante, so the preflop re-solve is 49 and the opponent model 50. SCOPE
amendment A10 brings the second 3-bet size and the fitted R into scope.

**The problem (the 2026-11-16 audit).** The model leans on jams. A called
raise or 3-bet pays the BB only R of its equity, but a called all-in pays all
of it, so jamming dodges the discount. On the stored model at R 0.90:

| Depth | BB facing the open: fold / call / 3-bet / jam |
|---|---|
| 25 bb | 15 / 57 / 0 / 28% |
| 50 bb | 9 / 70 / 0 / 21% |
| 100 bb | 5 / 78 / 11 / 6% |

A share here, and in bar 3, is of the deals that reach the BB's decision at
the open: each BB class is weighted by its combos against the SB's opening
range.

**The tree.** DECISIONS 34's, with a second 3-bet size:
- SB first in: fold, raise to 2.5, or jam.
- BB facing the open: fold, call, 3-bet to 7.5 (3×), 3-bet to 10 (4×), or jam.
- SB facing either 3-bet: fold, call, or jam.
- Calls or folds against every jam.

Not added, by Ian's picks: a min-raise, a 3 bb open, a limp, and a 4-bet below
all-in.

**Payoffs.** DECISIONS 34's, except that R depends on the pot and the depth:
- a fold loses what the folder put in;
- a called all-in nets the SB S(2E − 1);
- a called raise or 3-bet, with c bb in from each player, nets the SB
  c(2·share − 1), with share = 1 − R(p, d)·(1 − E). The pot p is the open
  (c = 2.5), the 3× 3-bet (c = 7.5) or the 4× 3-bet (c = 10); d is the depth.
- R is used as measured, above 1 included: an out-of-position 3-bettor can
  realize more than its equity. The game rejects only R outside (0, 2), as a
  typo guard.

**Fitting R.**
- **What R is:** the share of its flop equity the BB, out of position, turns
  into EV once the flop is played. On one flop, R = EV_BB / (pot × E_BB):
  - EV_BB is the flop bridge's root EV for the BB (`root_ev[0]`, in chips);
  - E_BB is the BB's range equity at the root, from a report at the root path
    (its per-hand equity and weights);
  - the flop bridge's binary is unchanged (c45af752). If it cannot report the
    root, the build stops and asks Ian.

  A unit test checks the units on a check-down spot, where R must be 1. It is
  an ordinary test; Ian did not make it a bar.
- **The solves:** the flop bridge, tree T1, a 2% target, at most 1,000
  iterations (DECISIONS 40's settings). The ranges are each seat's model
  weights along the pot's line, as `model_range` gives them to the library.
  The pot is 2c and the stack d − c.
- **The cells:** the three pots at 25, 50 and 100 bb, 9 in all.
- **The flops:** 20, drawn uniformly without replacement from all 22,100
  flops with seed 20261119. The same 20 serve every cell and both rounds.
- **A cell's R** is the mean of its 20 per-flop values. Its standard error
  (sd / √20) is reported.
- **Unreached cells.** When the round's model reaches a cell's pot in under
  0.1% of deals (DECISIONS 35's rule), the cell is not measured. It takes the
  same pot's R from the nearest measured fit depth, or 0.90 if no depth
  measured that pot. The stored model labels it.
- **Between fit depths,** R is a straight line in depth: 30 and 40 bb from 25
  and 50; 60 to 90 bb from 50 and 100.
- **Two rounds:**
  1. the new tree solved at R 0.90 for every pot, at 25, 50 and 100 bb; R
     measured on those ranges;
  2. the new tree solved at round 1's R, at the same depths; R measured again.

  The product model uses round 2's R. The change between rounds is bar 4.

**The product solve.**
- **The grid and lookup** are DECISIONS 34's: 25, 30, 40, 50, 60, 70, 80, 90
  and 100 bb; the nearest depth, ties to the smaller; push/fold at 20 bb or
  less; 100 bb above 100.
- **Three solves per depth,** 27 in all: round 2's R, and every pot's R moved
  down 0.05 and up 0.05 together.
- **"Depends on R"** compares the −0.05 and +0.05 solves, as DECISIONS 34
  compared R 0.85 and 0.95.
- **Every solve,** the rounds' included: `cfr_plus`, exactly 1,000
  iterations, the average policy, the exact matrix. No early stopping, and no
  re-running until an answer matches.
- **Gate P's two 20 bb check solves are not repeated.** Ian did not keep the
  continuity bar.
- **Files.**
  - The old model is renamed `data/preflop_model_v1.json`, byte for byte.
  - The new one is `data/preflop_model.json`. It stores each cell's R, whether
    it was measured or a fallback, and the ±0.05 shift.
  - The fit's per-flop values go in a committed `data/preflop_r_fit.json`.
    The bridge outputs are cached under `data/external/`, which is gitignored.
- **Compute,** started only when Ian says so, on AC power. A rough estimate:
  about 3 h of flop solves per round, so 6 h for both, plus about 3 h of
  preflop solves.

**The switch.** Ian picked all three.
- **Preflop advice above 20 bb** comes from the new model.
  - The `--facing` names stay. `bb_vs_raise` has five actions: fold, call,
    3-bet 3×, 3-bet 4×, jam. Ties go to the earlier one, in that order. A
    suggested 3-bet is 3× or 4× the open faced.
  - **A faced 3-bet maps to a size.** Its ratio to the open it was made over
    (2.5 bb when a typed spot does not say) picks the nearer of 3× and 4×;
    3.5× goes to 3×. `bb_vs_4bet_jam` is placed the same way by the BB's own
    3-bet, read from the spot as the effective stack less the amount to call.
  - The size note is DECISIONS 35's, against the mapped size: "model assumes
    a 10 bb 3-bet; you face 9 bb".
  - The source reads "model chart, fitted R, D bb".
  - DECISIONS 35's 0.1% reach rule applies to every node, as before.
- **Postflop ranges.** The equity helper, the stopgap's starting ranges and
  the live turn and river solves (DECISIONS 47) take the new model's ranges.
  - A 3-bet pot picks its line by the same ratio rule.
  - A live solve's pot and stacks stay the hand's real ones.
  - The stopgap's fitted curves (`data/range_model.json`, Gate N) do not
    change.
- **The flop library** (still empty) uses the new ranges. Its 3BP100 spot
  uses the 3-bet size the new model's BB makes more often at 100 bb. Nothing
  is run here; Ian starts library runs.

**Gate Q: all seven bars must pass.**
1. **Exploitability:** at most 0.001 bb/hand at all 9 depths, for all three R
   sets, by `showdown.cfr.exploitability` on the compiled tree.
2. **Payoffs:** a separate closed-form function, written from this entry's
   rules and not from the game's code, gives every terminal payoff for every
   class pair. It matches every terminal utility in the compiled tree to
   1e-12, at 25 and 100 bb, for all three R sets.
3. **The jam lean at 50 bb.** With round 2's R, the BB jams over the open in at
   most 10% of the deals that reach that decision. It 3-bets, to 7.5 and to 10
   together, in at least 5%. Shares are as defined above.
4. **R settles.** Every cell measured in both rounds has its round-2 R within
   0.02 of round 1's.
   - Cells unmeasured in either round are listed with the R they got. They do
     not fail the bar.
   - Each of the three pots must be measured in both rounds at one fit depth
     at least, or the bar fails.
5. **Advisor spots** (Gate G extended, again). A new fixture of at least 30
   preflop spots above 20 bb. Each spot's depth, decision, action and R flag
   are written by hand from `showdown preflop chart` before the test runs.
   - At least 4 for each of the six decisions, at depths where the model
     reaches it.
   - For `sb_vs_3bet` and `bb_vs_4bet_jam`, at least 4 at each 3-bet size.
     At least 2 suggested BB 3-bets of each size. A size the model reaches at
     no depth is a FAIL, not a skip.
   - At least 2 spots face an off-model size, each with its note.
   - Every mix equals the stored model to 1e-12.
   - The 95th percentile time over the old and new spots is at most 300 ms,
     measured as DECISIONS 32 sets out.
6. **Live solves are legal.** Gate V bar 2's 500 simulated hands (seed
   20261116), advised for both players. Every live-solve answer is legal by
   Gate V bar 2's rule. At least 100 live-solve answers, at least 20 of them
   in 4× 3-bet pots; fewer is not measured, which is a FAIL.
7. **Live latency.** Gate V bar 4's method, on bar 6's hands:
   - every-change frames through the tracker, with Ian the SB in even hands
     and the BB in odd ones;
   - a separate process without coverage, on an idle laptop, with the flop's
     full 20,000 samples;
   - from feeding the frame that first shows the street's card to the
     answer; timeouts and failures count at their full time;
   - turn 95th percentile ≤ 3 s and river ≤ 1 s, numpy's linear percentile;
   - at least 30 per street, or the bar is not measured, which is a FAIL.

**Reported, not gated:**
- the jam lean at 100 bb;
- each cell's R, its standard error, and any fallbacks;
- every node's frequencies at every depth, beside the old model's;
- Gate R's three saved hands under the new model, and what changed;
- solve times.

Ian also did not pick reproducing the old model with the 4× size off, or a
gated check of the R measurement.

**Older tests, decided here.**
- **Pinned to `data/preflop_model_v1.json`,** because their expectations were
  written from the old model:
  - Gate P's tests, fast and slow;
  - Gate G extended's fixture (`model_spots.toml`);
  - Gate J's model answers;
  - Gate X's spots, so its cache still replays and X3 stays a strict xfail;
  - Gate N's and the range fit's tests, where they read model ranges.
- **Run on the new model, unchanged:** Gates R, T and V, whose bars check
  legality, tracker against replay, and solver rows, not old-model numbers;
  and Gate G's old fixture, which runs with `--ranges fixed`.
- **Any other test that fails after the switch** is reported to Ian, with the
  reason, before it changes. Nothing is re-baselined silently.

**Rules out:**
- changing the tree, the fit's cells, flops, seed or rounds, the iteration
  count or any bar after the first fit run, except by a dated amendment;
- changing either bridge binary;
- a library run;
- limps, min-raises, other opens, and 4-bets below all-in (SCOPE A7, A10);
- calling the model's answers Nash or GTO.

**Built, 2026-11-19, before any solve.** Two gaps in the spec, filled by Ian's picks:
- **A typed 3-bet pot** (`showdown advise --pot-type 3bp`, no history) takes the line of
  the 3-bet the BB makes more often at that depth, as the library does. `--threebet` (and
  `--open`, default 2.5) picks the line by the ratio rule instead. Replayed and tracked
  hands read both sizes from their moves.
- **Gate Q's evidence tests** sit in the slow suite and skip, saying why, until the fit or
  the product model exists. A skip is not a pass (DECISIONS 6).

**Amendment (2026-11-19), before the first fit run: bar 6's 4× count gets its own hands.**
Ian chose this after a count that needs no model: Gate V's 500 hands hold only 12 turn and
river decisions in 4× 3-bet pots (and 19 in 3× ones), so bar 6's 20 could not be reached
whatever the model does.
- **On the 500 hands,** bar 6 is unchanged except for the 4× minimum: every live-solve
  answer is legal by Gate V bar 2's rule, and there are at least 100.
- **A second set of 200 hands,** seed 20261119:
  - each player's stack is drawn uniformly from 25 to 100 bb, in whole chips of 0.1 bb;
  - the SB opens to 2.5, the BB 3-bets to 10 and the SB calls, so every pot is a 4× 3-bet
    pot;
  - after that, play is random and legal, as in Gate V's hands;
  - both players are advised.

  Every live-solve answer is legal by the same rule. At least 20 answers are needed;
  fewer is not measured, which is a FAIL.
- **Bar 7 is unchanged.**

**Result (2026-11-21): Gate Q FAIL on bars 4 and 5; step 4 stops here.** R did not settle:
- the 3× 3-bet pot was reached at no fit depth;
- every measured cell moved 0.04 to 0.10 between the rounds.

The same unreached 3× size, and the SB's first-in jam, failed bar 5's counts. Bars 1, 2, 3,
6 and 7 passed (GATES.md). Ian chose, on 2026-11-21:
- the old model stays live as `data/preflop_model.json`, byte for byte;
- the new one is kept, unused, as `data/preflop_model_v2.json`;
- step 5 builds on the old model;
- no successor gate is registered.

The ideas that were not taken up: damped extra rounds, filling an unmeasured 3× pot from the
4× pot's R, and dropping the 3× size.

---

### 50. Step 5: the opponent model, playstyle labels and an exploit line on the overlay; Gate O pre-registered (2026-11-19)

**Decided:** Ian picked these on 2026-11-19, after DECISIONS 49. This is Phase
12's opponent model (plan doc, Phase 12, items 1 to 4), joined to his playstyle
picks of DECISIONS 47: Nit, TAG, LAG and Station, set by buttons on the
overlay, shown and logged, and setting preflop widths, live-solve locks and
tilted stopgap curves. SCOPE amendment A11 brings it into scope. It is built
after Gate Q passes, so "the model" here is DECISIONS 49's.

**Reads, relative to the model** (Ian's pick). Every read is a ratio ρ: how
often a friend takes an action, against how often the model would in the same
spots. ρ = 1 plays the model, and 0.55 folds 0.55 times as often.
- **A chance** is one decision of the friend's that a tendency counts. Its
  model rate e is the model's own rate for that action at that spot, over the
  friend's range (not the friend's unknown hand).
- **Counting.** In n chances the friend took the action X times. E = Σe is
  what the model would have done, and ē = E / n.
- **Shrinking** (Phase 12's beta prior worth k chances):
  - the shrunk rate is p̂ = (X + k·ρ0·ē) / (n + k), and the read is ρ̂ = p̂ / ē;
  - with no chances, ρ̂ = ρ0;
  - ρ0 is 1 for an unmarked friend, or the label's ratio for a marked one
    (Ian's pick: "label if marked, else model"). A label changes the prior,
    not the counts.
- **A chance whose model rate is 0** does not count.

**The seven tendencies** (Ian ticked all four groups).

| Tendency | A chance | The action | Its model rate e |
|---|---|---|---|
| SB open | the friend is the SB, first in, above 20 bb | a raise or an all-in | the model's chart at the nearest depth |
| BB defend | the friend is the BB facing a raise below all-in, above 20 bb | a call, raise or all-in | the chart, against the model's SB open range |
| BB 3-bet | the same chances | a raise or an all-in | the same |
| Push/fold jam | the friend is the SB, first in, at 20 bb or less | an all-in | push/fold Nash at that depth |
| Push/fold call | the friend is the BB facing a first-in all-in, at 20 bb or less | a call | push/fold Nash, against Nash's jam range |
| Fold to a bet | postflop, the friend faces a bet, raise or all-in | a fold | see below |
| Bet when checked to | postflop, the friend acts after the other player checked on that street | a bet or all-in | see below |

- **Postflop model rates.**
  - On a turn or river where the base track ran a live solve (DECISIONS 47):
    the solved range-level rate at the mapped node.
  - Otherwise: the stopgap's curve for that pot, street, position and node
    (DECISIONS 46), averaged over its 10 bands. The bands are deciles of the
    range, so the mean is the range's rate.
  - A single-raised pot uses the `srp` curves and a 3-bet pot the `3bp` ones.
    Limped and 4-bet pots do not count.
- **Which hands count** (Ian's pick):
  - preflop chances only from hands dealt heads-up;
  - postflop chances from any pot that is heads-up by the flop.
- **The depth** is the hand's effective starting stack, looked up as the
  advisor does (DECISIONS 32, 34).
- **The source** is the tracker's PHH hands in `data/live/hands/`, which
  carry the players' names. They are read at start and after each hand.
  Poker Now game logs join when Phase 11 exists.

**k, fitted from the PHH players** (Ian's pick).
- **Data:** one pass over the PHH zip (DECISIONS 39, SHA-256 `65d566e7…`),
  heads-up hands only, counting each tendency's chances and actions per player
  by the same definitions, as plain rates. The pass starts only when Ian says
  so; it took 790 s last time.
- **The fit,** per tendency, over players with at least 100 chances of it:
  - p̄ is the pooled rate;
  - the spread between players is the variance of their rates, less the mean
    of p̄(1 − p̄) / nᵢ, their sampling noise;
  - k = p̄(1 − p̄) / that spread − 1;
  - a spread of 0 or below means the fit fails, and k = 20, noted.
- **Push/fold has no PHH data** (no stacks), so its two tendencies take k = 20.

**The labels, from PHH player groups** (Ian's pick).
- **The players:** PHH heads-up players with at least 500 heads-up hands.
- **The split:** at the median VPIP (looseness) and the median PFR / VPIP
  (aggression):

  | | Aggression at or below the median | Above it |
  |---|---|---|
  | VPIP at or below the median | Nit | TAG |
  | VPIP above the median | Station | LAG |

- **A label's ratio** for a tendency is its group's median rate over the
  median rate of all these players.
- **Push/fold proxies,** labelled as assumptions: the jam ratio is the label's
  SB open ratio, and the call ratio its BB defend ratio.
- **Stored:** `data/opponent_priors.json`, committed. It holds the per-player
  counts with no names, the fitted k and the label ratios, with the dataset's
  CC BY 4.0 attribution.

**How a read changes the villain.**
- **Preflop and push/fold: a cutoff in the model's own order** (Phase 12's
  design, item 2, and DECISIONS 37's open "Nash's own order").
  - The node's share for the read's actions becomes ρ̂ times the model's.
  - Classes are filled in the model's order: by its probability of those
    actions, then by equity against a random hand. Each class takes them
    fully until the share is filled; the boundary class is partly filled.
  - The rest take the model's other actions in proportion, or fold.
  - BB defend is applied first, then BB 3-bet inside the defending share.
  - Per-class scaling was not used here: push/fold Nash and most model
    classes are pure (0 or 1), and scaling a pure strategy changes nothing.
- **Postflop: the solver's or curve's mix, scaled** (Ian's pick: "keep the
  solver's choice of which hands").
  - The read's actions (a fold; or every bet and all-in together) get
    min(1, λ·q) per hand, where q is the base solve's probability.
  - λ is chosen so the node's rate is ρ̂ times the solved rate. For ρ̂ ≤ 1,
    λ = ρ̂.
  - When even λ → ∞ can't reach it (every hand with q > 0 is at 1), the node
    stays short and that is noted.
  - The rest of each hand's weight keeps the solve's split among the other
    actions. If they had none, it goes to Call facing a bet, or Check after a
    check.
- **On the flop** the same rule tilts the stopgap curves, band by band, and
  the tilted curves narrow the villain's range.
- **On the turn and river** the rule locks the villain's nodes of each read
  kind on that street, and on the river inside a turn solve.

**What Ian is shown** (Ian's picks). A villain has a read when Ian marked it,
or when it has at least one counted chance of a tendency this decision uses.
- **With a read,** the overlay's headline is the exploit, e.g. "RAISE 12 bb
  (exploit)". Under it:
  - the base answer with its usual source ("live solve: call 64%, raise
    36%"). The word GTO is never used for a model chart or the equity helper;
  - **gain:** what the exploit wins over the base answer against the read, in
    bb;
  - **risk:** what it loses against a villain who plays the model, in bb
    (zero or below, up to solver error);
  - **who and how sure:** "Bob: Station, folds to bets 0.55× the model (22%
    vs 41%), 34 chances".
- **Without a read** the overlay is exactly today's.
- **The buttons:** Nit, TAG, LAG, Station and clear, for the heads-up villain.
  Labels are kept by name in `data/live/opponents.json`, which is gitignored
  like the rest of `data/live/`.
- **The hand log** records the label, the reads used, their chances and both
  answers with each suggestion.

**The exploit, by decision.**
- **Preflop above 20 bb.** The best response, at every Ian node below this one,
  to the model with the friend's read nodes replaced. It is computed on the
  compiled model tree. Gain and risk compare that plan with the model's mix
  for Ian's class: against the read, and against the model.
- **Push/fold.** DECISIONS 37's best response, gain and risk, with the read's
  cutoff in Nash's order in place of the top N% by equity.
- **The flop.** The equity helper against the tilted range; the base is the
  helper against the untilted one. Gain and risk are shown only where the
  helper has an EV, a call or a fold (E·(pot + to call) − to call). Otherwise
  the line says "no EV on the flop".
- **The turn and river.** A chain of passes in `streets.rs`:
  1. the unlocked solve, as Gate V's; this is the base line, shown first;
  2. the locked solve, with the villain's nodes scaled from pass 1; Ian's row
     at his node is the exploit;
  3. two evaluations with both players fixed: Ian's base strategy against the
     locked villain (for the gain), and Ian's exploit strategy against the
     pass-1 villain (for the risk), at Ian's node and hand.

  - **The binary gains this,** as an optional `read` in its spec. Without
    one, it runs as today. Its new SHA-256 is recorded. If postflop-solver
    can't evaluate fixed strategies, the build stops and asks Ian.
  - **Two range tracks.** The base track narrows the ranges for later streets
    as DECISIONS 47 does. The exploit track narrows them by the locked solves
    and tilted curves. Both keep DECISIONS 47's floors.
  - **Timeouts** are twice the bars: the base keeps Gate V's 6 s turn and 3 s
    river; the exploit chain gets 12 s and 4 s. On a timeout or failure, the
    base answer stands with the note "no exploit:" and the reason.

**Gate O: all six bars must pass.**
1. **Counts from a hand-counted fixture.** At least 30 hand-made logged
   hands, 2 to 9 handed, with made-up names.
   - Every friend's chances n, actions X and each chance's model rate equal a
     count done by hand.
   - Preflop and push/fold model rates are written by hand from the charts.
   - Postflop model rates are checked by a separate code path, to 1e-9:
     against the bridge's own output for that node (as Gate V bar 3 did), or
     against the stopgap curve's stored values.
   - The fixture covers at least 3 chances of each of the seven tendencies;
     at least 2 hands dealt 3+ handed that are heads-up by the flop
     (postflop counts, preflop doesn't); at least 1 that is not (nothing
     counts); and a chance whose model rate is 0.
2. **Shrinkage and the k fit, by hand.**
   - At least 10 reads in the fixture, unmarked and under each label and with
     no chances among them, equal a hand calculation from their counts, prior
     and k, to 1e-12.
   - Each fitted k and each label ratio equals a recomputation from the
     stored per-player counts by a separate function, to 1e-9.
3. **Locks hold.** At least 20 seeded locked live solves: turn and river,
   both read kinds, ρ̂ below and above 1.
   - In the locked solve's report, every locked villain row equals the scaled
     mix computed from the unlocked solve's report, to 1e-6.
   - Each locked node's rate equals ρ̂ times the solved rate, to 1e-6, unless
     it is noted as short.
4. **Push/fold simulations.**
   - **The bots:** a BB that calls with 1.5× Nash's calling share, and an SB
     that jams with 0.5× Nash's jamming share, both by the cutoff rule, at 10
     and 20 bb: four runs. Ian takes the other seat.
   - **The deals:** 100,000 per run, seed 20261119. Each deal gives both
     hands and a full board, and an all-in is settled on that board by eval7's
     `evaluate`.
   - **The gain.** On the same deals, Ian's exploit for the bot's true read
     and Ian's Nash strategy each play the bot. The measured gain, the mean
     paired difference, is within 3 standard errors of the predicted exact
     gain, above or below.
   - **The risk.** On the same deals against a Nash bot, the measured risk is
     within 3 standard errors of the predicted exact risk, above or below.
   - The standard error is the paired differences' sd / √100,000.
5. **Preflop latency.** Over Ian's preflop decisions with a read in bar 6's
   hands, from feeding the frame to the suggestion event with the exploit,
   base, gain and risk: the 95th percentile is at most 300 ms. There must be
   at least 30 decisions. Separate process, no coverage, idle laptop
   (DECISIONS 32).
6. **Live latency.** Gate V bar 4's method and its 500 hands (seed 20261116):
   - every-change frames through the tracker;
   - Ian the SB in even hands;
   - the villain marked Nit, TAG, LAG and Station in turn by hand number,
     with an empty hand log that the run does not add to, so its reads are
     the labels'.

   From feeding the frame that first shows the street's card:
   - **the base line:** turn 95th percentile ≤ 3 s, river ≤ 1 s;
   - **the exploit line, with gain and risk:** turn ≤ 6 s, river ≤ 2 s.

   Numpy's linear percentile. Timeouts and failures count at their full time.
   There must be at least 30 per street for each line, or the bar is not
   measured, which is a FAIL.

**Reported, not gated** (Ian did not tick these as bars):
- on bar 3's spots, the sign of each gain and risk, and whether Ian's river
  bluffs rise against ρ̂ = 1.5 folds and fall against 0.5;
- the labels in the log, and the buttons;
- each tendency's fitted k, the label ratios, and the group sizes;
- the new binary with no read against ef5ab1cf, on Gate V bar 3's 40 specs.

Ian also did not pick preflop simulations above 20 bb.

**Older tests, decided here.** The opponent model acts only when the advisor
is given an opponent store with a read in it. `Advisor.load()` without one
behaves as today. So:
- Gates R, T and V are unchanged;
- Gate T bar 6's overlay texts are unchanged (the buttons are separate
  widgets);
- Gate V's tests run on the new streets binary.

Any older test that fails anyway is reported to Ian before it changes.

**Rules out:**
- labels set by anything but Ian's buttons; automatic player typing stays
  parked;
- committing friends' names, labels, reads or hands: `data/live/` stays
  gitignored, and the fixture's names are made up;
- changing the definitions, the k fit, the label groups, the lock rule, the
  bots, the seeds or any bar after the first evidence run, except by a dated
  amendment;
- changing the flop bridge's binary;
- a library run.

---

### 51. Spike S1, the screen reader: Gate S1's measurement fixed before any screenshot or reader code (2026-11-21)

**Decided.** Ian picked these on 2026-11-20, when he asked for the shortest
path to a live game (plan doc, Status, "The path to a live heads-up game"):
- the first live game is heads-up with one friend who knows;
- the screenshots come from `showdown capture` (F9) during a self-play
  session;
- I draft the truth labels, and Ian checks 10 of them.

S1's bars stay as Phase 8 set them, and as DECISIONS 42 widened them: 100% of
cards, at least 99% of numbers, and at most 300 ms per read. This entry fixes
how they are measured, and adds one bar.

**The screenshots.**
- **The session:**
  - Ian self-plays a private play-money Poker Now game in two browser
    windows;
  - the four-colour deck is on;
  - one window size and zoom is used throughout, and is recorded in GATES.md.
- **What to capture:** at least 100 F9 captures, covering:
  - every street, both buttons and both players' turns;
  - bets in front;
  - an all-in run-out and a showdown with cards shown;
  - end-of-hand frames;
  - stacks of 1 to 4 digits.
- **Where they live:** the gitignored `data/live/screens/`. They are never
  committed.
- **The split,** by capture order (the file names sort by time):
  - the first captures, at most 50, are the dev set;
  - the rest, at least 50, are the test set;
  - with fewer than 100, the test set keeps 50 and the dev set gets what is
    left. With fewer than 60 in all, S1 waits for more.

**The labels.**
- **What each frame should read as:** DECISIONS 42's `TableState`, plus the
  blinds:
  - Ian's cards and the board;
  - for each seat, its name, stack and bet, whether it holds cards, and its
    shown cards;
  - the button, the seat to act, `ended`, and the pot when it is shown.
- **The cross-check:** the game's downloaded log gives each hand's cards,
  stacks and actions. A label that disagrees with the log is redrafted.
- **Ian's check:** 10 test frames, picked at random with the seed recorded.
  One mismatch means every label is redrafted and checked again.
- **Sealing:** the test labels are written and checked, and their SHA-256 is
  recorded in GATES.md, before the reader first runs on any test frame.
  - The labels and screenshots are pinned by a manifest hash, as
    `require_pluribus` does (DECISIONS 25).
  - A missing or changed file fails the test, never skips it.

**Gate S1,** scored once on the test set:
1. **Cards: 100%.** That covers Ian's cards, the board and shown cards. A
   missing or extra card counts as wrong.
2. **Numbers: at least 99%.** That covers stacks, bets, the pot (when shown)
   and the blinds, each exact to the chip.
3. **The tracker's fields: at least 99% each.** This bar is new, because the
   tracker depends on these fields. They are the button, the seat to act,
   whether each seat holds cards, and `ended`. Names are reported, not gated.
4. **Speed: every test read takes at most 300 ms.** It is measured as
   DECISIONS 32 does: in a subprocess, without coverage, on an idle laptop. A
   read runs from the PNG's pixels in memory to the `TableState`.

A read may return a `ReadError` instead of a frame, and the advice then says
"no suggestion". On the test set, a `ReadError` counts as wrong for every
field of its frame.

**The method,** as first planned. It may change, but only on the dev set.
- **Window size:** each read is normalised by the table's position and size
  in the window. A window size the dev set never showed gives a `ReadError`
  ("window size changed").
- **Cards:** ranks by template matching against glyphs cut from the dev set;
  suits by colour, which the four-colour deck makes distinct.
- **Numbers and names:** Windows OCR (Windows.Media.Ocr, through pywinrt) on
  small crops.
- **The button, the turn and `ended`:** fixed visual markers.
- **Packages:** Pillow and the pywinrt packages join the `live` extra, pinned,
  when the reader first needs them. Their versions are recorded in GATES.md.

**Rules out:**
- running the reader on a test frame before the test labels are sealed;
- tuning on the test set;
- changing the split, a sealed label or any bar after the first test run,
  except by a dated amendment;
- reading any window but Poker Now's, or sending screenshots off the laptop
  (D1, DECISIONS 30);
- committing screenshots, labels or game logs.

---

### 52. Phase 10: `showdown live --screen` and Gate H, on self-play; pre-registered before the loop's code (2026-11-21)

**Decided.**
- Ian approved D1 to D11 on 2026-11-21 (plan doc, Status).
- Gate H runs on self-play, decided without Ian on 2026-11-21: Ian plays
  himself in two Poker Now windows. A game with a friend can follow later,
  under the same bars.
- This entry fixes the screen loop and Gate H before any loop code. The reader
  (S1, DECISIONS 51) and the Poker Now log parser (Phase 11, Gate I) don't
  exist yet. So the loop takes the reader through an interface, and is built
  and tested with fake images now.

**The interface:** `read(png: bytes) -> TableState | ReadError`.
- `ReadError` sits beside the frame contract in `live/table.py` and carries a
  reason.
- S1's `live/reader.py` implements `read`. Until it exists,
  `showdown live --screen` stops with "the screen reader (spike S1) isn't
  built yet".

**The loop,** `src/showdown/live/screen.py`, run by `showdown live --screen`:
- **One window.** At start the loop waits for a Poker Now window in front,
  and locks onto that window (its handle). That window is Ian's seat; in
  self-play the other window is the opponent's, and the loop never reads it.
  - It captures only while the locked window is in front and its title says
    Poker Now. Otherwise it waits.
  - Both windows are maximised (D10), so the table can only be seen while
    it is in front.
- **Every 250 ms** it grabs the window with `capture.grab_png`.
- **Unchanged images are skipped.** An image identical to the one before is
  not read again; it counts as the same read.
- **Two reads alike.** A frame goes to the tracker only when two captures in a
  row read the same and it differs from the last frame fed. Animations, such
  as cards dealing or chips sliding, change between captures, so they never
  reach the tracker.
- **Reading errors** that read the same twice are logged and shown as "no
  suggestion: reading error: why", once per change. They never reach the
  tracker.
- **Exceptions.** An exception inside one capture's work is logged with its
  traceback as a crash line, and the loop goes on.
- **PNGs saved,** under the gitignored `data/live/decisions/<session>/`:
  - the image of every frame fed with Ian to act;
  - the image of every logged reading error.
- **The overlay** is DECISIONS 42's window:
  - it is placed beside the table: to the right of the window if the screen
    has room, else inside the window's top-right corner;
  - Ian can drag it;
  - it stays on top and visible to screen share.
- **The session log,** `data/live/sessions/<start>.jsonl` (gitignored), is
  flushed after every line. There is one line per:
  - frame fed, the whole `TableState` with its capture time;
  - tracker event, with the decision, the suggestion, the timings and the PNG;
  - reading error;
  - crash.

  Each line names the tracker's hand number. `--screen` always saves: the
  session log, the PNGs, and PHH for every ended hand. That is V1's "every
  hand logged".
- **Live solves** still hold the loop while they run, up to Gate V's
  timeouts. The overlay shows "solving…" meanwhile.
- **Never:** clicks, keystrokes, another window, or anything sent off the
  laptop.

**Gate H, the session.**
- One private play-money Poker Now game. Ian is alone in two browser windows,
  both maximised at S1's window size and zoom (D10). The four-colour deck is
  on if S1 had it (D3). The blinds and stacks are recorded in GATES.md.
- At least 100 hands dealt heads-up, counted from Poker Now's downloaded log.
- No other heavy process runs during it: no library build, no solve, no gate
  run.
- **The truth** is Poker Now's log, read by the Phase 11 parser after Gate I
  passes. Gate H is scored once, after the session.
- **Hands are matched in order.** Each tracker hand goes to the first unmatched
  log hand after the last match with the same two starting stacks. A
  tracker hand's starting stacks are stack plus bet on its first frame.
- **Ian's seat** in the log is the nickname of the window the loop read,
  recorded in GATES.md.

**Gate H's bars:**
1. **Cards: 100%.** That covers every card in every frame fed to the tracker:
   - the board, which must equal the log's board up to that street;
   - the opponent's shown cards, which must equal the log's;
   - Ian's hole cards, which must equal the log's.

   If the log lacks Ian's hole cards (D6): 20 hands are drawn, with seed
   20261122, from those with a saved decision PNG. I label Ian's cards from
   the PNG, and each must equal the tracker's. A tracker hand that matches no
   log hand fails this bar.
2. **Latency.**
   - **Preflop: median at most 2 s. Flop: median at most 15 s.** These are
     over Ian's decisions answered with a real suggestion, taking each
     decision's first one. The time runs from the capture of the first of
     the two images that let the decision's frame through, to the overlay
     showing the suggestion. So it includes the second capture, both reads
     and the tracker.
   - **Turn and river: Gate V's bars,** measured as Gate V measures them.
     That is from feeding the frame that first shows the card to the answer,
     for decisions where a live solve was started. The bars are a 95th
     percentile of at most 3 s on the turn and 1 s on the river (numpy's
     linear percentile). The same times from that frame's first capture are
     reported, not gated.
3. **No crash.** Zero crash lines in the session log. The session runs in one
   run of the command, and every hand the tracker ended is written as PHH.
4. **Coverage: at least 90% (D7).**
   - **Ian's decisions** are his actions in the log: fold, check, call, bet
     or raise. Blinds and shows don't count.
   - **A decision is covered** when the session log has a real suggestion
     for it: an action, not "no suggestion". It is found by its matched
     hand and the number of actions before it in the hand.
   - **Left out of both counts, and reported:** decisions the advisor turns
     down by its own rules. In those the tracker read the spot, and the
     advisor gave "no suggestion" (such as DECISIONS 35's 0.1% reach rule)
     or a spot error.
   - **Uncovered:** reading errors, abandoned hands, hands with no match and
     turns never seen.
5. **Reported, not gated:**
   - hands the tracker abandoned, by cause (the reading error's text, "N
     players dealt in", "joined mid-hand", no end frame);
   - uncovered decisions, by cause;
   - bets written at an unseen size;
   - the read time per capture: median and 95th percentile.

**The order:**
1. A dry run of about 20 self-play hands. Fix once, then stop. Its hands don't
   count.
2. The Gate H session: 100 or more hands.
3. Ian downloads the game's log into `data/live/`.
4. Gate H is scored once, and recorded in GATES.md as PASS or FAIL.

**The loop's tests, before the reader exists.** They use fake PNG bytes and a
fake reader that turns each into a frame from Gate T's saved hands:
- a frame seen once between two others never reaches the tracker;
- unchanged images are not read again;
- every decision that Gate T's every-change frames give comes through, and
  each one's PNG is saved;
- reading errors are logged once per change and never fed;
- a crash in one capture is logged, and the next capture still works;
- captures happen only while the locked window is in front;
- the overlay's position.

**Decided without Ian (2026-11-21),** each the reversible option:
- the loop reads only the locked window, and only while it is in front, since
  self-play uses two maximised windows;
- coverage leaves out the advisor's own refusals and reports them. They are a
  model gap, which Gates G, P and V already cover, and not a reading failure;
- hands are matched by starting stacks, in order;
- D6's seed is 20261122;
- the turn and river are timed as Gate V does, and the full time from the
  capture is reported beside it;
- `--screen` always saves, so a forgotten flag can't lose the session.

**Rules out:**
- clicking anything, or hiding the overlay from screen share;
- reading the opponent's window or any window but Poker Now's;
- sending images off the laptop;
- committing screenshots, PNGs, the session log or game logs;
- ClubWPT, ever (DECISIONS 29);
- changing a bar after the session, except by a dated amendment.

---

### 53. A six-max preflop spot engine for unopened and limped pots; Gate M pre-registered (2026-11-22)

**Decided.** Ian approved the design and every bar below on 2026-11-22, all as recommended,
in one question box asked before any code (SCOPE A12). It is the first slice of a six-max
cash trainer: given a spot, `showdown sixmax` shows the opponents' assumed ranges, each
action's EV, the best action and a tier. A drill trainer and six-max hand review are later
steps with their own entries.

**What it is not.** It is not a solver and finds no equilibrium. It is the best response to
opponents who follow a stated profile, with postflop valued as equity × R and not played.
Its answers are as good as the profile and R.

**The spot.**
- Seats in preflop order: UTG, HJ, CO, BTN, SB, BB. Postflop order: SB, BB, UTG, HJ, CO,
  BTN.
- Stacks are 100 bb before blinds and antes. Blinds 0.5/1. The ante is 0 or 0.5 bb from
  every player (3 bb in all).
- k limpers, 0 to 3, ahead of the hero. They are non-blind seats; every other seat ahead of
  the hero folded. With the hero in the BB, the SB folded. Which non-blind seats limped
  changes no number: they all act before a non-blind hero postflop, and after a blind one.
- Allowed: UTG k = 0; HJ k ≤ 1; CO k ≤ 2; BTN and SB k ≤ 3; BB k = 1 to 3 (k = 0 is a walk).
- Players behind: the seats after the hero in preflop order.

**Actions.**
- Fold: EV 0. Not offered to the BB, whose check is free.
- Limp: call to 1 bb. The SB completes; the BB checks.
- Raise to X: unopened, X = 2.5, 3 or 4 bb; with k limpers, X = 3+k, 4+k or 5+k bb. The
  middle size is the reference size, X_ref.

**EV, in bb relative to folding** (chips already posted are sunk):
- **The deal.** 40,000 deals per spot, seeded. Each deal gives every opponent a hand: a
  limper from its profile's limp range, a player behind from all 1,326 combos. The whole
  set is redrawn if two hands share a card. Then a 5-card board from the rest.
- **The hero's hand.** In each deal, a combo of the hero's class is drawn uniformly from
  those that miss every dealt card, and the deal is weighted by how many there are (0 if
  none). That is the same as dealing the hero first: opponents' ranges are closed under
  suit relabelling. So one deal serves all 169 classes and every action. An exact combo
  (`As5s`) can be given instead; it gets weight 1 when it misses every dealt card, else 0.
- **Strength.** Classes are ranked by exact equity against a random hand (the matrix row,
  weighted by card-removal pair counts). A hand's place q in a range runs from 0 (weakest)
  to 1 (strongest), combo-weighted, with combos of a class spread evenly across the class's
  share. "Top x" means q ≥ 1 − x.
- **Facing the hero's raise to X** (δ is the band's fold shift, 0 at the base):
  - a player behind 3-bets with its top t, calls with the next c(X), and folds the rest,
    where c(X) = max(0, c_ref − s_b·(X − X_ref) − δ). The SB and BB have their own t and
    c_ref;
  - a limper re-raises with the top r of its limp range, calls when q ≥ f(X), and folds the
    rest, where f(X) = min(1 − r, max(0, f_ref + s_L·(X − X_ref) + δ)), q taken within the
    limp range;
  - players behind act first, in seat order, then the limpers, in seat order. The first
    re-raise is the one the hero faces; everyone else then folds, and chips already in stay
    in the pot.
- **Facing the hero's limp:** a non-blind player behind raises with its top x and overlimps
  with the next o; the SB raises with its top x_sb and completes with the next z; the BB
  raises with its top x_bb and checks the rest.
- **Payoffs.** The pot P is 6 × ante plus every chip put in.
  - Everyone folds to the raise: the hero wins the pot.
  - To the flop: R × share × P − the chips the hero added. The share is exact when one
    opponent is left: the matrix cell M[hero class, opponent class]. With two or more, it
    is the deal's board, the pot split equally among the best hands (`multiway.py`'s rule).
    `multiway.pot_shares` is per set of hands, too slow to call per deal, so the engine
    ranks each deal's board once with the same evaluator.
  - A raise behind the hero's limp: the hero folds. **The limp EV is a floor.**
  - A re-raise: the hero stacks off or folds, whichever its exact equity against the
    re-raiser's range (`live/jam.py`'s `jam_equity`) says is worth more, given the pot it
    can see. Stacking off, both put in 100 − ante; the payoff uses M[hero, re-raiser's
    class] × P − the hero's chips added.
- **R,** by who has the initiative and who is last to act postflop: hero raised and in
  position 1.00; raised and out of position 0.90; limped pot in position 0.85; out of
  position 0.75. Anchor: Gate Q's own flop solves measured 0.63 to 0.78 for an
  out-of-position caller and 1.02 to 1.10 for the out-of-position 3-bettor (GATES.md).
- **Standard error** of each EV and of the gap between two actions: self-normalised
  importance sampling, sqrt(Σ w²(p − EV)²) / Σ w, over the deals.

**Profiles, fitted to the PHH hands.** A spike,
`spikes/2026-11-22-phh-sixmax-profiles.py`, reads DECISIONS 39's zip (SHA-256 pinned there)
straight from disk: the HandHQ no-limit hands with 3 to 6 players, all stakes.
- **Buckets.** Players with at least 500 such hands, by their own VPIP and PFR over them:
  - tight: VPIP under 20%;
  - regular: VPIP 20% to under 35%;
  - loose-passive: VPIP 35% or more and PFR under half of VPIP.

  Loose-aggressive players (VPIP 35% or more, PFR at least half of it) are counted and left
  out.
- **What is counted,** preflop, by the acting player's bucket:
  1. first in, not a blind, everyone before folded: fold, limp, raise;
  2. facing one or more limpers and no raise, not a blind: fold, overlimp, raise;
  3. a player who limped (1 or 2), facing exactly one raise when it next acts: fold, call,
     re-raise; by m = raise-to minus the limpers before the raiser, in bb, in buckets under
     3.5, 3.5 to 4.5, 4.5 to 5.5, and 5.5 or more;
  4. the SB and the BB facing one open raise and no limpers: fold, call, 3-bet; by the
     open's size in bb, in buckets under 2.75, 2.75 to 3.25, 3.25 to 3.75, and 3.75 or more;
  5. a non-blind player facing one open raise and no limpers, its first action: fold, call,
     3-bet;
  6. the SB facing limpers and no raise: fold, complete, raise; the BB: check, raise.
- **Into the engine:**
  - limp range: the classes between the top (open-raise %) and the top (open-raise % +
    limp %) of count 1, by strength, partial classes weighted;
  - f_ref: count 3's fold share at m 3.5 to 4.5 (the engine's 4+k); r: count 3's re-raise
    share over all sizes; s_L: the chance-weighted least-squares slope of count 3's fold
    share on each bucket's mean m;
  - c_ref (SB, BB): count 4's call share at 2.75 to 3.25 bb (the engine's 3 bb); t (SB,
    BB): count 4's 3-bet share over all sizes; s_b: the slope of the BB's fold share on each
    size bucket's mean size, used for every player behind;
  - a non-blind player behind: t and c_ref from count 5;
  - x, o from count 2; x_sb, z, x_bb from count 6.
- **Fallback.** A rate with fewer than 1,000 chances in its bucket, or a slope with fewer
  than three buckets of 1,000 chances, uses the hand-picked value below. The output says
  "assumed" beside it.

  | | tight | regular | loose-passive |
  |---|---|---|---|
  | open-raise / limp, first in | 12 / 10% | 13 / 20% | 7 / 40% |
  | limpers vs an iso of 4+k: fold / re-raise; fold slope per bb | 50 / 2%; 0.06 | 40 / 4%; 0.04 | 25 / 3%; 0.02 |
  | non-blind behind vs an open: 3-bet / call | 4 / 4% | 5 / 7% | 2 / 15% |
  | SB: 3-bet / call; BB: 3-bet / call | 4 / 5%; 4 / 25% | 5 / 8%; 5 / 35% | 2 / 20%; 2 / 50% |
  | fold slope per bb, players behind | 0.04 | 0.04 | 0.02 |
  | vs a limp: raise / overlimp; SB raise / complete; BB raise | 8 / 5%; 8 / 20%; 8% | 10 / 10%; 10 / 35%; 10% | 4 / 30%; 4 / 60%; 4% |
- **Output:** `data/sixmax_profiles.json` (rates, chances, slopes, the zip's SHA-256) and
  `docs/sixmax-profiles.md`. Both hold only aggregates, credited to the dataset (CC BY 4.0).
  One profile covers the whole table, limpers and players behind.
- These are 2009 online players at 25NL and up, with no antes. They are priors for Ian's
  games, not measurements of them.

**The verdict.**
- **Best:** the highest EV at the base point. **Runner-up:** the second.
- **The band:** 9 points, R moved by −0.1, 0, +0.1 (all R together) × δ = −0.10, 0, +0.10
  (the limpers' fold to an iso, and the calls of players behind).
- **Close:** at some band point another action has the highest EV. The runner-up is shown,
  with the band points where something else wins.
- **Review:** not close, but either the gap to the runner-up is under 3 standard errors, or
  the best action changes when the hero folds to every re-raise instead of stacking off.
- **Clear:** otherwise.

**Gate M,** recorded before any engine or spike code. It passes when bars 1 to 3 pass.
1. **Closed forms,** each worked by hand in the test from the matrix, not through the
   engine:
   - everyone folds (every continue and re-raise rate 0): each raise's EV equals the pot
     before the hero acts, at every allowed seat and k, both antes;
   - one caller with a fixed range: hero on the BTN behind one limper whose range is KK,
     who always calls (f = r = 0), blinds always fold: EV = 1.00 × M[hero, KK] × P − X;
   - a limped pot with the BB: the hero in the BB checks behind one limper whose range is
     QQ, SB folded: EV = 0.75 × M[hero, QQ] × (2.5 + 6 × ante);
   - a stack-off against a limp-reraise: one limper whose range is AA and who always
     re-raises; KK folds (EV = −X); AA stacks off (EV = 0.5 × P − (100 − ante));
   - these four match to 1e-9, on AA, KK, A5s, 72o where the spot allows;
   - a 3-way pot: hero AsAh on the BTN isolates two limpers holding KhKd and QcQs, who always
     call, blinds folding. The EV is within 4 combined standard errors of R × share × P − X,
     the share from `multiway.pot_shares` with 200,000 runouts.
2. **Monotonic,** over the 169 classes of every allowed seat and k, each profile, both
   antes (102 charts). Classes that are close or review in either chart compared are left
   out and counted.
   - **The ante widens:** every class whose best action is not fold with no ante is not
     fold with the 0.5 ante.
   - **More limpers, no new offsuit isos:** for BTN, SB and BB from 1 to 2 and 2 to 3
     limpers, and CO from 1 to 2, each profile and ante: every offsuit class whose best
     action is a raise with one more limper is a raise with one fewer.
   - **Looser limpers, larger isos:** for HJ (k = 1), CO (k = 1, 2) and BTN (k = 1, 2, 3),
     each ante: for each of AA, KK, QQ, AKs and AKo, the best raise size against
     loose-passive is at least the best against tight.
   - **Reported, not gated:** how many classes isolate against each profile. Tight limpers
     fold more, which honestly widens isos against them.
3. **Chart.** Unopened pots, no ante, regular profile, against PokerStrategy's six-max
   opening ranges (below). At each of UTG, HJ, CO, BTN and SB, at least 85% of the
   classes our tier calls clear agree with the chart on raise vs not raise (fold or limp).
   Every disagreement is listed, and the close and review classes counted.

**The chart.** PokerStrategy.com's "Big Stack Strategy" six-max opening ranges, lessons
2253 to 2257 (UTG, MP, CO, BU, SB), saved on 2026-11-22 with Ian's approval into the
gitignored `data/external/pokerstrategy/`, pinned by SHA-256, never committed:

| Lesson | Seat | SHA-256 | Range | Page's count |
|---|---|---|---|---|
| 2253 | UTG | `d1a323c47fc26b1cf058463204cb93a8ad643de259479350953d20af4a49ac42` | 13% | 176 combos |
| 2254 | MP, our HJ | `4cc23c645ce6f0a21a94a0a1669ace8440f9fb4438eadac0199e98b2087e7a4b` | 17% | 226 |
| 2255 | CO | `58fc8ec282fbaecef5e22d4474fe075d0e4bbce9a5410e531563a2364c6cf83f` | 32% | 426 |
| 2256 | BU | `fbb9c26a785beff323d03b429a2bc89a4cfbe0e940f7831a9e254a3511665006` | 62% | 826 |
| 2257 | SB | `f1ac3ea6d3e1e57731d737028c771a929662aab2fda8f4c266325dea585c37c8` | 31% | 410 |

- Each page's first list followed by its "(#N / P%)" or "(P%, #N)" count is its open range.
  It is parsed with `parse_range`. Where a token reads two ways, the reading whose combo
  count equals the page's N is used: MP's "65s+" means 65s, 76s, 87s, 98s, T9s and JTs (226
  combos; 206 the other way). The test asserts every list's count equals the page's.
- The ranges were built from 1.5 million NL200 hands against a "standard opponent", not by
  a solver. The pages name open sizes of 2 to 3 bb; we compare raise vs not raise only.

**The order:**
1. This entry and SCOPE A12, committed and pushed.
2. The spike, run once on AC. A crash or a wrong count gets one fix, then it stops.
3. The engine, its tests, and `showdown sixmax`.
4. Gate M scored once and recorded in GATES.md. A failing bar gets one reproduce-and-fix,
   then the result stands.
5. `docs/sixmax-preflop.md`: what the slice can and cannot be trusted for.

**Decided without Ian (2026-11-22),** each the reversible option:
- the CLI is `showdown sixmax SEAT HAND [--limpers K] [--ante A] [--profile P]
  [--samples N] [--seed S]`;
- limpers are non-blind seats, and with the hero in the BB the SB folded;
- strength is equity against a random hand, so the limp range is the band below the
  open-raise range;
- bar 1's limped pot is the hero in the BB checking behind a fixed-range limper. A
  random-handed BB can only be matched by sampling, not to 1e-9;
- the PokerStrategy pages are about 470 KB each, not the 50 to 200 KB estimated in the
  question;
- seeds: one deal per seat, k and profile, shared by both antes and all actions.

**Rules out:**
- calling any answer GTO or solved;
- six-max in the live advisor, the overlay or `showdown advise`;
- other stacks, 3-bet pots, open-raised pots facing the hero, straddles and ICM;
- changing the heads-up tree, the live advisor or the Poker Now path;
- committing the PHH hands or the PokerStrategy pages;
- moving a bar after results are seen, except by a dated amendment.

**Amendment to DECISIONS 53 (2026-11-22, before Gate M was scored): study and training
only (SCOPE A13).** Ian's instruction of 2026-11-21 reached this session through the
master session after the entry was pushed. It narrows the scope and moves no bar.
- `showdown sixmax`, and the drill trainer and hand review that build on it, are study
  tools under DECISIONS 29. They run between sessions, on spots typed in or on completed
  hands.
- Ruled out: advice during a hand, screen reading, anything for ClubWPT (DECISIONS 13),
  and anything for a real-money table. README's "Not this" applies: never run showdown
  while a ClubWPT Gold client is open.
- The roadmap is `docs/plan-sixmax-trainer.md`.

---

### 54. The "standard" six-max profile, whose blinds defend like a modern chart; Gate M2 pre-registered (2026-11-22)

**Decided.** Ian answered on 2026-11-22, in the master session, which relayed it: option 3.
First a "standard" profile whose blinds defend like a modern chart, with a successor gate
against PokerStrategy, pre-registered before scoring. Then the drill trainer (DECISIONS
55), with "standard" as its default profile, grading by kind of action. Gate M's bar 3
FAIL stays as recorded. His reason: drills against blinds that fold about 73% would teach
over-stealing against today's players. The decisions below went to the master with
recommendations on 2026-11-22. This entry uses the recommended ones.

**The profile "standard":**
- **Copied from the fitted regular profile:** the limp range (open-raise and limp
  shares), the fold to an iso, the limp-reraise, both size slopes (0.038 per bb for
  limpers, 0.049 for players behind), and every response to a limp.
- **Replaced:** how players behind defend against the hero's raise (open or iso), by the
  hero's seat. Call / 3-bet, as shares of all hands, at the middle size:

  | Hero's seat | BB | SB | Non-blind players behind |
  |---|---|---|---|
  | UTG | 24 / 9% | 0 / 8% | 4 / 7% |
  | HJ | 27 / 10% | 0 / 9% | 4 / 7% |
  | CO | 33 / 11% | 0 / 11% | 4 / 7% |
  | BTN | 44 / 14% | 3 / 14% | none behind |
  | SB | 50 / 14% | none | none |

- **Where the numbers come from:** hand-picked from commonly published 100 bb six-max
  solver frequencies, with nothing downloaded. They are assumptions and the output says
  so. The band's ±10 points on calls covers some of their error.
- **The BB hero** has no one behind, so the table has no row for it.
- **The engine change:** a profile may carry per-seat rates, used when the hero sits in
  that seat. The fitted profiles have none, so their answers do not change.

**Gate M2,** recorded before the profile or the engine change exists. It passes when bars 1
to 3 pass. "Kind-stable" means that at all 9 band points the winning action is the same
kind (fold, limp or raise) as the best action, and for a review, the runner-up is that
kind too.
1. **Closed forms:**
   - Gate M bar 1's 21 checks still pass, unchanged;
   - the seat lookup: in a profile with every rate 0, except that the BB always 3-bets
     when the hero is UTG, the hero UTG with 72o folds to the 3-bet, so each open's EV is
     −X exactly; from the HJ, where no rate is set, every open's EV is the pot exactly.
2. **Directions,** on the standard profile's 34 charts (17 seat and limper shapes × 2
   antes), counting only classes kind-stable in both charts compared:
   - **the ante widens:** every class that enters (best action not fold) with no ante also
     enters with the 0.5 ante. At least 100 classes compared in all;
   - **more limpers, no new offsuit isos:** for BTN, SB and BB from 1 to 2 and 2 to 3
     limpers, and CO from 1 to 2, both antes: every offsuit class whose best action is a
     raise with one more limper is a raise with one fewer. At least 50 compared in all.
3. **PokerStrategy's opens** (DECISIONS 53's pages and parse rule): unopened pots, no ante,
   standard profile.
   - At each of UTG, HJ, CO, BTN and SB, at least 30 kind-stable classes are compared, and
     at least 85% of them agree with the chart on raise vs not raise.
   - Every disagreement is listed. The clear-only agreement (Gate M bar 3's rule) is
     reported beside it.

**The order:** this entry and SCOPE A14 committed and pushed; then the profile, the engine
change and the tests; Gate M2 scored once and recorded in GATES.md. A failing bar gets one
reproduce-and-fix, for a bug only, then the result stands.

**Decided without Ian (2026-11-22),** each the reversible option, pending his reply in
the master session:
- the numbers come from published solver frequencies by memory, not a downloaded chart;
- defence depends on the hero's seat, everything else is the regular profile's;
- the directions and the chart are judged on kind-stable classes with minimum counts.
  This follows the lesson of Gate M bar 3, where 6 clear classes decided the HJ.

**Rules out:**
- editing Gate M's record;
- calling "standard" solver output: its numbers are assumptions;
- tuning the standard profile toward PokerStrategy's chart after seeing results;
- moving a bar after results, except by a dated amendment.

**Amendment to DECISIONS 54 (2026-11-22, before Gate M2 was scored): the BB's defence is
fitted to a published chart.**
- **What changed.** Ian answered decision 1 through the master session: fit, don't
  hand-pick. Use a free published modern chart of blind defence by the raiser's seat,
  saved like the PokerStrategy pages. If none exists, keep the assumed numbers. He
  approved this source and fit rule in this session the same day. A Gate M2 run on the
  hand-picked numbers had started at e156792. It was stopped and its output never read,
  so Gate M2 is scored once, on the fitted profile. No bar moves.
- **The source:** VIP-Grinders, "Big blind defense", by João Mourato, published
  2026-06-15, https://www.vip-grinders.com/poker-strategy/big-blind-defense/. Saved on
  2026-11-22 to the gitignored `data/external/vip-grinders/big-blind-defense.html`
  (108,158 bytes, SHA-256
  `3563ffeccda76b78d8b5645391dab55a3d3b91e5b144107e4fb2e787930c9420`), never committed.
  - It is a different source from Gate M2's reference chart (PokerStrategy's opening
    ranges), so the gate is not graded against its own input.
  - Its table gives the BB's defend, 3-bet and flat shares against each opener's 2.5x
    open (BTN, CO, HJ, LJ/UTG, SB) as ranges. It assumes 100 bb six-max cash at NL50 to
    NL200 rake. It names no solver.
- **The fit:**
  - BB 3-bet = the midpoint of the 3-bet range for the hero's seat;
  - BB call = the midpoint of the flat range, moved from 2.5x to the engine's 3 bb
    reference by the regular profile's fitted slope (0.0493 per bb, so −2.46 points);
  - no rake adjustment;
  - a test parses the saved page and checks the profile against it.

  | Hero's seat | Page, 2.5x: 3-bet / flat | Fitted BB call / 3-bet |
  |---|---|---|
  | UTG | 4–6 / 21–24% | 20.0 / 5.0% |
  | HJ | 6–8 / 26–30% | 25.5 / 7.0% |
  | CO | 8–10 / 32–38% | 32.5 / 9.0% |
  | BTN | 11–13 / 41–45% | 40.5 / 12.0% |
  | SB | 13–16 / 42–46% | 41.5 / 14.5% |

- **Still assumed,** because the page has no numbers for them: the SB's defence and the
  non-blind players behind, as in the table above. They are labelled "assumed" in the
  output.
- **Decided without Ian:** the midpoint of each range; the move to 3 bb by the fitted
  slope; and ignoring the page's 3x row (its 2.5x to 3x drop is about 20 points, far off
  every other source here).

---

### 55. Step 2: a six-max drill trainer; Gate K pre-registered (2026-11-22)

**Decided.**
- Ian approved decisions 5 to 8 (sent with DECISIONS 54's) through the master session on
  2026-11-22.
- In this session he chose "Limit, build drills": Gate M's bar 3 stays a documented
  limit.
- "standard" (DECISIONS 54) is the default profile; the fitted ones stay selectable.
- Study only (SCOPE A13, A15). It runs on dealt practice spots, never on a live hand.

**The command:** `showdown sixmax drill [--count N] [--profile P] [--ante A] [--seed S]
[--samples N]`. `drill` takes the seat's place.

**A drill:**
- **The spot:** a seat and limper count drawn uniformly from the 17 allowed shapes. The
  ante is 0 or 0.5 at random unless `--ante` is given.
- **The hand:** a combo drawn uniformly from the 1,326 and shown as two cards; its class
  is graded. If the class's best action is a clear fold, it is shown with probability 1/5.
  Otherwise another hand is drawn for the same spot, so drills are not mostly 72o.
- **Before answering,** the trainer shows the spot, the hand and the profile's assumed
  ranges, as `showdown sixmax` prints them.
- **The answer:**
  - f folds; l limps, overlimps, completes or checks; c also checks; r raises; q quits;
  - the BB has no fold;
  - only the kind is asked.
- **The grade,** where a kind's EV is the EV of its best action:
  - **good:** the answer's kind is the best action's kind;
  - **marginal:** otherwise, but at one of the 9 band points the winning action is of
    the answer's kind;
  - **review:** otherwise. The bb lost is EV(best) − EV(the answer's kind) at the base
    point.
- **After answering,** the trainer shows the grade, the best action with its size, each
  action's EV, the tier and its reasons (as `showdown sixmax`), and the bb lost.
- **Speed:** one deal of 40,000 per spot and profile, kept for the session.
- **The log:** `data/drills/<start>.jsonl`, gitignored, flushed per line. Each line holds
  the time, spot, ante, profile, hand, answer, grade, best action, the EVs, the bb lost,
  the tier and the seconds taken.
- **The summary,** at the end: drills by grade, the bb lost in all, and the misses by seat
  and limper count.

**Gate K,** recorded before any trainer code. It passes when bars 1 to 3 pass. Two scripted
sessions run with seed 20261122, the standard profile and a random ante. The same seed gives
the same 300 drills in both.
1. **Grading.** Each drill's grade is checked against one worked out in the test from
   `sixmax.answer` for the same spot, hand, samples and seed, by the rule above.
   - **Session A** answers the best kind every time. All 300 must be graded good.
   - **Session B** answers a kind drawn uniformly (seed 7) from those allowed.
     - Every grade must match.
     - Every review's bb lost must match to 1e-9.
     - At least 30 good, 10 marginal and 30 review must occur, so each grade is tested.
2. **Speed.** In session A, the time from the start of a drill to its prompt, the first
   deal of each spot included: median at most 2 s, 95th percentile at most 5 s. No other
   heavy process runs meanwhile.
3. **The log.** Each session's log has exactly 300 lines, one per drill, with the answer
   given. The summary's counts by grade and its total bb lost equal the sums over the
   lines, the bb to 1e-9.

**Reported, not gated:** the share of drills whose best action is a clear fold, and the
grades in session B by tier.

**Rules out:** live use of any kind; ClubWPT; grading the size (a later decision, if
wanted); committing drill logs.

---

### 56. R for an out-of-position raiser falls from 0.90 to 0.75; Gate M3 pre-registered (2026-11-22)

**Decided.** Ian chose this on 2026-11-22, in the master session, which relayed it.
- **Why:** under "standard" the SB still opens every hand (Gate M2, bar 3). R 0.90 for a
  raiser out of position was the suspect.
- **The change:** R for the hero who raised and is out of position postflop goes from
  0.90 to 0.75. The other three R values (1.00, 0.85, 0.75) stay, and so does the band
  (every R ±0.1).
- **The record stands:** Gate M2's bar 3 FAIL stays as recorded.

**Where 0.75 comes from, and how firm it is.**
- Gate Q's flop solves (GATES.md) measured R for the out-of-position player in a
  heads-up raised pot. They did not settle: the open pot's R drifted from 0.72 to 0.63
  at 25 bb, and from 0.78 to 0.68 at 100 bb, between the two rounds.
- So 0.75 is a value inside a measured range, not a settled one.
- Gate Q measured the caller, the BB defending. A raiser usually realises more than a
  caller, so 0.75 is likely on the low side for a raiser. The band's −0.1 and +0.1 cover
  0.65 to 0.85.

**What it changes:**
- every profile's answers wherever the hero raises and someone left in the pot acts
  after them postflop: the SB and BB raising, and early seats called by a later seat;
- not Gate M's, M2's or K's records. Their slow tests now pin R at 0.90, the value they
  were scored at, so they still reproduce;
- `showdown sixmax` and the drills use 0.75 from this entry on.

**Gate M3,** recorded before the change is coded. It is Gate M2's bars on the standard
profile, at the new R. It passes when bars 1 to 3 pass.
1. **Closed forms:**
   - Gate M bar 1 and Gate M2 bar 1 still pass, unchanged;
   - **the new R:** the hero in the BB raises one limper whose range is KK and who always
     calls; nobody else acts. EV = 0.75 × M[hero, KK] × (0.5 + 6 × ante + 2X) − (X − 1),
     to 1e-9, for each of AA, KK, A5s and 72o and every raise size, at both antes.
2. **Directions,** on the standard profile's 34 charts, kind-stable classes only (DECISIONS
   54's definition):
   - the ante widens: at least 100 compared, no violation;
   - more limpers, no new offsuit isos: at least 50 compared, no violation.
3. **PokerStrategy's opens,** unopened, no ante, standard profile: at each of UTG, HJ, CO,
   BTN and SB, at least 30 kind-stable classes compared, and at least 85% agree on raise
   vs not raise. Disagreements are listed, and the clear-only agreement reported.

**Reported, not gated:** the same bar 3 for the regular profile at the new R, and how many
classes the SB opens under each profile.

**The order:** this entry, committed and pushed. Then the change, the tests, and the old
gates pinned to 0.90. Gate M3 is scored once and recorded. A failing bar gets one
reproduce-and-fix, for a bug only.

**Decided without Ian:**
- the gate name, M3, and its bars, which copy M2's;
- the new closed form, the BB raising a fixed-range limper. It is the only spot where the
  raiser is out of position and the outcome can be worked by hand;
- pinning the older gates' slow tests to 0.90.

**Rules out:** changing any other R or the band here; editing Gates M, M2 or K's records.

**Amendment to DECISIONS 56 (2026-11-22): Gate M3 was not scored; the next entry replaces
it.**
- **What happened.** While Gate M3's run was under way at 7ced07c, Ian answered in the
  master session, which relayed it:
  - make both fixes together under one pre-registered entry and one re-gate: R 0.75 here,
    and the standard profile's limpers taken from the fitted loose-passive profile
    instead of the regular one;
  - do it in a fresh session, not this one.
- **What was done.** The run was stopped and its output never read. Gate M3 stays
  unscored and is superseded by that next entry. R 0.75 stays in the code meanwhile. Until
  the re-gate, answers wherever the hero raises out of position are ungated.
- **No bar moved.** Gates M, M2 and K's records stand, and their slow tests still pin R at
  0.90.

---

### 57. Both six-max fixes: R 0.75 for an out-of-position raiser, and the standard profile's limpers from loose-passive; Gate M4 pre-registered (2026-11-22)

**Decided.**
- Ian chose both fixes under one entry and one re-gate (DECISIONS 56's amendment).
- The up-front decisions went to the master session on 2026-11-22. Ian answered "all
  recommended", relayed by the master. This entry uses those answers.
- Gate M2's bar 3 FAIL, Gate M3 (registered, never scored) and Gates M and K stay as
  recorded.

**Fix (a): R for an out-of-position raiser is 0.75.**
- It has been in `sixmax.py` since 7ced07c (DECISIONS 56).
- The other three R values (1.00, 0.85, 0.75) stay, and so does the band: every R ±0.1,
  fold rates ±10 points.
- How firm is 0.75? Gate Q's flop solves never settled. The open pot's R moved from 0.72
  to 0.63 at 25 bb and from 0.78 to 0.68 at 100 bb between rounds. They measured an
  out-of-position *caller*. A raiser usually realises more, so 0.75 is likely on the low
  side for one. The band covers 0.65 to 0.85.

**Fix (b): the standard profile's limpers come from the fitted loose-passive profile.**
- **Taken from loose-passive:** the limpers' own five rates:
  - open-raise 17.5% and limp 30.7%, so the limp range is the 31% of hands just below the
    top 17.5%;
  - fold to an iso 39%;
  - limp-reraise 3.5% of the limp range;
  - fold slope 0.037 per bb.
- **Unchanged:**
  - players behind's responses to the hero's limp stay regular's: raise 19%, overlimp
    8%, SB raise 12% and complete 33%, BB raise 11%;
  - the seat defence stays as DECISIONS 54 had it: the BB fitted to VIP-Grinders, the SB
    and the others assumed;
  - the players-behind slope (0.049) stays regular's, including the BB's move from 2.5 bb
    to the 3 bb reference.
- **Why:** 2009 regulars limp only 2.9% of hands (44, K6s, A4o, K8o), nothing like the
  limpers at Ian's tables (Ian, 2026-11-22).
- **The output** labels the five rates "fitted (loose-passive)".

**What it changes:**
- Unopened pots change through R alone. The BTN's unopened answers cannot change: it is
  in position against both blinds (R 1.00), and there are no limpers.
- Pots with limpers change under "standard" only. The fitted profiles' limpers are
  untouched.
- `showdown sixmax` and the drills use both fixes from this entry on.
- **Old gates keep reproducing.** The slow tests of Gates M2 and K pin the standard
  profile as it was scored, with regular's limpers, as well as R 0.90.
  `load_profiles(standard_limpers=...)` picks the source. Gate M2's fast check of the
  profile is pinned the same way.

**Gate M4,** recorded before fix (b) is coded. It replaces Gate M3. It passes when bars 1
to 3 pass. "Kind-stable" is DECISIONS 54's definition.
1. **Closed forms:**
   - Gate M bar 1's 21 checks and Gate M2 bar 1 (the seat lookup, and the M2 profile check
     on the profile as scored) pass unchanged;
   - **the new R:** the hero in the BB raises one limper whose range is KK and who always
     calls; nobody else acts. EV = 0.75 × M[hero, KK] × (0.5 + 6 × ante + 2X) − (X − 1),
     to 1e-9, for AA, KK, A5s and 72o, every raise size, both antes (Gate M3's check);
   - **the profile:** "standard" equals regular, except the seat defence (as Gate M2
     checks) and the five limper rates, which equal loose-passive's exactly.
2. **Directions,** on the standard profile's 34 charts at the new R, kind-stable classes
   only:
   - the ante widens: at least 100 compared, no violation;
   - more limpers, no new offsuit isos (BTN, SB and BB from 1 to 2 and 2 to 3 limpers, CO
     from 1 to 2, both antes): at least 50 compared, no violation.
3. **PokerStrategy's opens** (DECISIONS 53's pages and parse rule), unopened, no ante,
   standard profile:
   - at each of UTG, HJ, CO and SB, at least 10 kind-stable classes are compared, and at
     least 85% of them agree on raise vs not raise;
   - the minimum of 10 sits just under the fewest Gate M2 saw (UTG 12, HJ 15, CO 26). There,
     the ±10-point fold band, not R, limits kind-stability;
   - **the BTN is not scored.** Its chart must be identical, in every class's best action,
     tier, best size and kind-stability, to the chart under Gate M2's profile and R 0.90.
     If it is not, bar 3 fails. Its agreement is reported;
   - every disagreement is listed, and the clear-only agreement reported.

**Reported, not gated:**
- bar 3 for the regular profile at the new R;
- how many classes the SB opens under each profile;
- how many classes isolate, under the standard profile, by limped spot and ante.

**The order:**
1. This entry and SCOPE A16, committed and pushed.
2. Fix (b), `test_gate_m3*.py` renamed to `test_gate_m4*.py` and extended, and Gates M2
   and K pinned.
3. Gate M4 scored once and recorded in GATES.md. A failing bar gets one
   reproduce-and-fix, for a bug only, then the result stands.

**Rules out:**
- changing any other R, the band or the seat defence here;
- tuning either fix after seeing results;
- editing the records of Gates M, M2, M3 or K.

---

### 58. Step 3: six-max hand review by spot; Gate W pre-registered (2026-11-22)

**Decided.**
- Ian approved decisions 6 to 11 ("all recommended", relayed by the master session) on
  2026-11-22.
- Step 3 of `docs/plan-sixmax-trainer.md`. Study only (SCOPE A13, A17):
  - completed hands only, never during a session;
  - never ClubWPT, except a file the site itself exports (DECISIONS 13);
  - hand histories are never committed.

**The command:** `showdown sixmax review PATHS... --player NAME [--profile P] [--samples N]
[--seed S]`.
- PATHS are files or folders of PHH (`.phh`) and PokerStars text (`.txt`), read by
  `hh/parse.py`'s `load` (DECISIONS 25).
- There is no Poker Now parser here. That is Phase 11, which needs one real downloaded log
  first.
- It prints a report and writes no file.

**The analyzer keeps more of each hand.** `HandRecord` gains each player's ante and the
preflop actions in order: who, fold, check, call or raise, and the amount. Seats come from
pokerkit's order: with six players, p1 SB, p2 BB, p3 UTG, p4 HJ, p5 CO, p6 BTN.

**What is graded.** For each hand the named player is in, the player's first preflop
decision is graded when it fits an engine spot. Otherwise it is skipped, and counted under
the first of these causes that applies:
1. **not six-handed:** not exactly six players dealt in;
2. **blinds:** p1 does not post half of p2's blind, or anyone else posts a blind or
   straddle;
3. **ante:** antes are not all equal, or not 0 or 0.5 bb;
4. **stack depth:** the effective stack is outside 60 to 150 bb. That is the smaller of the
   player's starting stack and the largest other one;
5. **no decision:** the player never acted preflop (a walk);
6. **raised before you:** someone bet or raised before the player's first action;
7. **the SB completed:** the player is the BB and the SB called;
8. **short all-in before you:** someone called for less than 1 bb;
9. **too many limpers:** more limpers than the engine allows from that seat (SB and BB at
   most 3);
10. **cards unknown:** the player's hole cards are not in the history.

The spot is the seat, the limpers ahead (non-blind calls of 1 bb) and the ante. The answer's
kind:
- a fold is fold;
- a call or a check is limp (limp, overlimp, complete or check);
- a raise is raise, with its size, raise-to in bb.

**The grade:**
- The class of the player's hand is graded against `sixmax.answer` for that spot and
  profile ("standard" by default), as a fresh answer would give it.
- The rule is DECISIONS 55's:
  - **good:** the answer's kind is the best action's kind;
  - **marginal:** otherwise, but the answer's kind wins at some band point;
  - **review:** otherwise.
- The bb lost is EV(best) − EV(the answer's kind).
- The size is shown beside the engine's best size, not graded.
- Answers are cached per seat, limpers, ante and class. The deal's random state is put
  back before each one, as the drills do, so each equals a fresh answer.

**The report:**
- **Coverage:** files read, hands parsed and failed, hands with the player, decisions
  graded, skips by cause.
- **Grades by tier:** clear, close and review, each by good, marginal and review.
- **bb lost:** in all, and on clear spots.
- **Leaks:** the review-graded decisions, grouped by seat, unopened or limped, and the
  answer's kind → the best kind. A group needs at least 3 decisions.
  - The top 3 groups by bb lost are shown, each with its count and bb.
  - Each lists up to 5 hands, largest bb lost first: the file and hand, the cards, the
    spot, and the answer beside the best.

**Gate W,** recorded before any review code or fixture. It passes when bars 1 to 3 pass.
1. **Classification,** on a fixture written and labelled by hand before the classifier
   exists, in `tests/fixtures/sixmax_review/`, committed in its own commit before any review
   code:
   - at least 40 hands, all fictional, with the player "Hero";
   - at least 2 of them in PokerStars text, the rest PHH;
   - for every hand, the spot (seat, limpers, ante), the hand class, the kind and the raise
     size, or the skip cause, must match the labels exactly;
   - the fixture holds every seat graded at least once, 0, 1, 2 and 3 limpers, both antes,
     each kind, and every skip cause.
2. **Grading,** on every graded fixture decision plus 300 graded Pluribus decisions drawn
   with seed 20261122:
   - each must equal one worked out in the test from a fresh `sixmax.answer` (same spot,
     class, standard profile, 40,000 deals, seed 0) by DECISIONS 55's rule;
   - the grade, best action and tier must match, and the bb lost to 1e-9.
3. **Real hands:** Pluribus's decisions in the 10,000 Pluribus hands (phh-dataset,
   DECISIONS 25, pinned there), standard profile:
   - at least 99% of hands parse, with failures counted;
   - every hand with Pluribus is graded or skipped under a named cause. Graded plus
     skipped equals hands with Pluribus;
   - at least 2,000 decisions are graded;
   - the report's counts by tier and grade, its bb lost (in all and on clear spots), and
     each leak's count and bb equal the sums over the decisions, the bb to 1e-9.

**Reported, not gated:**
- the skips by cause;
- the grades by tier;
- the run time;
- Pluribus's top 3 "leaks". Pluribus is a strong bot, so they mostly show the engine's
  limits.

**Not a gate bar:** the plan's check on Ian's own hands. That means coverage, and reviewing
5 hands per leak to say whether it is real. It waits until he has a file from an allowed
source.

**The order:**
1. This entry and SCOPE A17, committed and pushed.
2. The fixture and its labels, committed.
3. The analyzer change, the classifier, the report, the CLI and the tests.
4. Gate W scored once and recorded. A failing bar gets one reproduce-and-fix, for a bug
   only.

**Decided without Ian,** each the reversible option:
- leaks group review grades only: a marginal answer wins somewhere in the band, so it is
  not a leak;
- the order of the skip causes, and the 60 to 150 bb window;
- answers cached per class, equal to a fresh answer;
- the gate's letter, W.

**Rules out:**
- reading hands during a session, or watching a folder;
- any ClubWPT file not exported by the site;
- committing any real hand history, Pluribus's included;
- the Poker Now parser;
- grading raise sizes;
- a profile per table or per player;
- other table sizes.

---

### 59. The pivot: an exploit trainer and a leak finder; the live Poker Now path is parked (2026-11-26)

**Decided.** Ian, 2026-11-26, in plan mode, then approving the plan
(`~/.claude/plans/as-it-stands-i-logical-cupcake.md`):
- live play is out unless it can run on sites that allow it;
- the product becomes an exploit trainer and a leak finder now, with a bot later.

The trainer works like GTO Wizard's: you are dealt a spot, pick an action, and get a
grade. Exploit, not GTO: each spot names the opponents' player types and their traits, and
the best action is the best one against those types. Every grade explains why, and leaks
found in your hands point to lessons.

**The product, first release** (Ian's answers of 2026-11-26):
- **Grades:** GTO Wizard's scale (Best, Correct, Inaccuracy, Wrong, Blunder), by EV lost as
  a % of the pot. An answer that wins somewhere in the engine's assumption band never grades
  below Correct.
- **Player types,** named and set by role: one type for the limpers, another for the players
  behind and the blinds. Each type has a trait card.
- **Spots:**
  - unopened and limped six-max pots;
  - pots facing one open raise;
  - heads-up push/fold with types, as tournament study (no ICM; ICM is a later item).
- **Teaching:** a "why" line on every grade; leaks point to lesson cards.
- **Hand files:** PokerStars-format exports, read after the session.

**The live Poker Now path is parked.**
- Phase 10's loop (`live/screen.py`, DECISIONS 52) stays in the code and its tests stay in
  the gate. Nothing is deleted.
- Spike S1 (DECISIONS 51), Gate H and the live goal of `docs/plan-live-advisor.md` leave the
  roadmap. Phase 11's Poker Now log parser leaves it too, unless Ian has a downloaded Poker
  Now log to review.
- Picking any of them back up needs its own entry.

**SCOPE A13 is amended (SCOPE A18).** Post-session review of hand files from sites whose
terms let you download them is in scope.
- Never live, never during a hand, never a folder watched during a session.
- ClubWPT stays under DECISIONS 13: only a file the site itself exports.
- Hand histories are never committed.

**Automatic play comes later (SCOPE A19),** only on venues that allow bots, such as
bot-vs-bot APIs or a self-hosted play-money table. Real-money sites ban bots in their
terms. It gets its own entry when its turn comes; until then no code plays by itself
anywhere.

**The roadmap** is `docs/plan-sixmax-trainer.md`, rewritten as the product roadmap. Steps,
each pre-registered with its own entry and gate before its code:
1. grades and player types in the engine and the CLI drill, plus push/fold with types;
2. pots facing one open raise, as an engine extension;
3. the trainer page in `showdown play`;
4. the leak finder on PokerStars exports, with opponent typing, a report tab and lesson
   cards.

**Up-front decisions (2026-11-26).** Ian approved 12 new ones in this session, all as
recommended. The same list went to the master session. Each is fixed in the entry of the
step it belongs to.

**Rules out:**
- live advice, screen reading or any play during a hand, on any site;
- automatic play anywhere before its own entry;
- ClubWPT code (DECISIONS 13, 29);
- committing hand histories, drill logs or `data/external/`.

---

### 60. Trainer step 1: GTO Wizard's grade scale, player types by role, and push/fold with types; Gate Y pre-registered (2026-11-27)

**Decided.** Step 1 of the roadmap (DECISIONS 59). Ian's answers of 2026-11-26 set the
scale and the types. His 12 up-front decisions, approved in the session that day, set the
type rules (decisions 1 to 4). SCOPE A20. Study only, as A13 and A18.

**The grade:** `sixmax.grade(answer, action, pot)`. Here lost = EV(best) − EV(action) at the
base point, in bb, and pct = 100 × lost / pot. The pot is everything in before the hero
acts: antes, blinds and limps (`Spot.pot`).
- **Best:** lost ≤ 1e-9; or the tier is close, every band winner is of the best action's
  kind ("only the size is close"), and the action is of that kind.
- **The band floor:** otherwise, an action that wins at some band point is **Correct**.
- **Otherwise by pct:** Correct ≤ 3; Inaccuracy ≤ 10; Wrong ≤ 25; Blunder above 25.
- The cut-offs change only by a dated amendment.

**Player types.** Seven keys: standard, nit, tag, lag, maniac, weak-tight, station, shown
as Standard, Nit, TAG, LAG, Maniac, Weak-tight rec and Calling station.
- **The fit** is a spike, `spikes/2026-11-27-phh-sixmax-types.py`. It reads DECISIONS 39's
  zip, pinned by SHA-256, with DECISIONS 53's filters and counts 1 to 6 unchanged, plus one
  count for step 2:
  - **7. The opener facing one 3-bet:** a player whose first raise opened a pot with no
    limpers, at its next action with exactly two raises in: fold, call, 4-bet.
- **The groups,** over players with at least 500 such hands, by their own VPIP and PFR:
  - aggressive, PFR ≥ VPIP / 2: Nit VPIP < 16%; TAG 16% to < 28%; LAG 28% to < 40%;
    Maniac 40% or more;
  - passive, PFR < VPIP / 2: Weak-tight rec VPIP < 24%; Calling station 24% or more;
  - **all:** every such player, pooled, for the ratios.
- **Rates:** DECISIONS 53's rules for each of the 17 rates, plus count 7's three shares,
  pooled within the group.
  - A rate with fewer than 1,000 chances in a group, or a slope with fewer than three
    buckets of 1,000, takes the "all" group's value. It is labelled "pooled".
- **Output:** `data/sixmax_types.json` and `docs/sixmax-types.md`, aggregates only,
  credited to the dataset (CC BY 4.0). The spike runs once on AC. A crash or a wrong count
  gets one fix, then it stops.
- **The trait card** shows the group's fitted numbers: VPIP, PFR, limp % (limp first in),
  fold to iso (to the 4+k iso), 3-bet % (a non-blind player behind, facing an open) and BB
  defence (call plus 3-bet facing a 3 bb open). They are labelled as 2009 online groups.

**A spot's profile is composed** from a limper type and a table type:
`sixmax.compose(limpers, table)`.
- **Limper rates** (open-raise, limp, fold to iso, limp-reraise, its size slope): the limper
  type's own fitted rates. For "standard", they are standard's (loose-passive, DECISIONS 57).
- **Table rates** (the 12 others):
  - standard's value, its per-seat defence included, times the table type's ratio, the
    type's rate over the "all" rate. "standard" has every ratio 1;
  - clipped so that a 3-bet share t ≤ 1 and a call share c ≤ 1 − t, and likewise for the
    responses to a limp (raise x ≤ 1, overlimp or complete ≤ 1 − x, BB raise ≤ 1).
- **compose("standard", "standard")** is the standard profile itself, so every old answer
  is unchanged.
- **Deal seeds.** A composed profile's deals are seeded by its limper type: by "standard"
  when the limpers are standard, so they equal the standard profile's deals. The deal does
  not depend on the table type. `Profile` gains a `deal_name`; when it is empty, the name
  is used, as now.
- The old profiles (standard, tight, regular, loose-passive) stay selectable.

**The CLI:**
- `showdown sixmax SEAT HAND --limpers-type T --table-type T` composes the profile, prints
  both trait cards, and otherwise prints as now. `--profile` keeps its meaning when no type
  is given.
- **The drill,** `showdown sixmax drill [--limpers-type T] [--table-type T]`:
  - each drill draws the limper type and the table type uniformly from the seven, unless
    fixed;
  - the answer is an action with its size: f, l (or c), or a raise size typed as a number;
  - it is graded on the new scale;
  - the log adds the action, the label, the % lost and both types.
- **After each answer,** a deterministic "why" built from the engine's numbers:
  - for a raise: how often everyone folds, how often it is called and the hero's equity
    against the callers, how often it is re-raised, and the risk against the pot (the fold
    share a pure bluff needs);
  - for a limp: how often someone raises behind (the floor), and the equity at the flop;
  - then the chosen action's EV and its loss in bb and % of the pot;
  - then "Against a standard player you'd …": the best action under compose("standard",
    "standard"), with its EV.
- **Gate K's kind-only drill** stays, as `run(..., sizes=False)` with no types, and Gate K's
  slow test uses it.

**Push/fold with types,** labelled "tournament-style, no ICM":
- **A type's width:** the villain SB jams, or the villain BB calls, the top w% of hands by
  equity against a random hand (DECISIONS 37's read). Here w = min(100, 100 × Nash's share
  × the type's ratio). For jams the ratio is the open-raise ratio; for calls it is the BB
  defence ratio (call plus 3-bet). "standard" has ratio 1: Nash's width.
- **The answer** is DECISIONS 37's exact best response, with Nash's action shown beside it.
- **The band** is w − 10, w and w + 10 points of hands, clipped to 1 to 100. An action that
  is best at one of them is never below Correct.
- **The pot before acting** is 1.5 bb for the SB and S + 1 for the BB facing a jam.
- **The CLI:** `showdown pushfold exploit S --villain-type T --hero sb|bb`.

**Gate Y,** recorded before the spike, the grade or the types exist. It passes when bars 1
to 5 pass. "Kind-stable" is DECISIONS 54's definition.
1. **The grade rule.** A scripted drill session:
   - 300 drills, seed 20261127, random types, random ante;
   - the answer drawn uniformly from the spot's actions, sizes included (seed 7);
   - each drill's label, bb lost (to 1e-9) and % lost equal ones worked out in the test
     from a fresh `sixmax.answer` under `compose` for the same spot and class, by the rule
     above, coded separately in the test;
   - each of the five labels occurs at least 5 times;
   - unit tests also hit each branch and the cut-offs at exactly 3, 10 and 25%.
2. **The band floor.** In that session, every answer that wins at some band point is Best
   or Correct. At least 10 such answers are not the base point's best.
3. **Type directions,** kind-stable classes only:
   - **steals:** unopened CO, BTN and SB, both antes, standard limpers:
     - every class whose best is a raise against a LAG table is a raise against a Nit table;
     - every class whose best is a raise against a Calling-station table is a raise against
       a Weak-tight rec table;
     - each of the two pairs has at least 50 classes compared in all, and the Nit (and
       Weak-tight rec) table raises at least as many classes;
   - **isos, against limpers who fold less:** for each of the six fitted limper types, at
     CO with 1 limper and BTN with 1 and 2, both antes, standard table. Lowering only the
     limpers' fold to an iso by 10 points (clipped at 0) adds no offsuit class whose best is
     an iso. At least 50 classes compared in all.
4. **Push/fold.** For each of the seven types, at 5, 10, 15 and 20 bb, with the hero as SB
   and as BB:
   - the best response's EV and Nash's EV against the type's read equal
     `cfr.best_response` and `cfr.policy_value` on the compiled tree, to 1e-9;
   - the chart equals the tree's best response wherever the choice is not a tie.
5. **Old gates unchanged.**
   - The slow tests of Gates M, M2, M4, K and W are re-run once and pass. Gate K is pinned
     to the kind-only drill, as above. Their profiles and R stay pinned as before.
   - compose("standard", "standard") equals `load_profiles()["standard"]` in every rate,
     source and per-seat value, and its deal equals the standard profile's.

**Reported, not gated:**
- the groups' sizes and trait cards;
- the drill's speed with types (median and 95th percentile);
- how many classes steal or isolate per type;
- the session's labels by tier.

**The order:**
1. This entry and SCOPE A20, committed and pushed.
2. The spike, run once.
3. The grade, the composition, the CLI, the drill, push/fold with types, and the tests.
4. Gate Y scored once and recorded in GATES.md. A failing bar gets one reproduce-and-fix,
   for a bug only, then the result stands.

**Decided without Ian (2026-11-27),** each the reversible option:
- a tie with the best (within 1e-9) is Best;
- the type keys, and the fallback to the pooled rate where a group is thin;
- the trait card's numbers are the group's fitted 2009 rates;
- the steal and iso directions above, and the gate's letter, Y;
- push/fold is taught on the trainer page in step 3; the CLI gets `--villain-type` on
  `pushfold exploit`;
- the "why" line's contents.

**Rules out:**
- calling any answer GTO;
- per-seat open widths for the limper types (step 2 handles openers);
- tuning a type or a cut-off after results are seen, except by a dated amendment;
- committing the PHH hands or drill logs.

---

### 61. Trainer step 2: pots facing one open raise; Gate Z pre-registered (2026-11-27)

**Decided.** Step 2 of the roadmap (DECISIONS 59), an extension of the six-max engine.
Ian's up-front decisions 5 to 8 of 2026-11-26 fix the opener's ranges, the hero's sizes, the
opener's answer to a 3-bet and the players behind. SCOPE A21. Study only, as A13 and A18.
Gate Y passed at 6afc847, so the grade and the types are DECISIONS 60's.

**The spot.**
- The opener's seat (UTG, HJ, CO, BTN or SB) and the open: 2.5 or 3 bb.
- The hero is any seat after the opener; everyone between them folded; there are no
  limpers. Stacks are 100 bb, blinds 0.5/1, and the ante is 0 or 0.5 from everyone.
- **The opener's type** and **the table type** (everyone behind the hero), each one of
  DECISIONS 60's seven.
- **The pot before acting:** 6 × ante + 1.5 + the open, less 0.5 when the SB opened.

**The opener's range** is the top w of hands by strength (DECISIONS 53's order):
- w = min(100%, base × the type's open-raise ratio);
- base, assumed, labelled so: UTG 15%, HJ 19%, CO 27%, BTN 45%, SB 40%.

**The hero's actions:**
- fold (the BB can fold too);
- call;
- 3-bet to 3× the open or to 4× the open;
- jam (100 − ante in all).

**What the others do:**
- **Players behind** use the table type's composed profile (`compose("standard", table)`),
  with the rates it has against an open from the opener's seat (its per-seat defence for
  that seat).
  - After the hero's call, each one in seat order squeezes with its top t (its 3-bet share
    against an open), overcalls with the next c = c_ref − slope × (open − 3) − δ, and folds
    the rest. The first squeeze is the re-raise the hero faces; the opener and everyone
    else then fold.
  - After the hero's 3-bet or jam, each one cold 4-bets (or calls the jam) with its top 2%
    and folds the rest.
- **The opener:**
  - after a call, it is in the pot;
  - after the hero's 3-bet to X (and players behind fold), it 4-bets with the top f of its
    open range, calls with the next c(X) = max(0, c − s × (X − 3 × open) − δ), clipped to at
    most 1 − f, and folds the rest;
    - under standard, f = 12% and c = 33% (assumed, decision 7);
    - a type's f and c are standard's times its fitted opener_4bet and opener_call ratios
      (DECISIONS 60's count 7);
    - s is standard's players-behind slope, 0.049 per bb, for every type;
  - facing the jam, it calls with its top f and folds the rest.
- **A 4-bet is all-in.** The hero stacks off or folds, whichever its exact equity against
  the 4-bet range says is worth more, as now.

**Payoffs,** in bb against folding, as DECISIONS 53:
- everyone folds: the hero wins the pot;
- to the flop: R × share × pot − the chips the hero added;
  - R after the hero's 3-bet is called: raised in position 1.00, out of position 0.75;
  - **R after the hero's call** is the limped pot's: 0.85 in position, 0.75 out. The hero
    has no initiative either way;
- a re-raise: stack off or fold;
- the jam called: M[hero, the caller's class] × the all-in pot − the hero's chips.

**The band and the tier** are DECISIONS 53's: R ± 0.1 × δ = −0.10, 0, +0.10, where δ moves the
overcalls of players behind and the opener's calls against a 3-bet. The jam cannot fold to
a re-raise, so its no-stack-off value is its own.

**The grade** is DECISIONS 60's, on the pot above. Calling is its own kind; both 3-bets and
the jam are of the raise kind.

**The engine change.**
- A spot type for facing an open, its deal and outcomes, and `kind` for "call" and "jam".
- An outcome may carry its own re-raise ranges and an all-in flag.
- None of this changes an unopened or limped answer.

**The CLI:** `showdown sixmax SEAT HAND --opener SEAT [--open 2.5|3] [--opener-type T]
[--table-type T] [--ante A]`.

**Gate Z,** recorded before any code for this step. It passes when bars 1 to 3 pass.
"Kind-stable" is DECISIONS 54's definition, with call as its own kind.
1. **Closed forms,** worked by hand in the test from the matrix, to 1e-9, on AA, KK, A5s and
   72o, both antes, both open sizes:
   - **everyone folds:** the opener folds every hand to a 3-bet and to a jam, and nobody
     behind continues. Each 3-bet's EV and the jam's EV equal the pot before acting, for
     the hero on the BTN against a CO open and in the BB against an SB open;
   - **a call heads-up:** the hero in the BB calls an SB open from a range of KK.
     EV = 0.85 × M[hero, KK] × (6 × ante + 2 × open) − (open − 1);
   - **a 3-bet called:** the hero on the BTN 3-bets a CO opener whose range is QQ and who
     always calls; the blinds fold. EV = 1.00 × M[hero, QQ] × (6 × ante + 1.5 + 2X) − X;
   - **a 4-bet:** the same, but the opener's range is AA and it always 4-bets. KK folds
     (EV = −X); AA stacks off: EV = M[AA, AA] × (2 × (100 − ante) + 6 × ante + 1.5) − (100 − ante);
   - **the jam called:** the hero on the BTN jams into a CO opener whose range is AA and who
     always calls. EV = M[hero, AA] × (2 × (100 − ante) + 6 × ante + 1.5) − (100 − ante).
2. **Directions,** kind-stable classes only. Table standard, open 2.5, both antes, at five
   spots: CO opens and the hero is on the BTN or in the BB; the BTN opens and the hero is in
   the SB or the BB; UTG opens and the hero is in the BB.
   - **Fold more against a Nit:** every class that continues (best not fold) against a Nit
     opener also continues against a LAG opener, and against a Maniac opener.
   - **3-bet less against a Nit, wider for value against a LAG or a Maniac:** the classes
     whose best is a 3-bet or the jam number no more against a Nit opener than against a LAG
     opener, and no more than against a Maniac opener.
   - At least 100 classes compared for each pair.
3. **The chart.** PokerStrategy's vs-open ranges, already saved under DECISIONS 53 (lessons
   2256 and 2257; never committed).
   - **Spots:** the hero on the BTN against UTG, HJ (their MP) and CO opens; the hero in the
     SB against UTG, HJ, CO and BTN opens. A 3 bb open, no ante, standard opener and table.
   - **The chart's action for a class** is the one covering most of its combos: fold when
     most are outside the defending range, else call or 3-bet. Classes split evenly are
     left out. Each list's combo count must equal the page's "#N".
   - **The bar:** on classes kind-stable in our chart, pooled over the 7 spots, at least 85%
     agree on continue vs fold, with at least 100 compared.
   - Every disagreement is listed. The three-way agreement (fold, call, 3-bet) and each
     spot's agreement are reported.

**Reported, not gated:**
- each opener type's range width by seat;
- how many classes 3-bet against each opener type;
- the time to answer one spot.

**Old gates:** the change cannot move an unopened or limped answer. Gate Y's slow test and
Gates M4 and W are re-run once and must pass unchanged.

**The order:**
1. This entry and SCOPE A21, committed and pushed.
2. The engine extension, the CLI and the tests.
3. Gate Z scored once and recorded in GATES.md. A failing bar gets one reproduce-and-fix,
   for a bug only, then the result stands.
4. `docs/sixmax-preflop.md`: what facing an open can be trusted for.

**Decided without Ian (2026-11-27),** each the reversible option:
- R after a call is the limped pot's;
- the opener's call share falls with the 3-bet's size at standard's slope, for every type;
- the opener calls a jam with its 4-bet range only;
- the hero may fold in the BB;
- the gate's spots and minimum counts, and the letter Z.

**Rules out:**
- 3-bet pots where the hero opened and faces a 3-bet, and squeezes over a caller;
- limped-then-raised pots (an iso facing the hero);
- calling any answer GTO;
- committing the PokerStrategy pages.

**Result (2026-11-27): Gate Z FAIL, bar 3 only** (GATES.md).
- Bars 1 and 2 pass. Bar 3: 79.9% of 134 stable classes agree with PokerStrategy on
  continue vs fold, under the 85% bar. Every miss is a 3-bet where the chart folds.
- A hand-worked 72o matched the engine to 1e-15, so it is the model, not a bug: the
  opener's 55% fold to a 3× 3-bet, its call share falling 0.049 per bb of extra size, and R
  1.00 for any hand.
- The result stands, and bar 3's test is a strict xfail. Ian chooses between a fix entry
  (a flat call share across sizes and R by hand, re-gated as Z2) and a documented limit.
  Until he answers, the documented limit is in force (the reversible option): the trainer
  page labels facing-an-open answers with it.

---

### 62. Trainer step 3: the trainer page in `showdown play`; Gate U pre-registered (2026-11-27)

**Decided.** Step 3 of the roadmap (DECISIONS 59). It is a local page, like the push/fold
trainer (DECISIONS 12, 23), on 127.0.0.1 only. Study only, as A13 and A18. SCOPE A22.

**The server.**
- `App.create` takes `{"game": "trainer"}` with optional filters and a seed.
- It reuses `/api/hand` (the next drill), `/api/act` (an answer) and `/api/summary`.
- New routes:
  - `GET /trainer`, the page, with the launch token as the index page has it;
  - `GET /api/lesson?id=`, a lesson card's text.
- The index page links to the trainer.

**The session,** `SixmaxSession` in `bot/sessions.py`:
- **Families,** drawn uniformly from those allowed:
  - **six-max:** unopened and limped spots, dealt by the drill's `Trainer`;
  - **facing an open:** by the same trainer, extended. The (hero, opener) pair is uniform
    over the 15 allowed; the open is 2.5 or 3; the opener and table types are drawn;
  - **push/fold:** a depth uniform from 2 to 20 bb, the hero SB or BB, a villain type,
    graded by `exploit.typed_spot`.
- **The hand:** the drill's rule, uniform over the 1,326 combos, with a clear fold shown one
  time in five. Push/fold hands are uniform, with no such rule.
- **Filters:** family, the hero's seat, limpers (0 to 3), ante (0 or 0.5), and one type that
  then fixes every opponent role (limpers, table, opener, push/fold villain).
- **The grade** is DECISIONS 60's, through `sixmax.grade` or `TypedSpot.grade`.
- **The log:** one line per answered drill, in `data/drills/<start>-trainer.jsonl`
  (gitignored).

**The page,** `bot/static/trainer.html`:
- the six seats with each one's role, its type badge and its trait card; your cards, the
  limps, the open, the ante and the pot;
- a button for every action and size;
- **the result card:** the label in colour; every action's EV in bb and as a % of the pot;
  the "why" lines; "against a standard player you'd …"; the band note; the assumed ranges;
  and the lesson card for the spot;
- **the session panel:** counts by label, accuracy (Best or Correct), bb lost, and misses by
  spot and by type;
- the filter bar;
- facing-an-open answers carry Gate Z's limit: "3-bet bluffs are overrated here".

**Lesson cards move into this step** from step 4, because the result card shows them.
- About 8 cards in `docs/lessons/`, our own text: the concept, a rule of thumb, and the
  engine's numbers for one example spot.
- `showdown/lessons.py` picks a card from the family, the hero's seat, the limpers, and
  the answer's kind against the best kind.
- No external links until Ian approves each one (decision 12).

**Gate U,** recorded before the session, page or lesson code. It passes when bars 1 to 4
pass.
1. **Grades through the API.** A scripted session over HTTP against an in-process server:
   - 300 drills, seed 20261128, all three families, no filters;
   - the answer drawn uniformly from the offered actions (seed 7);
   - each response's label, bb lost (to 1e-9) and % lost equal ones worked out in the test
     from a fresh `sixmax.answer` (or `exploit.typed_spot`) by DECISIONS 60's rule;
   - each family occurs at least 50 times.
2. **Latency.** Each `/api/hand` round trip, first deals included: median at most 2 s, 95th
   percentile at most 5 s (Gate K's bars). No other heavy process runs meanwhile.
3. **The log.** Exactly 300 lines, one per answered drill. The summary's counts by label and
   its bb lost equal the sums over the lines, the bb to 1e-9.
4. **The browser.** `showdown play` started through the preview tools (`.claude/launch.json`,
   port 8766). One drill per family is played on the trainer page, the page's text is read,
   and a screenshot is taken. All three must show a graded result card. Recorded in
   GATES.md; not an automated test.

**Reported, not gated:** labels by family; the round trip's maximum.

**The order:**
1. This entry and SCOPE A22, committed and pushed.
2. The session, the server routes, the page, the lesson cards and `lessons.py`, and the
   tests.
3. Gate U scored once and recorded. A failing bar gets one reproduce-and-fix, for a bug only.

**Decided without Ian (2026-11-27),** each the reversible option:
- the lesson cards move into this step;
- one type filter fixes every opponent role;
- push/fold depths of 2 to 20 bb, no ante;
- the page is a second static file, not a rewrite of `index.html`;
- the gate's letter, U.

**Rules out:**
- serving beyond 127.0.0.1;
- any live use;
- committing drill logs.

---

### 63. Trainer step 4: the leak finder on PokerStars exports, with opponent typing; Gate W2 pre-registered (2026-11-27)

**Decided.** Step 4 of the roadmap (DECISIONS 59). It extends DECISIONS 58's review. Ian's
up-front decisions 9 to 12 of 2026-11-26 set the Review tab, the typing and the leak groups.
SCOPE A23. Study only, as A13 and A18:
- completed hands from files a site lets you download;
- never during a session, never a watched folder;
- hand histories never committed.

**Classification.** DECISIONS 58's classifier gains the pots facing one open raise
(`opens=True`).
- **Facing an open:** exactly one raise came before the player's first action, with no
  limper before it, and nobody called it before the player. The opener (UTG to SB) is the
  raiser.
- **The open's size** in bb, from 2 to 3.5, maps to the nearer of 2.5 and 3; a tie goes to 3.
- **Its skip causes** replace "raised before you" (cause 6) with three, in this order:
  - "raised before you": two or more raises, or a raise after a limper;
  - "open called before you";
  - "open size": the open is outside 2 to 3.5 bb.
- **The answer** is an engine action:
  - a fold is fold;
  - a call is call;
  - a raise is the jam when it is all in or at least 40 bb, else the 3-bet to 3× when
    raise-to ÷ open ≤ 3.5, else to 4×.
- **In unopened and limped pots** a raise maps to the nearest of the spot's three sizes,
  with a tie to the smaller. A limp or check is the spot's limp action.

**Opponent typing,** over every hand in the files, per player name:
- **The stats:**
  - VPIP and PFR, as shares of the hands the player was dealt into;
  - limp %: limps first in, over the chances to act first in (not a blind, everyone before
    folded);
  - fold to iso: folds, over the chances where the player limped and next faced exactly one
    raise.
- **The type:** with at least 30 hands, the nearest of the six fitted types (DECISIONS 60).
  The distance is Euclidean, in percentage points, against the type cards' VPIP, PFR, limp
  % and fold to iso. A stat with no chances is left out; ties go by `TYPE_KEYS` order. With
  fewer than 30 hands, the type is standard.
- **Per decision:**
  - the limper type is the most common among that hand's limpers;
  - the opener type is the opener's;
  - the table type is the most common among the players to act after the player, or
    standard when there are none;
  - ties go to the earliest in seat order.

**Grades:** DECISIONS 60's scale. The answer is graded against the composed profile, and the
opener when facing an open. It is cached per spot, types and class, and equals a fresh
answer.

**The report** (`showdown sixmax review`, and the page's Review tab):
- **coverage:** files, hands parsed and failed, hands with the player, decisions graded by
  family, skips by cause;
- labels in all and by family, and bb lost;
- **opponents:** players typed, by type, and how many fell back to standard;
- **leaks:** Inaccuracy, Wrong and Blunder decisions, grouped by family, seat, opponent type
  (limped: the limpers'; unopened: the table's; facing an open: the opener's), and the
  answer's kind against the best kind. A group needs at least 3 decisions. The top 5 by bb
  lost each show their count, bb lost, labels, up to 5 hands (largest loss first) and their
  lesson card (`lessons.lesson_for`).

**The Review tab** (decision 9):
- a file picker for a PokerStars export;
- the text is posted to `/api/review` on 127.0.0.1 only, up to 20 MB for this route, parsed
  in memory and never saved;
- the player is the one with known hole cards in the most hands, unless a name is given.

**Gate W2,** recorded before the fixture or any review code. It passes when bars 1 to 5 pass.
1. **The fixture,** `tests/fixtures/sixmax_review_w2/`, written by a generator script before
   any review code and committed in its own commit:
   - fictional six-handed hands, as PHH plus one PokerStars file;
   - at least 40 hands. Four opponents with designed tendencies play at least 30 of them;
     two play fewer than 30;
   - at least 15 facing-an-open decisions for Hero, graded and skipped (each new cause at
     least once), plus unopened and limped ones;
   - labels computed by the generator from its own construction, by its own counts: each
     hand's family, spot, open bucket, engine action and class, or its skip cause; each
     player's stats and type.

   The bar: every hand's classification, every player's stats (to 1e-12) and every type
   equal the labels.
2. **Grades:** every graded fixture decision equals one worked out in the test from a fresh
   answer under the composed profile (and opener), by DECISIONS 60's rule. The label, best
   action and tier must match, and the bb lost to 1e-9.
3. **The report:** the counts by label and family, the bb lost, and each leak's count and bb
   equal the sums over the decisions, to 1e-9. Every leak names a lesson card that exists.
4. **Gate W unchanged:** Gate W's fast and slow tests pass with the review pinned to
   DECISIONS 58's kind scale and classifier (`scale="kind"`, `opens=False`).
5. **The Review tab,** in the browser through the preview tools, reviews the fixture's
   PokerStars file and shows the report. Recorded in GATES.md; not an automated test.

**Reported, not gated:** the new review on Pluribus's 10,000 hands (coverage by cause,
labels, top leaks, run time).

**Waiting on Ian, not a bar:** his own export, with coverage by cause and 5 hands per top
leak checked by him.

**The order:**
1. This entry and SCOPE A23, committed and pushed.
2. The fixture generator, the fixture and its labels, committed on their own.
3. The classifier, typing, grading, report, CLI, Review tab and tests.
4. Gate W2 scored once and recorded. A failing bar gets one reproduce-and-fix, for a bug
   only.

**Decided without Ian (2026-11-27),** each the reversible option:
- the open-size window and buckets, the 40 bb jam line, and the 3.5 ratio between the 3-bet
  sizes;
- the stats' definitions, ties, and the type per decision by majority;
- a generated fixture, its labels counted by the generator;
- the top 5 leaks; the gate's name, W2.

**Rules out:**
- watching a folder, or reading hands during a session;
- any ClubWPT file the site does not itself export;
- committing any real hand history;
- 3-bet pots where the player opened and faces a 3-bet;
- a profile per player beyond the type.

**Result (2026-11-27): Gate W2 PASS** (GATES.md).
- A fixture bug was fixed before scoring, at 520515f: the 0.5 bb ante had been written as
  0.5 chips in 9 hands.
- Bar 3's per-leak sums held only vacuously on the fixture, which makes no leak group of 3.
- On Pluribus, 8,947 of 10,000 hands are graded. The top leaks facing an open are Gate Z's
  limit.

---

### 64. The facing-an-open fix: a flat opener call share and R 0.85 for a called 3-bet; Gate Z2 pre-registered (2026-11-27)

**Decided.** Ian chose option A on Gate Z's bar 3 FAIL (DECISIONS 61's result), relayed by
the master session on 2026-11-27: a fix entry and a re-gate, pre-registered before any
code. Gate Z's FAIL stays on record. SCOPE A24.

**The fix,** for pots facing one open raise only:
1. **The size slope is dropped.** The opener's call share against a 3-bet no longer falls
   with the 3-bet's size: c(X) = c − δ at both 3× and 4×, clipped as before.
2. **R for a called 3-bet in position is 0.85,** down from 1.00. Out of position it stays
   0.75. Unopened and limped pots keep DECISIONS 53's and 56's R values.

**Decided without Ian:** of his two R options (by hand playability, or 0.85 for a called
3-bet), the second, because it is one number, easy to gate and to undo.

**What it cannot move:** any unopened or limped answer, so Gates M to W, K and Y. A fast test
asserts that sample answers are unchanged.

**Old gates keep reproducing.** Gates Z, U and W2 were scored on the old model. Their tests
pin it through `GATED_OPENER_SLOPE` and `GATED_THREEBET_IP` (1.00), and are re-run once.

**Gate Z2,** recorded before the fix is coded. It passes when bars 1 to 3 pass. Spots, types,
counts and the chart rule are Gate Z's.
1. **Closed forms,** to 1e-9:
   - Gate Z bar 1's checks, with the 3-bet called at R 0.85:
     EV = 0.85 × M[hero, QQ] × (6 × ante + 1.5 + 2X) − X;
   - **the flat call share:** with an opener whose call share is 33% and 4-bet 12%, the share
     of deals where it calls is the same at both 3-bet sizes.
2. **Directions:** Gate Z bar 2 at the new model.
3. **The chart:** Gate Z bar 3 at the new model: at least 85% of at least 100 kind-stable
   classes agree with PokerStrategy on continue vs fold.

**Reported, not gated:** the three-way agreement and each spot's; 72o on the BTN against a
CO open (fold should now beat both 3-bets); how many classes 3-bet per opener type.

**The order:** this entry and SCOPE A24, then the fix, the pins and the tests, then Gate Z2
scored once. A failing bar gets one reproduce-and-fix, for a bug only. Then the lesson
cards' numbers for facing an open and `docs/sixmax-preflop.md` are updated.

**Rules out:** tuning either number after results are seen; changing unopened or limped
spots; editing Gate Z's record.

**Result (2026-11-27): Gate Z2 FAIL, bar 3's count only** (GATES.md).
- Bars 1 and 2 pass.
- Bar 3: the 70 kind-stable classes agree 90.0%, but 100 are needed. Most weak hands are now
  close calls between fold and 3-bet.
- 72o folds now, and 3× beats 4× for value. At the base point the engine still 3-bets most
  hands facing an open.
- The result stands, and bar 3's test is a strict xfail. Gates Z, U and W2 reproduce under
  the pins.
- What follows is Ian's choice: a further fix (R by hand playability, or the opener's fold
  rate), or the documented limit, which stays in force meanwhile.
