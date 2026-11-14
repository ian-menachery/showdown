# Plan: Phases 1 to 3 (solver core and equity engine)

Written 2026-11-14, before any of this code existed. Ian asked for the early core
phases to be built in one session while he was away, with no questions asked.
Calls that would normally have been his are recorded in DECISIONS 14 onward. The
SCOPE amendment for running three phases in one session is A4.

## Facts this plan is built on

All of these were measured on this machine against open_spiel 2.0.2.

- **OpenSpiel's CFR+.** `CFRPlusSolver` uses alternating updates, regret
  matching+ and linear averaging. The weight is the iteration number t times the
  player's own reach. Regrets are weighted by counterfactual reach, which includes
  chance. After each player's pass, regrets are clipped and the current policy is
  recomputed for every infoset. Nodes where every player's reach is 0 return 0.
- **OpenSpiel's exploitability.** It equals (BR0 + BR1 − utility_sum) / 2.
- **Kuhn.** Cards 0, 1, 2 are J, Q, K. The deal is P0, then P1. Actions are
  0 = pass and 1 = bet. There are 12 infosets and 24 decision nodes.
- **Leduc.** Cards 0 to 5, with rank = id // 2. The deal is P0, then P1, and the
  public card comes after round 1. Actions are 0 = fold, 1 = call and 2 = raise.
  - Fold is legal only when facing a bet.
  - At most 2 raises per round, of size 2 and then 4. The ante is 1.
  - P0 acts first in both rounds.
  - A pair beats no pair, otherwise the higher rank wins, and ties split.
  - 936 infosets, 3,780 decision nodes, 5,520 terminals, 157 chance nodes.

## Architecture

```
games/base.py     Game and State protocols; CHANCE and TERMINAL markers
games/kuhn.py     Kuhn, same action and chance encoding as OpenSpiel
games/leduc.py    Leduc, same encoding; infoset keys include suits
cfr/tree.py       compile a Game into flat preorder arrays (zero-sum checked)
cfr/solver.py     one CFR class with OpenSpiel's three flags; cfr() and cfr_plus()
cfr/best_response.py  exact best response, policy value, NashConv, exploitability
equity/cards.py   card ids (4*rank + suit), 1326 combos, 169 classes on a 13x13 grid
equity/evaluator.py   eval7.evaluate behind one function (DECISIONS 5)
equity/ranges.py  range strings: AA, AKs, TT+, A2s+, 22-55, AsKs, random
equity/exact.py   exhaustive heads-up equity (hand or range, any board), suit-canonical cache
equity/montecarlo.py  seeded Monte Carlo with a standard error
equity/matrix.py  169x169 preflop matrix, built board-major in numpy across processes
cli.py            showdown solve | equity | matrix
```

**Why a compiled tree.** Nodes are numbered in preorder, so a forward loop sees
parents before children and a reverse loop sees children first. CFR then works
on plain lists with no recursion and no per-node objects. OpenSpiel's Python CFR+
takes about 0.5 s per Leduc iteration, and Gate B requires us to be no slower.
The target is under 0.15 s.

**Why our CFR copies OpenSpiel's update order exactly.** Gate B only asks for
exploitability within 1.10× of OpenSpiel's. If the semantics are identical, a
stronger test becomes possible: the average policies match OpenSpiel's
iteration by iteration to about 1e-10. A bug cannot pass that test.

**Oracle tests live in `tests/`.** `tests/openspiel_oracle.py` walks our game and
OpenSpiel's in lockstep. At every node it checks the same node type, player,
legal actions, chance outcomes and probabilities, and terminal returns. It maps
our infoset keys to OpenSpiel's, one to one. That mapping translates policies
for the exploitability and trajectory comparisons. Nothing in `src/` imports
OpenSpiel (DECISIONS 6).

**Slow tests.** Anything over about 10 s is marked `slow`. The default run (and
`py gate.py`) skips them. `py gate.py --full` runs everything. Gate evidence goes
in `GATES.md`, with the commit, the date, the numbers and the command that
reproduces them.

## The 169×169 matrix (DECISIONS 18)

Brute force per combo pair takes about 5 s each, over 812,175 pairs, which is
far too slow. Instead, for each random 5-card board:

1. rank all 1,081 hands that do not touch the board, with eval7;
2. compare every pair of them with numpy, giving win or tie for about 580,000
   non-conflicting combo pairs from one board;
3. sum into 169×169 blocks with `np.add.reduceat`, with combos sorted by class.

Board sampling is unbiased. A random board that avoids a pair's 4 cards is
uniform over that pair's 48-card remainder, and every combo pair is equally
likely to be valid. The standard error comes from batch means over seeded
batches spread across worker processes, so the result does not depend on how
many workers ran it. The card-removal weights for push/fold (non-conflicting
combo-pair counts per class pair) are exact integers, not sampled.

## Gate tests, by phase

| Gate | Fast suite | Slow suite |
|---|---|---|
| A | lockstep vs OpenSpiel Kuhn; uniform exploitability to 1e-9; CFR and CFR+ trajectory equality; 1,000-iteration CFR+ exploitability, value and equilibrium-family checks | none |
| B | lockstep vs OpenSpiel Leduc; exploitability on 3 policies to 1e-9; first iterations equal OpenSpiel's | 200 iterations, ours vs OpenSpiel's: exploitability ratio and wall time |
| C | eval7 vs phevaluator on 100k random pairs; MC calibration over 200 seeds; matrix symmetry and SE ceiling; ranges and cards | AsAh vs KdKc exact; 20 matchups vs phevaluator enumeration and pokerkit MC; matrix cells vs exact class-vs-class |

## Order of work

1. Kuhn, tree, solver, best response, tests. Gate A. Commit and push.
2. Leduc and its oracle tests. Time the solver and optimise only if Gate B's
   timing fails. Gate B. Commit and push.
3. Cards, evaluator, ranges, exact, MC, matrix. Build and commit
   `data/preflop_169.npz`. Gate C. Commit and push.
4. Update README status, SCOPE amendment A4, GATES.md and memory.

Phase 4 (push/fold) is not started. It needs Open question 4, the reference
chart, and that is Ian's call.
