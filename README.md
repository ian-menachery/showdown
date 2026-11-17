# showdown

A heads-up poker lab in Python. One game ties it together: heads-up push/fold,
at effective stacks from 1 to 20 big blinds.

- **A CFR solver.** It was proven on Kuhn and Leduc against OpenSpiel, then used
  to solve push/fold at every depth.
- **An equity engine.** It includes an exact 169×169 preflop all-in matrix,
  which is the push/fold game's payoff table.
- **A push/fold trainer and a Leduc bot.** Both play in a local browser page.
  The trainer grades every decision in big blinds lost against Nash.
- **A hand-history analyzer.** It reports the usual stats and all-in
  EV-adjusted results, and grades short heads-up hands against the solved
  strategy.

**Status: Phases 1 to 7 done (2026-11-14). Gates A to F PASS.** Every number
below comes from [`GATES.md`](GATES.md), which records each measurement against
a bar set before the code existed (SCOPE, DECISIONS 11).

| Gate | What is checked against an outside answer | Headline result |
|---|---|---|
| A: Kuhn | the known equilibrium family; OpenSpiel's exploitability | exploitability 8.7e-5 after 1,000 CFR+ iterations; game value within 3.6e-7 of −1/18 |
| B: Leduc | OpenSpiel's `CFRPlusSolver` | **bit-identical** policies at every iteration; 3.6× to 11.5× faster than OpenSpiel's Python |
| C: equity | phevaluator; pokerkit | 100,000 of 100,000 showdowns agree; 20 of 20 exact enumerations identical; Monte Carlo calibrated (189 of 200 within 2 SE) |
| D: push/fold | HoldemResources' published heads-up equilibrium | exploitability ≤ 3.6e-6 bb at all 20 depths; 100% agreement in all 40 pre-registered comparisons |
| E: bot and engine | pokerkit's NLHE state machine | 20,000 bot-vs-bot hands land at z = +0.19 against the solver's value; 20 scripted hands of each game over HTTP |
| F: analyzer | a hand-counted fixture; the phh-dataset | 945 of 945 stat values exact; 17 all-in EVs within 1e-6 bb; 10,000 of 10,000 Pluribus hands parse |
| G: live advisor V1 | hand-counted equities; the push/fold solution | 43 of 43 spots; river and turn equity exact; flop within 3 SE; 95th-percentile 65–70 ms (bar 300 ms) |

Beyond the gates:
- The exact matrix equals an independent exact table (b-inary/poker-cfr) to
  the integer in every cell.
- HoldemResources' strategies, scored on our exact game, have exploitability of
  at most 1.0e-6 bb. So their equilibrium is also an equilibrium of ours.

## Try it

```powershell
showdown solve kuhn --iterations 1000          # the near-Nash strategy, with exploitability
showdown solve leduc --iterations 1000 --every 250
showdown equity AsKs QhQd --board Ts9s2dJc     # exact: 13 of 44 rivers win
showdown equity "TT+,AK" "22-99"                # Monte Carlo, with a standard error
showdown matrix show AKs QQ                     # exact, from data/preflop_169_exact.npz
showdown pushfold chart 10                      # SB jam and BB call charts at 10 bb
showdown play                                   # trainer and Leduc in your browser, 127.0.0.1 only
showdown analyze path/to/hands                  # PHH files, or PokerStars .txt exports
showdown advise --hero AsKd --seat sb --stack 10   # live advisor V1: push/fold preflop, equity helper postflop
```

`showdown analyze` prints, per player:
- VPIP, PFR, 3-bet, WTSD and W$SD;
- bb/100, raw and all-in EV-adjusted;
- push/fold grades for heads-up hands at 20 bb effective or less.

The exact definitions are in DECISIONS 25 to 27.

## Start here

1. [`SCOPE.md`](SCOPE.md): what is in and out, the borrow-vs-build table, the
   pre-registered gates, the phases, the open questions and the amendments
   log.
2. [`DECISIONS.md`](DECISIONS.md): 27 numbered, settled decisions. Read them
   before proposing anything they rule out.
3. [`GATES.md`](GATES.md): every gate's measured numbers against its bar, and
   the commands that reproduce them.
4. [`docs/`](docs/): how each stretch was planned:
   - `plan-phases-1-3.md` and `plan-phases-4-7.md`, the latter holding Ian's
     answers that bound the autonomous run;
   - `gate-d-reference.md`, on the push/fold reference and how to fetch the
     reference data;
   - `design-review-phases-5-6.md`, the pokerkit facts the bot and analyzer
     rely on.
5. [`spikes/`](spikes/): one-off checks with their outputs. They cover the
   dependency spike, the reference data, and the Gate D report.

## Setup (Windows, Python 3.12)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
py gate.py
```

`gate.py` is the definition of done. It runs:

- ruff check and ruff format --check;
- pytest, with an 80% coverage floor;
- a check that the tree is clean and HEAD is pushed.

It uses `.venv` automatically. `py gate.py --full` adds the slow gate-evidence
tests (about 17 minutes on an idle 16-core machine). They include:
- OpenSpiel's 200-iteration Leduc run;
- exact preflop enumerations;
- a 10 bb push/fold re-solve;
- 20,000 simulated hands;
- the Pluribus run.

The slow suite needs the reference data in `data/external/`. See below.

## Layout

```
src/showdown/
  games/       game interface; Kuhn, Leduc, push/fold
  cfr/         compiled tree, CFR and CFR+, best response, exploitability
  equity/      cards and classes, ranges, exact, Monte Carlo, 169x169 matrix, multiway pots
  pushfold.py  push/fold solve, charts, closed forms, Gate D comparison
  engine/      pokerkit adapter: one heads-up push/fold hand
  bot/         strategies and grading, play sessions, the 127.0.0.1 server and page
  hh/          replay through pokerkit, stats, all-in EV, push/fold grading
  cli.py       showdown solve | equity | matrix | pushfold | play | analyze
data/preflop_169.npz         Monte Carlo matrix, Gate C evidence (DECISIONS 18)
data/preflop_169_exact.npz   exact matrix, the push/fold payoffs (DECISIONS 21)
data/pushfold.json           push/fold solutions at 1 to 20 bb (DECISIONS 22)
data/leduc_cfr_plus.json     the Leduc bot's strategy (CFR+, 1,000 iterations)
data/external/               third-party reference data, gitignored (DECISIONS 20, 25)
tests/fixtures/hh/           the Gate F fixture: 34 hands and their hand-counted stats
```

## Borrowed code

| Library | Version | License | Used for |
|---|---|---|---|
| [pokerkit](https://github.com/uoftcprg/pokerkit) | 0.7.7 | MIT | NLHE state machine, hand-history parsing |
| [eval7](https://github.com/JulianAndrews/pyeval7) | 0.1.11 | MIT | `evaluate` only (DECISIONS 5) |
| [OpenSpiel](https://github.com/google-deepmind/open_spiel) | 2.0.2 | Apache-2.0 | test oracle, dev only |
| [phevaluator](https://github.com/HenryRLee/PokerHandEvaluator) | 0.6.0 | Apache-2.0 | test oracle, dev only |

No library source is copied into this repo. Everything comes in through pip at
the versions pinned in `pyproject.toml`. The play page uses only the Python
standard library and plain HTML and JS, and it loads nothing from the network.

**Built here:**
- the game interface and all three games;
- CFR, CFR+ and best response;
- every equity calculation, both matrices included;
- the push/fold solve and its charts;
- the bots, the trainer and the play server;
- the replay, stats, all-in EV and grading in the analyzer.

## Reference data (downloaded, never committed)

Three data sets are used only as outside answers in tests and spikes. They
live in the gitignored `data/external/`, pinned by SHA-256 (DECISIONS 20 and
25). The fetch commands are in
[`docs/gate-d-reference.md`](docs/gate-d-reference.md). `py gate.py --full`
fails without them; it never skips.

| Source | License | Used for |
|---|---|---|
| [HoldemResources.net](https://www.holdemresources.net/hune) heads-up push/fold raw data | none stated | Gate D reference |
| [b-inary/poker-cfr](https://github.com/b-inary/poker-cfr) exact preflop equity table | BSD-2-Clause | checks every cell of the exact matrix |
| [phh-dataset](https://github.com/uoftcprg/phh-dataset) Pluribus hands (10,000, commit e47fbd5) | MIT | Gate F parse rate; Done 4 |

## Known limits

- **Push/fold is class-level.** Hands are grouped into the 169 classes. Every
  combo in a class plays, and is graded, like the class. Card removal is
  counted exactly between classes.
- **Push/fold covers one game only.** That is jam-or-fold for the small blind
  and call-or-fold for the big blind, with no ante and chip EV. There are no
  limps, min-raises, antes or ICM.
- **Solutions exist at integer depths only.** A real hand at 7.3 bb is graded
  against the 7 bb solution, and the depth used is printed.
- **Some all-in EV is estimated.** It is exact whenever two board cards or
  fewer are to come, and for any heads-up all-in. Multiway preflop all-ins use
  seeded Monte Carlo (20,000 runouts by default), and the standard error is
  printed.
- **Heads-up preflop all-ins are slow to adjust.** Each one is enumerated
  exactly, which takes a few seconds. The 10,000 Pluribus hands take about 100
  s.
- **PokerStars parsing has pokerkit's limits.** Only no-limit hold'em. Antes
  and rake are not parsed. Opponents' cards are known only when shown.
- **A hand counts as parsed only if its replay reconciles.** The replayed
  stacks must equal the recorded finishing stacks, and failures are counted
  and printed. Odd-chip chops (8 of the 10,000 Pluribus hands) are flagged
  rather than failed.
- **The Pluribus hands are not gradable.** They are 6-max at 100 bb, so no
  hand fits the push/fold game.
- **The play page is limited.** It serves 127.0.0.1 only and keeps sessions in
  memory. Leduc is played but not graded.
- **Python 3.11 or 3.12 only,** because eval7 has no wheel for 3.13
  (DECISIONS 10). It has been tested on Windows only.

## Not this

Nothing here touches live play: no HUD, no overlay, no table reading, and no
connection to any poker site (DECISIONS 9).

**Do not run showdown while a ClubWPT Gold client is open.** That includes the
equity tool, the charts, the trainer and the analyzer. ClubWPT Gold's
prohibited-tools page bans equity and range tools "while the game client is
open", and it also bans strategy charts and range matrices. Study after the
session is over (DECISIONS 13).

## License

MIT ([`LICENSE`](LICENSE)), except [`bridges/postflop/`](bridges/postflop/),
which links an AGPL solver and is licensed AGPL-3.0-or-later (see its README).
