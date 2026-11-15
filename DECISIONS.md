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
