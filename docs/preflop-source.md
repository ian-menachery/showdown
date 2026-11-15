# Preflop source above 20 bb (spike S3, decision D3)

Written 2026-11-15 for Ian's decision D3 (`docs/plan-live-advisor.md`). This
is a spike: nothing in `src/` changed. The prototype is
`spikes/2026-11-15-preflop-source.py`; its docstring has the commands and a
summary of the output.

**Why D3 matters more after S2.** Gate S2 failed, and under DECISIONS 31 V1
is preflop suggestions plus a postflop equity helper. That helper needs the
opponent's preflop range, and so does the flop library planned next. Above
20 bb, the preflop source therefore answers both questions: what to suggest
before the flop, and which range the helper assumes after it.

## The short answer

| | 1. Our CFR prototype | 2. A licensed published chart | 3. Push/fold only |
|---|---|---|---|
| **Covers 25–100 bb** | Yes: open, 3-bet and 4-bet jam, at any depth we solve | No realistic chart exists. The only licensed heads-up data is b-inary's check-down solves (BSD-2) | No: "no suggestion" above 20 bb |
| **Outside check** | None yet. It matches push/fold exactly at 20 bb, but nothing outside checks 25–100 bb | b-inary is an independent solve, but of a different check-down game | Yes: Gate D, against HoldemResources |
| **Main limit** | The postflop model R moves the strategy far more than solver error does | The same check-down model; needs a download approval and a decoder (no Rust on this machine) | Games deeper than 20 bb get no preflop advice, and the equity helper has no opponent range |
| **Scope** | Needs a SCOPE amendment: SCOPE rules out "any abstraction beyond push/fold" | Needs a download approval and a DECISIONS entry | Already in scope |

**Recommendation for D3:** option 1 with R_oop = 0.9, labelled on screen as a
model chart. It comes after a SCOPE amendment and a pre-registered gate, with
the R = 1 solve checked against b-inary's files if Ian approves that download.
Until then, V1 runs option 3. The reasons are at the end of this note.

## Option 1: a small preflop game solved with our own CFR

### The game

Heads-up, blinds 0.5/1, no ante. S is the effective stack before the blinds
(DECISIONS 22). Chance deals a pair of the 169 classes, weighted by exact
card-removal counts, as in `games/pushfold.py`.

| Who | Facing | Actions |
|---|---|---|
| SB | first in | fold, raise to 2.5, all-in |
| BB | the raise | fold, call, 3-bet to 7.5 (3×), all-in |
| SB | the 3-bet | fold, call, all-in |
| BB | SB's all-in (first in, or over the 3-bet) | fold, call |
| SB | BB's all-in over the raise | fold, call |

Payoffs:
- A fold loses what the folder has put in.
- A called all-in nets S(2E − 1), where E is the exact all-in equity from
  `data/preflop_169_exact.npz`.
- A called raise or 3-bet sees the flop, but the flop is never played. With
  c bb in from each player, the SB nets c(2·share − 1), where
  share = 1 − R_oop·(1 − E).
- After the flop the BB is out of position, so it realizes R_oop of its
  equity. The game stays zero-sum by giving what the BB forfeits to the SB, so
  the SB's effective R is at least 1.
  - R_oop = 1 is a check-down to showdown.
  - R_oop = 0.9 is the plan's "0.9 OOP / 1.0 IP".

The solver is the generic `cfr_plus` on `compile_game`'s tree, with
`exploitability` and `policy_value` from `showdown.cfr`. Each solve ran 300
iterations. That was set from a timing probe before any strategy was
read, and it is below Gate D's 1,000 to keep each solve near 5 minutes.

### What it measured

The tree has 485,538 nodes and 1,014 infosets at every depth. Push/fold's has
142,806 and 338.

| Run | Exploitability (bb/hand) | SB value (bb/hand) | SB first in: fold / raise / jam | BB vs raise: fold / call / 3-bet / jam | SB vs 3-bet: fold / call / jam | BB calls SB's 4-bet jam | SB calls BB's jam | BB calls SB's first-in jam |
|---|---|---|---|---|---|---|---|---|
| 20 bb, R 1 | 2.3e-4 | −0.128 | 49 / 31 / 21% | 3 / 71 / 0 / 26% | *51 / 27 / 22%* | *95%* | 31% | 23% |
| 20 bb, R 0.9 | 2.2e-4 | −0.078 | 43 / 50 / 7% | 17 / 53 / 0 / 30% | *29 / 52 / 19%* | *97%* | 37% | 25% |
| 25 bb, R 1 | 2.6e-4 | −0.131 | 46 / 45 / 9% | 1 / 76 / 0 / 23% | *44 / 36 / 20%* | *72%* | 27% | 19% |
| 25 bb, R 0.9 | 2.5e-4 | −0.059 | 41 / 57 / 2% | 15 / 56 / 0 / 29% | *33 / 52 / 16%* | *96%* | 31% | 23% |
| 50 bb, R 1 | 7.2e-4 | −0.089 | 37 / 63 / 0% | 0 / 82 / 9 / 8% | 40 / 47 / 13% | 36% | 15% | *9%* |
| 50 bb, R 0.9 | 4.6e-4 | +0.037 | 27 / 73 / 0% | 9 / 70 / 0 / 21% | *11 / 78 / 11%* | *30%* | 15% | *11%* |
| 100 bb, R 1 | 1.6e-3 | −0.098 | 38 / 62 / 0% | 0 / 80 / 20 / 0% | 27 / 64 / 9% | 19% | 9% | *4%* |
| 100 bb, R 0.9 | 1.0e-3 | +0.122 | 16 / 84 / 0% | 5 / 78 / 11 / 6% | 0 / 94 / 6% | 16% | 7% | *6%* |

How to read it:
- Each cell is a share of the hands that reach that spot, counted in combos.
  Card removal against the opponent's range is ignored here; it is counted
  in the solve itself.
- *Italic* cells are off the equilibrium path. The opponent's action that
  leads there is taken with 0.06% of hands or less:
  - the BB's 3-bet at 20 and 25 bb, and at 50 bb with R 0.9;
  - the SB's first-in jam at 50 and 100 bb.

  Strategies there are barely trained and should not be read as advice.

### Checks

- **Continuity with push/fold: exact.** With the raise removed, the game is
  push/fold. At 20 bb with 1,000 iterations, as DECISIONS 22 sets, it
  reproduces `data/pushfold.json` exactly:
  - the maximum difference in any push or call probability is 0;
  - the exploitability is 2.822e-6 on both sides;
  - the SB value is −0.183190 on both;
  - Gate D's rule scores push 168/168 (1 excluded) and call 169/169.

  The spike's game code, deal weights and all-in payoffs are therefore those
  of the gated push/fold game.
- **Sanity at 20 bb: passes.** The SB can always play push/fold, and the BB's
  only answers to a jam are the same as in push/fold. So the full game's SB
  value must be at least push/fold's −0.1832, less the two exploitabilities.
  It is −0.128 with R = 1 and −0.078 with R = 0.9.
- **Convergence.** After 300 iterations, exploitability is 2.2e-4 to 2.6e-4
  bb/hand at 20 and 25 bb, 4.6e-4 to 7.2e-4 at 50 bb, and 1.0e-3 to 1.6e-3 at
  100 bb. It falls about 3× per doubling of iterations. Getting 100 bb under
  1e-3 with R = 1 would take roughly 400 to 500 iterations.
- **Run time.**
  - Compiling takes 1 to 4 s.
  - One iteration takes 0.8 to 0.9 s on an otherwise idle machine, and
    2.3 s while S2's TexasSolver held all 16 cores. That is 3 to 4 times push/fold's
    0.23 s per iteration, in line with a tree 3.4 times the size.
  - A solve takes 4 to 5 minutes. A grid of six depths at both R values
    would take about an hour, offline.
  - Nothing is solved during play: the advisor would look up stored
    strategies.

### How much R matters

R matters more than anything else measured here.

**The SB's value swings with R:**

| Stack | R = 1 | R = 0.9 | Swing |
|---|---|---|---|
| 20 bb | −0.128 | −0.078 | 0.05 |
| 25 bb | −0.131 | −0.059 | 0.07 |
| 50 bb | −0.089 | +0.037 | 0.13 |
| 100 bb | −0.098 | +0.122 | 0.22 |

Even against the largest exploitability measured (0.0016), the choice of R
outweighs solver error by about 30 to 140 times.

**The ranges move with it.**
- At the first-in, facing-a-raise and facing-a-3-bet nodes, the mean
  total-variation distance between the two R values is 0.09 to 0.41. Here 0
  means the same strategy and 1 means disjoint.
- Calls against a jam over the open, or against a first-in jam, barely move
  (0.01 to 0.05), because an all-in pot does not depend on R.
- At 100 bb:
  - the SB's first-in folds fall from 38% to 16%, and 21 classes flip from
    fold to raise;
  - facing a 3-bet, the SB folds 27% at R = 1 and almost never at R = 0.9;
  - the BB goes from never folding to a raise to folding 72o, 62o, 52o, 42o
    and 32o.
- At 20 and 25 bb, R = 0.9 moves hands from jamming to raising. At 20 bb,
  for example, A7s, A5s, A9o, A8o, A7o and 55 raise instead of jamming.

**R = 1 has a positional blind spot.** It removes the button's positional
edge:
- the BB folds 3% or less to a raise at every depth;
- the SB folds 37% to 49% first in;
- the SB loses money at every depth.

R = 0.9 looks more like heads-up play: at 100 bb the SB opens 84%, and the BB
folds only its five worst hands. But looking right is not a check: 0.9 is an
assumption, and the spike ran only the two values in the plan.

### Limits

- **A small tree:**
  - no limp and no min-raise (SCOPE rules out both today);
  - one open size, 2.5;
  - one 3-bet size, 3×;
  - no 4-bet except all-in.

  The solver charts in the licence survey below include limps and several
  sizes.
- **Postflop is not played.**
  - Every hand and every pot uses the same R.
  - Money behind never goes in. At 25 bb, a called 3-bet leaves 17.5 bb
    behind in a 15 bb pot, and the model treats the hand as over.
- **The 3-bet is nearly unused at 20 and 25 bb, and at 50 bb with R = 0.9.**
  The BB jams or calls instead. A live opponent who makes a small 3-bet there, or uses any size
  not in the tree, gets an answer from a barely trained spot. The advisor
  would need a rule for mapping real sizes onto the tree, and should say
  "off-tree" when the mapping is poor.
- **Exploitability is measured inside the abstract game only.** An opponent
  who can limp, use other sizes and actually play after the flop is not
  bounded by these numbers.
- **The depths form a grid,** so stacks in between need a rule (nearest
  depth, or the depth just below).
- **The advice jumps at 20 bb.**
  - At 20 bb, the richer game beats push/fold by 0.055 to 0.105 bb/hand.
  - Its SB jams 7% to 21% of hands; push/fold's jams 40%.
  - So switching sources at 20 bb changes the advice abruptly. Push/fold
    stays the checked answer to its own game, but the overlay should say
    which source answered.
- **300 iterations is modest.** Many classes still mix (6% to 15% of first-in
  hands), so the overlay should show mixes rather than round them away.

## Option 2: published charts with a licence

Searched 2026-11-15 (web only, nothing downloaded). The question for each
source was whether its chart data may be transcribed into a private repo that
may later go public. "Free to view" is not a licence, and a GitHub repo with
no LICENSE file is all rights reserved.

**No source gives realistic heads-up charts for 25 to 100 bb under a clear
open licence.** The three licensed sources each fall short in a different way:

| Source | What it covers | Terms | Usable here |
|---|---|---|---|
| [b-inary/poker-cfr](https://github.com/b-inary/poker-cfr) | Heads-up preflop only. Solved strategies are binary files in `output/` at 7, 10, 15, 20, 25, 30, 40, 50, 60, 80 and 100 bb. Blinds 0.5/1, no ante, no rake. The SB may limp. Raises are 2.5×, 3×, 3.5× or 4× the current bet, or all-in, with no cap on re-raises. **Every call goes to showdown at preflop equity**: the same model as our R = 1. The files need the repo's Rust viewer to decode. | BSD 2-Clause (already used for the exact-matrix check, DECISIONS 20 and 21) | Yes, with the BSD notice. But it is a check-down model, not real heads-up play |
| cpunk7385-sys/preflop-ranges | Heads-up push/fold only, 1 to 25 bb, no ante. Created 2026-11-04 by one author, unvetted | CC0 1.0 | Yes, but push/fold only: no opens or 3-bets |
| a-hanamoto/leakproof-preflop-ranges | 6-max, 100 bb, no ante. Opens, 3-bets and 4-bets, but no SB-vs-BB chart. Created 2026-10-30, unvetted | CC BY 4.0 | Yes with attribution, but not heads-up. In 6-max the SB is out of position after the flop; in heads-up it is the button |
| [HoldemResources](https://holdemresources.net/hune) | Push/fold only, with no ante or a 10% ante; the charts stop at "20+". No deeper free heads-up charts | No licence for the charts; "© 2026 HoldemResources GmbH" | No |
| GTO Wizard | Paid heads-up solution library | Terms §7.5 forbid commercial use of "poker ranges"; nothing grants copying | No |
| SolvePoker | Heads-up at 50, 100 and 200 bb (MonkerSolver, 5% rake capped at 2 bb, limps, full tree to the 5-bet) | Forbids sharing "solver data, strategy outputs" | No |
| Poker Academy | Heads-up tournament charts, 8 to 100 bb, with a 0.25 bb ante | Commercial; no licence on the page | No |
| PokerCoaching, D&B Poker | Shove/fold and min-raise/shove preflop games up to 100 bb, from *Expert Heads Up No Limit Hold'em* | Reproduction forbidden | No |
| Upswing, Preflop Wizard, ART/GTO | Upswing's heads-up charts are in a paid course; Preflop Wizard gives rough 100 bb percentages; ART/GTO is 6-max | Copying forbidden (Upswing, Preflop Wizard); "personal use" only (ART/GTO) | No |
| Small heads-up GitHub repos (allenlong2007/poker-preflop, koleCar/poker-hand-converter, GTOpen, tavelarocque/holdem-cfr) | Heads-up 100 bb CSVs and charts of unknown origin | No LICENSE file | No |

No Wikimedia or CC-licensed heads-up chart turned up. No academic paper found
publishes heads-up no-limit preflop tables at these depths under a licence.

Two routes to a licensed chart remain, both outside this spike:
- **b-inary's solved files.**
  - They need a download approval, plus a decoder written here, since this
    machine has no Rust toolchain.
  - They share the check-down model's limits.
  - But they are an independent solve of a richer check-down game: limps,
    four raise sizes, uncapped re-raises. That makes them the natural outside
    check on our R = 1 solve.
- **A HoldemResources licence.**
  - HRC's EULA lets a licensee share "the results of authorized
    calculations". Buying HRC and solving heads-up 25 to 100 bb would give
    charts that may be used.
  - It costs money, and nobody checked whether results from the trial count
    as authorized.

These licence findings come from one research pass on 2026-11-15. Repo
licences were read through GitHub's API, and terms pages directly. The two
new CC repos have no track record, so they would need their own check before
any use.

## Option 3: push/fold only, "no suggestion" above 20 bb

- **What it has.** It is checked against HoldemResources at all 40 seat and
  depth comparisons (Gate D). It is already in the trainer, and
  `PushFoldStrategy.grade` gives the EV of every action.
- **What it costs.**
  - A game that starts deeper than 20 bb, such as a 100 bb buy-in, gets no
    preflop advice until stacks fall to 20 bb.
  - The V1 equity helper (DECISIONS 31) has no opponent range above 20 bb.
    The only fixed ranges in the repo are S2's "top X%" ranges, which
    DECISIONS 30 says are for timing only and "not a strategy".
  - The flop library planned after V1 needs preflop ranges as its input,
    for the same reason.

## Recommendation for D3

1. **Option 1, with R_oop = 0.9 as the default.**
   - It gives sensible-looking advice at 25 to 100 bb.
   - Just as important, it gives the ranges that the equity helper, and
     later the flop library, need.
   - It is labelled "model chart" on screen and in the hand log, the way
     DECISIONS 31 labels the helper's hints as equity heuristics.
2. **A SCOPE amendment first.**
   - SCOPE's out-of-scope list names "any abstraction beyond push/fold". It
     also names "limp or min-raise options", if the tree ever grows them.
   - The amendment should say plainly that the model's postflop assumption
     cannot be checked against an outside answer.
3. **A gate pre-registered before the product solve.** These are suggestions
   for Ian to set; none is decided here.
   - **Continuity:** the jam-only 20 bb game reproduces `data/pushfold.json`
     exactly. It passed here.
   - **Sanity:** at 20 bb, the full game's SB value is at least push/fold's,
     less both exploitabilities. It passed here.
   - **Payoffs:** an independent closed-form calculation of every terminal
     payoff, per class pair, matches the tree. This spike did not do it.
   - **Exploitability:** at most a fixed bar, in bb per hand, at every
     solved depth, with a fixed iteration count. For scale, 300 iterations
     gave 2.2e-4 to 1.6e-3 here.
   - **Fixed in advance:** the stack grid and the rule for stacks in between.
   - **Outside check, if Ian approves the download:**
     - decode b-inary's solved files at 25, 50 and 100 bb;
     - compare coarse range sizes against our R = 1 solve, such as the SB's
       first-in fold share and the BB's defence against a 2.5× raise;
     - this checks the game and the solver; R = 0.9 then changes only the
       flop payoff line;
     - the comparison is loose, because b-inary's game has limps and more
       sizes.
4. **Until then, option 3:** push/fold at 20 bb or less, "no suggestion"
   above.
5. **Not recommended: transcribing a published chart.** None surveyed has a
   licence that allows it, except b-inary (a check-down model) and two
   unvetted repos that are push/fold-only or 6-max.

**Trade-off behind R = 0.9 over R = 1.**
- R = 1 has no free parameter and is the model b-inary solved, so it alone
  could be checked against an outside answer.
- But it plays unlike heads-up poker: the BB never folds to a raise, and the
  SB folds over a third of its hands at 100 bb.
- R = 0.9 is closer to Ian's "sensible suggestions", at the price of a number
  chosen by judgment.
- A sweep over R from 0.8 to 1.0 would show how much the choice matters
  before it is fixed.
