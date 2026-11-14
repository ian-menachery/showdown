# showdown

A heads-up poker lab in Python:

- a CFR solver, proven on Kuhn and Leduc against known answers;
- an equity engine;
- a push/fold bot you can play against in a local browser page;
- a hand-history analyzer that grades real hands against the solved strategy.

**Status: Phases 1 to 3 done (2026-11-14). Gates A, B and C PASS.** See
[`GATES.md`](GATES.md) for every number.

- **Solver.** CFR and CFR+ are **bit-identical to OpenSpiel's** on Kuhn and
  Leduc: equal policies at every iteration, and the same exploitability double.
  On Leduc the solver ran 3.6× to 11.5× faster than OpenSpiel's Python
  implementation across the recorded runs.
- **Equity.** The engine agrees with phevaluator on 100,000 random showdowns and
  20 exact enumerations. It ships a 169×169 preflop matrix in which every cell
  has a standard error of at most 0.002.

Next is Phase 4, the push/fold game. It needs Open question 4 (which reference
chart Gate D compares against) settled first.

## Try it

```powershell
showdown solve kuhn --iterations 1000          # prints the near-Nash strategy
showdown solve leduc --iterations 1000 --every 250
showdown equity AsKs QhQd --board Ts9s2dJc     # exact: 13 of 44 rivers win
showdown equity "TT+,AK" "22-99"                # Monte Carlo, with a standard error
showdown matrix show AKs QQ                     # from data/preflop_169.npz
```

## Start here

1. [`SCOPE.md`](SCOPE.md): what is in and out, the borrow-vs-build table, the
   pre-registered gates A to F, the phase order, and the open questions.
2. [`DECISIONS.md`](DECISIONS.md): numbered, settled decisions. Read them before
   proposing anything they rule out.
3. [`GATES.md`](GATES.md): each gate's measured numbers against its bar.
4. [`docs/plan-phases-1-3.md`](docs/plan-phases-1-3.md): how phases 1 to 3 were
   designed.
5. [`spikes/2026-11-14-deps.py`](spikes/2026-11-14-deps.py): the dependency
   check behind decisions 5, 6 and 10, with its output.

## Setup (Windows, Python 3.12)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
py gate.py
```

`gate.py` is the definition of done. It runs:

- ruff check and ruff format --check;
- pytest, with an 80% coverage floor;
- a clean-tree check that HEAD is pushed.

It uses `.venv` automatically when that folder exists. `py gate.py --full` adds
the slow gate-evidence tests (about 4 minutes), including OpenSpiel's
200-iteration Leduc run and exact preflop enumerations.

## Layout

```
src/showdown/
  games/      game interface; kuhn, leduc          (pushfold: Phase 4)
  cfr/        compiled tree, CFR and CFR+, best response, exploitability
  equity/     cards and classes, ranges, exact, Monte Carlo, 169x169 matrix
  cli.py      showdown solve | equity | matrix     (play, analyze: Phases 5, 6)
  engine/     pokerkit adapter                     (Phase 5)
  bot/        policies, local play page and API    (Phase 5, 127.0.0.1 only)
  hh/         hand-history parsing, stats, all-in EV (Phase 6)
data/preflop_169.npz   the committed matrix (DECISIONS 18)
tests/openspiel_oracle.py   OpenSpiel as a reference, tests only
```

## Borrowed code

| Library | Version | License | Used for |
|---|---|---|---|
| [pokerkit](https://github.com/uoftcprg/pokerkit) | 0.7.7 | MIT | NLHE state machine, hand-history parsers |
| [eval7](https://github.com/JulianAndrews/pyeval7) | 0.1.11 | MIT | `evaluate` only (DECISIONS 5) |
| [OpenSpiel](https://github.com/google-deepmind/open_spiel) | 2.0.2 | Apache-2.0 | test oracle, dev only |
| [phevaluator](https://github.com/HenryRLee/PokerHandEvaluator) | 0.6.0 | Apache-2.0 | test oracle, dev only |

No library source is copied into this repo. Everything comes in through pip at
the versions pinned in `pyproject.toml`.

## Not this

Nothing here touches live play: no HUD, no overlay, no table reading, and no
connection to any poker site (DECISIONS 9).

**Do not run showdown while a ClubWPT Gold client is open.** That includes the
equity tool, the charts, the trainer and the analyzer. ClubWPT Gold's
prohibited-tools page bans equity and range tools "while the game client is
open", and it also bans strategy charts and range matrices. Study after the
session is over (DECISIONS 13).
