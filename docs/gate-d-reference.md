# Gate D reference: which published push/fold solution to check against

Written 2026-11-14 for SCOPE Open question 4. Gate D requires the push/fold
solution to match "a published reference chart on at least 95% of the 169
classes at every depth checked", and the source has to be chosen and recorded
in DECISIONS before the solver first runs. This note lists what exists, what
each source assumes, and recommends one. The choice is Ian's.

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
is readable, with the chart as the fallback. Nobody has opened the zip yet,
because downloading it needs Ian's approval.

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

## Sources

- HoldemResources.net, HeadsUp Push/Fold Nash Equilibrium:
  <https://www.holdemresources.net/hune>
- b-inary/poker-cfr: <https://github.com/b-inary/poker-cfr>
- Miltersen and Sørensen, "A near-optimal strategy for a heads-up no-limit
  Texas Hold'em poker tournament", AAMAS 2007:
  <https://www.itu.dk/~trbj/papers/poker.pdf>
