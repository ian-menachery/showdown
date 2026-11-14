# showdown

A heads-up poker lab in Python:

- a CFR solver, proven on Kuhn and Leduc against known answers;
- an equity engine;
- a push/fold bot you can play against in the terminal;
- a hand-history analyzer that grades real hands against the solved strategy.

**Status: Phase 0, plan only.** There is no solver code yet. The package is a
stub, so the gate passes on a smoke test.

## Start here

1. [`SCOPE.md`](SCOPE.md): what is in and out, the borrow-vs-build table, the
   pre-registered gates A to F, the phase order, and the open questions.
2. [`DECISIONS.md`](DECISIONS.md): numbered, settled decisions. Read them before
   proposing anything they rule out.
3. [`spikes/2026-11-14-deps.py`](spikes/2026-11-14-deps.py): the dependency
   check behind decisions 5, 6 and 10, with its output.

## Setup (Windows, Python 3.12)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
py gate.py
```

`gate.py` is the definition of done. It runs ruff check, ruff format --check,
pytest with an 80% coverage floor, and a clean-tree check that HEAD is pushed.
It uses `.venv` automatically when that folder exists.

## Planned layout

```
src/showdown/
  games/      game interface; kuhn, leduc, pushfold
  cfr/        CFR, CFR+, best response, exploitability
  equity/     combos and ranges, exact enumeration, Monte Carlo, 169x169 matrix
  engine/     pokerkit adapter
  bot/        policies and terminal play
  hh/         hand-history parsing, stats, all-in EV
  cli.py      showdown solve | equity | play | analyze
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
