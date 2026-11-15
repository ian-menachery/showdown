# Gate D reference: which published push/fold solution to check against

Written 2026-11-14 for SCOPE Open question 4. Gate D requires the push/fold
solution to match "a published reference chart on at least 95% of the 169
classes at every depth checked", and the source has to be chosen and recorded
in DECISIONS before the solver first runs. This note lists what exists, what
each source assumes, and recommends one.

**Outcome (2026-11-14):**
- Ian chose the HoldemResources raw data, and approved downloading it and
  b-inary's exact equity table. This is recorded in DECISIONS 20.
- He did not approve the proposed depths and scoring at the end of this note.
  They stay a proposal.
- The two sections at the end, "What the files turned out to contain" and "Our
  own error, measured", were added after the downloads. They replace the
  guesses written before the files were opened.

## What the reference has to match

Our game (SCOPE, "The spine"): heads-up, no ante, the small blind jams or folds
and the big blind calls or folds. Payoffs are chips won on the one hand, in big
blinds. The effective stack is 1 to 20 bb. A reference built on a different
game (antes, tournament equity, several hands) would disagree with us even if
both solutions were right.

## Candidates

| Source | Same game as ours? | What it publishes | Licence and access | Verdict |
|---|---|---|---|---|
| HoldemResources.net, "HeadsUp Push/Fold Nash Equilibrium" (the HUNE page) | Yes. No-ante tab, chip EV, effective stack in bb before posting blinds | Pusher and caller charts: the largest stack at which each class pushes or calls, 0.1 bb resolution, capped at "20+". A raw-data zip of the unsimplified solution | Free to view. No licence stated for the charts or the zip (the site's Legal page covers only the paid HRC software) | **Recommended** |
| b-inary/poker-cfr, `push_fold` binary (Rust) | Yes. Same payoffs; works on all 1,326 combos with exact equities | Nothing pre-computed. You run it at one stack depth and it prints push and call percentages to 0.1% | BSD-2-Clause. Needs a Rust toolchain, which this machine does not have | Useful as a second check, not as the gate |
| Chen and Ankenman, *The Mathematics of Poker* (2006), jam-or-fold tables | Yes, by HoldemResources' account | Threshold tables like HUNE's | Copyrighted book. We would need a copy and could not commit the numbers | Not recommended |
| Miltersen and Sørensen (AAMAS 2007) | No. It solves a whole heads-up tournament (8,000 chips, 300/600 blinds) as a multi-hand game | A jam/fold strategy that maximises the chance of winning the tournament, not the chips won on one hand | Free paper | Wrong game; cite only |
| SAGE, Sklansky-Chubukov numbers | No. SAGE is an approximation and Sklansky-Chubukov assumes the caller sees your cards | Simple rules of thumb | — | Wrong game |
| Commercial tools (HRC, ICMIZER, SnapShove, SNGPT) | Yes, at their no-ante, chip-EV settings | Inside paid software | Paid licences | Not reproducible from the repo |

A sixth lead, a C++ solver at `rt500/Heads-Up-Push-or-Fold`, no longer exists on
GitHub.

## Why HoldemResources

- **It is the same game.** The page defines the effective stack as the smaller
  stack before either blind is posted, which is our definition. The no-ante tab
  matches our payoffs. Its smallest pusher threshold is 1.4 bb, so it agrees
  with Gate D's own check that every class jams at 1 bb.
- **It is the reference other sources are measured against.** The page itself
  compares its chart with SNGPT's and *Mathematics of Poker*'s.
- **It publishes the unsimplified solution as well.** The raw-data zip
  (`holdemresources_hu_equilibrium.zip`, 86,510 bytes, dated 2012-05-06) is
  described as the full equilibrium for every stack from 1 to 200 bb in steps of
  0.05 bb. The page says the charts can be derived from it, and that it was
  recalculated with a later version than the chart, so the two may differ
  slightly.

## Chart or raw data

The page warns that the chart is a simplification. In the exact solution most
classes mix at some stack depths, and some have several gaps. Three suited
hands (63s, 53s, 43s) have gaps the chart does show. Collapsing that into one
number per class involves arbitrary choices, and the page says two independent
charts are unlikely to match exactly.

That bears directly on Gate D:

- **Against the chart**, a class our solver plays purely could still disagree
  near its threshold, because the chart rounded a mixed region to one side.
  The 95% bar leaves room for about 8 such classes per depth.
- **Against the raw data**, both sides are unsimplified equilibria. A class can
  be compared wherever both play it purely, and excluded and counted wherever
  either one mixes. That is the comparison Gate D's wording already describes.

So the recommendation is the **raw data as the gate reference**, if its format
is readable, with the chart as the fallback. When this was written the zip had
not been opened. What it contains is below, under "What the files turned out to
contain".

## Our own error

Our payoff table is the Monte Carlo matrix from Phase 3, with each cell's SE at
most 0.0017. At 10 bb an equity error of 0.0017 moves a showdown's value by
about 10 × 2 × 0.0017 = 0.034 bb. A class within that distance of indifference
could land on the other side from an exact-equity reference. Gate D's 95% bar
is meant to absorb that. If more than a handful of classes disagree at one
depth, the matrix is the first suspect, not the reference.

b-inary/poker-cfr also ships an exact equity table for every ordered combo pair
(`static/heads_up_pre_flop_equity.bin`, 7,033,112 bytes, BSD-2-Clause). Per
its source, each entry is 2 × wins + ties over all 1,712,304 boards. Read with
numpy, it would give an exact 169×169 matrix to check every cell of ours
against. That would be a far stronger test than Gate C's three spot checks.
It is optional, and the download also needs approval.

## Proposed comparison, to be fixed in DECISIONS before the solver runs

- **Depths checked:** 2, 3, 4, 5, 6, 8, 10, 12, 15 and 20 bb, for both the
  pusher and the caller. That gives 20 comparisons of 169 classes. At 1 bb,
  Gate D's own check already applies.
- **Our side:** a class is pure if its average strategy plays one action with
  probability at least 0.99, and mixed otherwise.
- **Raw-data side:** the same rule. If only the chart is used, a class pushes
  at depth d when d is at or below its threshold, gaps included.
- **Score:** a class that either side mixes is excluded, and the number
  excluded is printed with every result. The score is agreements divided by the
  classes compared. The gate passes if every one of the 20 comparisons scores
  at least 95%. If more than 10% of classes are excluded at any depth, that is
  reported as a finding, not hidden inside the score.
- **Storage:** the reference file stays out of git, in a gitignored
  `data/external/`, with its SHA-256 pinned in the test. The test fails, rather
  than skips, if the file is missing when the gate runs. No licence covers
  redistributing the data, and keeping it out of git keeps Open question 5
  (going public) simple.

## What the files turned out to contain

Checked by `spikes/2026-11-14-reference-data.py`. To fetch both files on a
fresh clone, run these from the repo root. The spike checks every SHA-256
before it reads anything.

```
mkdir -p data/external/hrc/raw data/external/b-inary
curl -sSfL -o data/external/hrc/holdemresources_hu_equilibrium.zip https://www.holdemresources.net/hrdata/holdemresources_hu_equilibrium.zip
curl -sSfL -o data/external/b-inary/heads_up_pre_flop_equity.bin https://raw.githubusercontent.com/b-inary/poker-cfr/a5347082007ba1eda7932ef2fe7fad43cb3be2a1/static/heads_up_pre_flop_equity.bin
```

Then extract `holdemresources_hu_push.csv` and `holdemresources_hu_call.csv`
from the zip, by name, into `data/external/hrc/raw/`.

- **The HoldemResources raw data.** The zip holds two CSVs, push and call.
  - Each has one row per stack, from 1.00 to 200.00 bb in steps of 0.05 (3,981
    rows), and one column per class.
  - The class names are the same 169 names we use.
  - Each value is a play probability, rounded to 0.01.
- **It matches the chart.** At the chart's thresholds the raw data agrees within
  0.05 bb on 10 of 10 spot checks. Those include all three gapped hands, so
  this is the solution behind the chart.
- **Mixing is rare.** At 2 to 20 bb, at most 3 classes mix at any one depth
  (0.01 < p < 0.99) for the pusher, and at most 2 for the caller.
- **The b-inary table** is what its source says it is: a 1,326 × 1,326 table of
  2 × wins + ties.
  - Conflicting pairs are 0.
  - Swapping the two hands always gives the complementary score.
  - It gave the same integer as our own exhaustive enumeration on 8 of 8
    pairs.

## Our own error, measured

Over all 14,196 distinct cells, our matrix compared with exact equity:
- the largest absolute error is 0.0046 (T4s vs 33);
- the mean absolute error is 0.0009;
- 97.2% of cells fall within 2 of their own SE, and 99.86% within 3.

So the standard errors are honest. At 10 bb the largest error moves one class
pair's showdown value by about 0.09 bb, and a typical error by about 0.02 bb.

That question is now gone. Ian approved an exact matrix, and Phase 4 solves on
it (DECISIONS 21). The matrix enumerates every board and equals b-inary's
table to the integer in every cell.

## Sources

- HoldemResources.net, HeadsUp Push/Fold Nash Equilibrium:
  <https://www.holdemresources.net/hune>
- b-inary/poker-cfr: <https://github.com/b-inary/poker-cfr>
- Miltersen and Sørensen, "A near-optimal strategy for a heads-up no-limit
  Texas Hold'em poker tournament", AAMAS 2007:
  <https://www.itu.dk/~trbj/papers/poker.pdf>

## Pluribus hands (Phase 6, DECISIONS 25)

The analyzer's real-data check (Gate F, Done 4) uses the 10,000 Pluribus hands
from the phh-dataset (MIT). Only `data/pluribus` is fetched, at a pinned
commit, into the gitignored `data/external/phh/`. The slow tests check a
manifest hash over every file. To fetch it, run this from the repo root:

```
mkdir -p data/external/phh && cd data/external/phh
git clone --filter=blob:none --no-checkout --sparse https://github.com/uoftcprg/phh-dataset.git repo
cd repo && git sparse-checkout set data/pluribus
git checkout e47fbd5816372360bade4de5d712346fe1bb70f6
```
