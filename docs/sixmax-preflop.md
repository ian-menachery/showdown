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
  - **A documented limit (Ian, 2026-11-22).** The UTG count stays as recorded. The band
    is not narrowed to make more hands stable.

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

- **UTG opens beyond the strongest hands, under "standard".** Only AA to TT, AKs and AKo
  keep their kind of action across the band. Even AQs to ATs, AQo and AJo fold at its
  harshest corner. This is a documented limit: the band stays as it is (Gate M4).
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
- **Limping: a raise behind a limp counts as a fold.** The engine has the limper give up
  the chips whenever someone raises behind, so the limp EV is a floor.
  - At tables that iso a lot, limping looks worse than it is. In the fitted profiles each
    non-blind player behind raises a limp 14 to 19% of the time. This hits hands that
    could call or re-raise: suited, paired and premium hands.
  - In hand review it makes fake leaks. Pluribus's small-blind limps with KK, QQ, AK and
    AQ grade as review, each 1.7 to 6.8 bb behind a raise (Gate W). A limp-trap with a
    premium hand is never graded fairly.
  - **A known limit, left for later.** Fixing it needs the limper to call or re-raise a
    raise behind, which needs its own DECISIONS entry and gate.
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
- **Anything else:** other stack depths, straddles, pots where you opened and face a 3-bet,
  postflop play and ICM are not modelled.

## Player types and grades (DECISIONS 60, Gate Y PASS)

- **Types.** Opponents are named types: one for the limpers, one for the table. They are
  fitted to 2009 groups of players by VPIP and PFR ([`sixmax-types.md`](sixmax-types.md)).
  A limper type uses its own fitted rates. A table type scales standard's modern defence by
  how that group differs from the 2009 average.
- **Trust the directions:** against Nit blinds you steal at least as wide as against LAG
  blinds, and wider against Weak-tight recs than against Calling stations; limpers who fold
  less get no new offsuit isos (Gate Y bar 3).
- **Grades** are GTO Wizard's scale by EV lost as a % of the pot. An answer that wins
  somewhere in the band is never below Correct. So read Inaccuracy, Wrong and Blunder as
  "loses at every assumption tested", and Best or Correct on a close spot as "either is
  defensible".

## Facing one open raise (DECISIONS 61, Gate Z FAIL, bar 3 only)

`showdown sixmax SEAT HAND --opener SEAT` answers fold, call, 3-bet (3× or 4× the open) or
jam, against an opener of a named type and a table type behind.

- **Trust:** the arithmetic (bar 1 closed forms to 1e-9), and continuing at least as often
  against a LAG or a Maniac opener as against a Nit (bar 2).
- **Do not trust its 3-bet bluffs.** It 3-bets nearly every hand against every opener type.
  Against PokerStrategy's vs-open ranges it agrees on continue vs fold for 79.9% of 134
  stable hands, under the 85% bar. Every miss is a 3-bet where the chart folds (KJo against
  UTG, 22 to 44 against the HJ and CO, A5o to A9o in the SB against the BTN).
  - **Why:** the opener folds 55% of its range to a 3× 3-bet (assumed, close to the 2009
    pool's 55%). Its calls fall another 0.049 per bb of extra size, so a 4× 3-bet gets 67%
    folds. And R 1.00 for a called 3-bettor in position treats 72o like AK. I checked 72o
    on the BTN against a CO open by hand: it matches the engine exactly (+0.40 bb at 4×), so
    it is the model, not a bug.
  - **Use it for:** fold vs call vs value 3-bet with strong hands, and how the answer moves
    between opener types. Fold where it 3-bets trash.
  - A fix (a flat call share across 3-bet sizes, R by hand playability) needs its own entry
    and a re-gate. Ian decides.

## Drills and hand review

Two tools build on this engine:
- **`showdown sixmax drill`** deals practice spots. It grades the action and its size on
  GTO Wizard's scale against player types (DECISIONS 60, Gate Y PASS). Gate K's kind-only
  drill (DECISIONS 55) stays as its record.
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
at work, not a mistake by Pluribus (see "Limping" above). Raised pots, which are 45% of Pluribus's hands, are not
graded. There is no Poker Now log parser yet.
