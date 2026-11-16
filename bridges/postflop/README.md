# bridges/postflop

showdown's bridge to b-inary's
[postflop-solver](https://github.com/b-inary/postflop-solver), pinned at
commit `9d1509fe5077d019825f833eed04b16d342dfda1` (DECISIONS 38, 40).

**Licence.** The bridge links postflop-solver, which is licensed
AGPL-3.0-or-later, so this bridge is licensed AGPL-3.0-or-later too. The rest of
showdown only runs the compiled bridge as a separate process (DECISIONS 29).
The solver checkout and the compiled binary live in the gitignored
`data/external/postflop-solver/`. They are never committed or distributed.

**Build:** run `showdown postflop build`. It checks the solver checkout's
commit, then runs `cargo +1.100.0-x86_64-pc-windows-gnu build --release` with
`RUSTFLAGS=-A dangerous_implicit_autorefs`. That lint is new in Rust 1.100, and
the 2023 solver trips it (Gate S4's record).

**Protocol.** The bridge reads one JSON spot on stdin and writes one JSON
result on stdout.
- **The spot:**
  - ranges, flop, pot and stack in chips (0.1 bb), and the tree's bet sizes;
  - the target as a % of the pot, and the maximum iterations;
  - `locks`: a list of `{path, rule}`;
  - `report`: a list of paths.

  A path is a list of action labels from the flop root (`Check`, `Bet`,
  `Call`, `Fold`, `Raise`, `AllIn`). `Bet` is the smallest bet.
- **Lock rules:**
  - `call`, `check` and `bet` put every hand on that action;
  - `fold_weakest` with a `fraction` folds that share of the acting player's
    range, weakest first by flop equity, and calls with the rest.
- **The result:**
  - the solve's exploitability and iterations;
  - each lock's applied strategy;
  - each reported node's per-hand strategy, normalized weights and equity;
  - both players' average EV at the root.
