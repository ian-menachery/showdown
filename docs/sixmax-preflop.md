# Six-max preflop spots: what `showdown sixmax` can and cannot be trusted for

`showdown sixmax` is the first slice of a six-max cash trainer (SCOPE A12, DECISIONS 53,
Gate M). Give it a seat, a hand, the limpers ahead, the ante and a profile:

```powershell
showdown sixmax BTN A5s --limpers 2 --ante 0.5 --profile loose-passive
```

It prints the opponents' assumed ranges, the EV of every action, the best action, and a
tier.

## What it answers

- **Spots:** unopened pots and pots with 1 to 3 limpers ahead, from each six-max seat.
  Stacks are 100 bb, blinds 0.5/1, with no ante or a 0.5 bb ante from every player.
- **Actions:** fold, limp (overlimp, complete or check), and three raise sizes: opens to
  2.5, 3 or 4 bb, isos to 3+k, 4+k or 5+k bb with k limpers.
- **Opponents:** one profile for the whole table: tight, regular or loose-passive. Each is
  a limp range plus how often each kind of player folds, calls or re-raises, fitted to
  2009 online 6-max hands ([`sixmax-profiles.md`](sixmax-profiles.md)).

## How it decides

Every opponent gets a hand from its range, and a board is dealt. Opponents act on their
own cards: a limper folds the bottom of its limp range to an iso, calls the middle and
re-raises the top; a player behind 3-bets its top hands and calls the next. Bigger sizes
make them fold more, by the profile's slope.

- **A pot that reaches the flop pays R × equity × pot.** Postflop is not played. R is 1.00
  for the raiser in position, 0.75 out of position, 0.85 in a limped pot in position, and
  0.75 out of position. The out-of-position raiser's R was 0.90 until DECISIONS 56. Gates
  M, M2 and K were scored at 0.90, Gate M4 at 0.75 (DECISIONS 57). Equity is exact (the
  169×169 matrix) when one opponent is left, and comes from the deal's board when there
  are more.
- **Facing a re-raise, the hero stacks off or folds,** whichever its equity against the
  re-raise range says.
- **Facing a raise after limping, the hero folds.** So the limp EV is a floor.

**The tier.** The engine moves every R by ±0.1 and the fold-to-raise rates by ±10 points
(9 points in all).
- **Clear:** the same action wins everywhere.
- **Close:** another action wins somewhere. The runner-up and where it wins are shown.
  When every point picks the same kind of action (all raises, say), the CLI says only the
  size is close.
- **Review:** no flip, but the lead is under 3 standard errors, or the answer changes when
  the hero never stacks off against a re-raise.

## Results (Gate M, GATES.md)

**Gate M failed on bar 3 only.**

- **Bar 1, the arithmetic: PASS.** Five hand-worked spots match: four exactly, and a
  3-way pot within 4 standard errors of `multiway.pot_shares`.
- **Bar 2, the directions: PASS.** Across 102 charts:
  - an ante never turns an entering hand into a fold;
  - one more limper never adds an offsuit iso;
  - premium hands never iso smaller against loose-passive limpers than against tight
    ones.
- **Bar 3, PokerStrategy's opens: FAIL.** On the hands the engine calls clear:
  - UTG, CO and BTN agree 100%;
  - HJ agrees 50%, on only 6 hands;
  - SB agrees 65%.

  The engine opens A9s, ATo and A9o from the HJ, and A5o to A8o and 22 to 55 from the
  SB. No bug: the fitted 2009 regulars fold about 73% in the BB to a small open, so
  stealing pays. On hands whose kind of action is stable across the band, sizes aside,
  agreement is 100% UTG, 78% HJ, 89% CO and 96% BTN. In the SB, the engine opens every
  hand against that BB.
- **Few spots are clear.** Over all charts, 36% of hands are clear, 62% close and 2%
  review. Of the close ones, 4 in 10 differ only in the raise size.

**The "standard" profile (Gate M2, DECISIONS 54).** It is the default. It is the regular
profile, except that players behind defend like a modern chart, and, since DECISIONS 57,
its limpers are the loose-passive profile's. The BB's defence by the
raiser's seat is fitted to VIP-Grinders' "Big blind defense" table. The SB's and the
other players' defence is assumed.
- **Directions: PASS.**
- **PokerStrategy: FAIL.**
  - **UTG to CO:** too few hands keep the same kind of action across the band to judge
    (12 to 26). Those compared agree 87 to 100%.
  - **BTN:** 81% agreement. The engine folds weak suited connectors and gappers that the
    chart opens to 2 bb.
  - **SB:** 59% agreement. The engine still opens every hand there.

**Both fixes (Gate M4, DECISIONS 57).** R for an out-of-position raiser fell from 0.90
to 0.75, and "standard" took its limpers from the loose-passive profile.
- **Arithmetic and directions: PASS.**
- **PokerStrategy: FAIL, at UTG only.**
  - **UTG:** only 7 hands keep their kind of action across the band, under the minimum
    of 10. All 7 agree with the chart.
  - **HJ, CO and SB:** every stable hand agrees with the chart (13, 21 and 25 hands).
  - **SB:** the engine now opens 78 hands, against the chart's 66, instead of all 169.
  - **BTN:** unchanged and not scored. Neither fix can move it.
  - Why UTG falls short: at R 0.65 out of position with 10 points more calls behind,
    AQs, AJs, ATs, AQo and AJo fold, though each opens at the base point.

## Trust it for

- **The arithmetic** of every spot it covers. Bar 1 checks it against hand-worked
  answers.
- **The kind of action** (fold, limp or raise) when the verdict is clear, or when it says
  "only the size is close", **against the profile you chose**.
- **The direction of an adjustment:**
  - an ante widens what you play: with 0.5 bb from everyone, isolating one limper with any
    two cards is often right;
  - more limpers mean fewer offsuit isos;
  - against loose-passive limpers you isolate fewer hands, because they fold only 39%
    to an iso, against tight limpers' 54%.
- **Seeing the assumptions:** each profile's limp, call and re-raise ranges, and how
  often the blinds defend, before you decide.
- **"Close" as a real flag.** The best action changes somewhere inside a modest
  assumption band, so either answer is defensible.
- **Unopened hands under "standard"** from the HJ, CO and SB, where every hand stable
  across the band agreed with PokerStrategy's opening ranges (Gate M4). From UTG, too few
  hands are stable to say, though those that are agree.
- **Unopened hands from UTG, CO and BTN** against regular players, where it agreed with
  PokerStrategy's opening ranges on every clear hand. Against them, the HJ and SB open
  wider than a standard chart. Use the chart there unless your blinds really do fold
  three times in four.

## Do not trust it for

- **Small-blind opens against the fitted profiles.** Under "standard" at R 0.75 the SB
  opens 78 hands, close to the chart's 66. Against the 2009 tight, regular and
  loose-passive blinds it still opens all 169, because they fold so often.
- **The exact size.** Sizes often trade places inside the band. When every band point
  picks a raise, the CLI says "only the size is close". Read that as: raise, any of the
  sizes.
- **The EV numbers themselves.** They scale with R, which is assumed, not measured for
  six-max. Gate Q's own flop solves measured an out-of-position caller's R at 0.63 to
  0.78, below the 0.75 to 1.00 used here. Compare EVs within one spot, not across spots.
- **Premium hands' EVs.** Every re-raise becomes an all-in for 100 bb, so AA and KK
  collect a stack whenever someone 3-bets. Real 3-bet pots at 100 bb are played, not
  jammed. AA's EV (about +15 bb under the gun, regular profile) is inflated, and its
  best size is pulled
  by stack-offs. "Folding to every re-raise, the best is …" shows how much that matters.
- **Limping.** A raise behind a limp is always folded, so the limp EV is a floor. At
  tables that iso a lot (in the fitted profiles each non-blind player behind raises a
  limp 14 to 19% of the time), limping looks worse than it is, mostly for suited and
  paired hands that could call.
- **Who limp-reraises.** A limper's re-raise range is the top of its limp range, and the
  limp range sits just below its open-raise range. So a limp-reraise holds hands like
  K8s, not the AA or KK a passive player sometimes limps. Facing a real limp-reraise,
  fold more than the engine assumes.
- **The standard profile's limpers.** Since DECISIONS 57 they are loose-passive's: they
  limp 31% of hands and fold 39% to an iso. Their limp range is the band just below
  their top 17.5% by equity against a random hand: 22-44, weak suited kings and queens,
  A2o-A7o, K2o-K9o and the like. It never holds AA or KK, and holds few suited
  connectors.
- **The tight profile's limpers.** Tight players in the data limp 0.8% of hands, so the
  engine's tight limper holds a thin band of medium hands. Real tight limpers more
  often hold small pairs and suited connectors.
- **Your players.** The profiles are 2009 online players at 25NL and up, with no antes,
  and one profile covers the whole table. A home game with an ante of the small blind
  from everyone is looser preflop. Pick the profile that fits, and treat the answer as
  a prior.
- **Hand strength.** Ranges are cut by equity against a random hand, which ranks high
  cards above small pairs and suited connectors. Ranges show the classes at least half
  in.
- **Anything else:** other stack depths, straddles, pots that someone has already raised,
  3-bet pots, postflop play and ICM are not modelled.

## Drills and hand review

Two tools build on this engine, and both grade the kind of action only:
- **`showdown sixmax drill`** deals practice spots (DECISIONS 55, Gate K PASS).
- **`showdown sixmax review PATHS --player NAME`** reads completed hands, as PHH or
  PokerStars text (DECISIONS 58, Gate W PASS). It grades the player's first preflop
  decision in each six-handed hand that fits a spot here:
  - an unopened pot, or 1 to 3 limpers;
  - an ante of 0 or 0.5 bb;
  - an effective stack of 60 to 150 bb.

  Every other hand is skipped and counted by cause. The report lists recurring leaks,
  with the hands to look at.

Read a review's leaks with this page's limits in mind. On Pluribus's 10,000 hands, the
biggest "leak" was limping KK, QQ and AK from the small blind. That is the limp EV floor
at work, not a mistake by Pluribus. Raised pots, which are 45% of Pluribus's hands, are not
graded. There is no Poker Now log parser yet.
