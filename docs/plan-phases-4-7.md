<!-- Copied from the approved plan of 2026-11-14 so it lives with the repo. Ian's answers in the table below bind the run (SCOPE A5). -->

# showdown: autonomous run, Phases 4 to 7

Repo: `C:\Users\ianme\projects\showdown`. Push to `main`; `py gate.py` defines
done. Read SCOPE, DECISIONS, GATES and this plan before each phase.

## Context

Phases 0 to 3 are done (Gates A to C PASS). Phase 4 is half built:
- **Pushed:** DECISIONS 22, which pre-registers Gate D's comparison rule.
- **Written, not committed:** `games/pushfold.py`, `pushfold.py`, the
  `pushfold` CLI and the tests.
- **Running:** the pre-registered solve (1 to 20 bb, `cfr_plus` with 1,000
  iterations) is running in the background and writes `data/pushfold.json`.

Ian asked for one long plan that can run to the end without questions. So every
open call was asked on 2026-11-14 and is recorded below. The run finishes
Phase 4, then builds Phase 5 (bot and browser play), Phase 6 (hand-history
analyzer) and Phase 7 (README truth pass). Each phase ends at its
pre-registered gate.

## Ian's answers (2026-11-14), which bind the run

| Topic | Answer |
|---|---|
| Scope of the run | Finish Phase 4, then Phases 5, 6 and 7 |
| A gate fails | Reproduce it and fix it once, if the cause is a clear code bug. Never move the threshold. Record it in DECISIONS and re-run. If it still fails, **stop the run** and write it up |
| Process | SCOPE amendment A5 (Phases 4 to 7 in one autonomous stretch). Commit and push to `main` at every gate PASS |
| Web stack | stdlib `http.server` (`ThreadingHTTPServer`) on 127.0.0.1, a JSON API, one vanilla HTML/JS page. No new dependencies |
| Trainer | Choose the seat (SB, BB or alternating) and either a fixed depth from 1 to 20 bb or a random integer depth each hand. Show the board and result on a called all-in. Session summary |
| Downloads | Pluribus hands from phh-dataset (MIT, commit `e47fbd5`, `data/pluribus` only, about 5.6 MB) into the gitignored `data/external/phh/`. No other downloads |
| Multiway all-in EV | Heads-up all-ins exact, **and** multiway all-ins adjusted too: exact on the turn and river, seeded Monte Carlo with an SE preflop and on the flop, with side pots |
| Stacks between solved depths | Grade at the nearest integer depth, and print which depth was used |
| Going public (Open question 5) | **Stay private.** No LICENSE change, no visibility change. The README is written as if public |
| ClubWPT (Open question 6) | No ClubWPT code (DECISIONS 13) |

## Run rules (apply in every phase)

- **Gate discipline.** Thresholds never move (DECISIONS 11). A failure gets one
  diagnose-and-fix: reproduce it first, then fix the code, record the cause in
  DECISIONS, and re-run. A second failure stops the run with a write-up in
  GATES.md and the final message.
- **Commits.** One or more per phase, each passing `py gate.py`. Each gate PASS
  is pushed to `main` (the repo is private), with the Co-Authored-By trailer.
- **Never:**
  - change the repo's visibility, licence, branch protection or settings;
  - send anything to any service except `git push` to this private repo;
  - download anything except the approved Pluribus hands;
  - bind to anything but 127.0.0.1 (DECISIONS 12);
  - touch ClubWPT;
  - add dependencies (Phase 5 uses the stdlib; Phase 6 uses pokerkit, which is
    already pinned).
- **Decisions are written down.** Every design choice a phase needs gets a
  DECISIONS entry before the code relies on it: entry 23 onward.
- **Slow work** (solves, 20,000-hand simulations, the Pluribus run) runs in the
  background. Anything over about 10 s is marked `@pytest.mark.slow`.
- **Evidence.** Every gate number goes into GATES.md with the command that
  reproduces it. Every claim in the README is checked against GATES.md.
- **Browser checks** use the built-in browser pane on
  `http://127.0.0.1:<port>` only.

---

## Phase 4: finish (Gate D)

1. Wait for the background `showdown pushfold build`. Read its per-depth table:
   exploitability, SB value, jam %, call %.
2. Run `py -m pytest tests/test_pushfold.py tests/test_gate_d.py`, then
   `tests/test_gate_d_slow.py -m slow` (the HoldemResources comparison, all 20
   exploitabilities, and the 10 bb re-solve, which takes about 4 min).
3. **If Gate D fails:** apply the gate-failure rule. Likely suspects, in order:
   - seat or action mapping (push vs call, SB vs BB keys);
   - class-order mapping in the CSV load (`names.index`);
   - the stack definition.
   Never re-solve with different iterations.
4. Run the scratchpad report script (`gate_d_report.py`; recreate it under
   `spikes/2026-11-14-gate-d-report.py` so it is committed). It produces:
   - the 20-row table for GATES.md: exploitability, SB value, jam %, call %,
     agreement with compared and excluded counts per seat, and the
     disagreements;
   - beyond the gate: the SB value and exploitability of HoldemResources'
     strategies scored on our exact game, and the largest probability
     difference.
5. Record the results:
   - **GATES.md:** the Gate D section, with every bar, PASS or FAIL, and the
     commands;
   - **SCOPE.md:** amendment A5 (the autonomous Phases 4 to 7 run);
   - **README:** status "Phases 1 to 4, Gates A to D", Try-it lines for
     `pushfold chart 10` and `pushfold build`, and the layout.
6. Commit the code, data and results, run `py gate.py`, and push.

---

## Phase 5: bot, engine adapter, local browser play (Gate E)

### Decisions first (DECISIONS 23, 24)
- **23. Play server.**
  - stdlib `ThreadingHTTPServer` bound to 127.0.0.1, with port 0 or a `--port`
    option. It refuses any other host.
  - The JSON API and its endpoint list.
  - Sessions live in memory, keyed by a random id. There are no accounts.
  - Static files are served from the package, not the network.
  - The page is vanilla HTML/JS, with no CDN.
- **24. Engine adapter and grading.**
  - Chips are integers in pokerkit, scaled ×2: SB 1, BB 2, stack 2S.
  - The heads-up seat order follows pokerkit (verified in a test).
  - Grading is at the class level: bb lost = EV(best action) − EV(chosen
    action) against the opponent's Nash strategy at that depth, from the exact
    matrix. A combo inherits its class's grade.
  - The bot samples its mixed strategy with a seeded `random.Random`.
  - The Leduc bot uses `cfr_plus` with 1,000 iterations (Gate B), committed as
    `data/leduc_cfr_plus.json` through the existing `solve --out`.

### Build
1. **`src/showdown/engine/pokerkit_adapter.py`: one heads-up push/fold hand.**
   - It builds a `pokerkit.NoLimitTexasHoldem.create_state` with automations
     for blinds, bet collection, card burning, chip pushing and pulling, and
     showdown. Hole dealing and board dealing are explicit, so tests can fix
     the cards.
   - API: `deal(rng)`, then `sb_action(fold|all-in)` and
     `bb_action(fold|call)`, then the result. The result holds the cards, the
     board, each player's chip delta in bb, and the class pair.
   - Tests check:
     - the seat roles, meaning who posts 0.5 and who acts first;
     - fixed-card hands (AA vs KK on a fixed board: chip deltas exact);
     - folds (−0.5, +1);
     - a split pot.
2. **`src/showdown/bot/policy.py`:**
   - `PushFoldBot(solution, depth, seat, rng)` and `LeducBot(policy, rng)`;
   - `grade_sb(class, depth, action)` and `grade_bb(...)`, which use
     `pushfold.sb_value` pieces. Put a per-class EV helper in `pushfold.py`
     and reuse it.
3. **`src/showdown/bot/server.py` and `src/showdown/bot/static/index.html`
   (with inline JS and CSS).** Endpoints:
   - `POST /api/session` with game, seat, depth mode and depth;
   - `POST /api/hand`, which deals;
   - `POST /api/act`, which returns the bot's response, the grade, the result
     and the running summary;
   - `GET /api/summary`.
   For Leduc, the hand runs on `games/leduc.py` states with the bot's
   `LeducBot`, and the page shows each street, the bot's action and the result.
4. **`showdown play [--port] [--no-browser]`:** starts the server, prints the
   URL, and opens it with `webbrowser` unless `--no-browser` is given.
   Following the memory note "launch apps outside Claude's package", it opens
   through the default handler. The browser-pane check uses the URL directly.
5. **Gate E tests:**
   - `tests/test_gate_e.py` (fast): the API completes 20 scripted hands of
     push/fold (both seats, fixed and random depth) and 20 of Leduc, through
     real HTTP against a server on an ephemeral 127.0.0.1 port. It also checks
     the summary totals against the per-hand grades.
   - `tests/test_gate_e_slow.py`: 20,000 bot-vs-bot hands at 10 bb through the
     pokerkit adapter, seeded. It checks |realised SB mean − solver value| ≤ 3
     SE, where the SE is the per-hand sample SD over √n. It also asserts the
     bind address is 127.0.0.1.
6. **Done 3 check in the browser pane:**
   - a full push/fold session (one fixed-depth and one random-depth, both
     seats), with the board shown, the grades and the summary;
   - a full Leduc session.
   Screenshots go in the final message, not the repo.
7. Record in GATES.md (Gate E) and the README (status, how to play,
   localhost-only note). Run `py gate.py --full`, commit and push.

---

## Phase 6: hand-history analyzer (Gate F)

### Data (approved)
Sparse-clone `uoftcprg/phh-dataset` at commit `e47fbd5` with `--filter=blob:none`
and `sparse-checkout set data/pluribus` into a new empty directory under the
gitignored `data/external/phh/`. Then:
- record the commit and a SHA-256 manifest (a hash over the sorted per-file
  hashes) in DECISIONS;
- add it to `tests/external_data.py` and the fetch commands in a docs note;
- treat the files as untrusted data: read them, never execute them.

### Decisions first (DECISIONS 25 to 27)
- **25. Stat definitions** (finalised from the design review). For each stat:
  - VPIP: voluntary chips preflop (blinds and checks don't count);
  - PFR: any preflop raise;
  - 3-bet: the opportunity (facing exactly one raise preflop) and whether it
    was made;
  - WTSD: saw the flop and reached showdown;
  - W$SD: won money at showdown;
  - bb/100: net chips over the big blind, per 100 hands;
  - all-in EV-adjusted bb/100: the expected net after the money is all in,
    with side pots and uncalled bets returned.
  Each definition comes with the counting rule for edge cases: walks, the
  big blind's option, all-ins, and short all-ins that don't reopen.
- **26. All-in EV.**
  - The adjustment point is the first moment every remaining player's chips
    are all in (or no further betting is possible). Pots are built from each
    player's total contribution.
  - Per pot, the share is the expected fraction of that pot among its eligible
    players. It is exact by enumeration when 2 or fewer cards are left to come,
    or when the pot is heads-up preflop. Otherwise it is seeded Monte Carlo
    with a stated SE.
  - The oracles are our heads-up `exact.hand_vs_hand` and pokerkit's
    `calculate_equities` (tests only).
- **27. Grading.** A hand is graded when it is heads-up, effective ≤ 20 bb, and
  the SB's first action is fold or all-in. The BB is graded only facing a jam.
  It uses the nearest integer depth, which is printed. Hands outside the game
  are counted as "not gradable" with a reason.

### Build
1. **`src/showdown/hh/parse.py`:** `load_phh(path)` returns `HandHistory`
   objects (`HandHistory.load`), and `load_pokerstars(text)` uses
   `HandHistory.from_pokerstars`. Failures are counted with their reasons and
   never dropped (Gate F).
2. **`src/showdown/hh/replay.py`:** walks each hand's pokerkit states into a
   normalised action log per player and street: contributions, all-in point,
   showdown and net result.
3. **`src/showdown/hh/stats.py`:** the per-player stats from DECISIONS 25, and
   the totals.
4. **`src/showdown/equity/multiway.py`:**
   - `pot_shares(hands, board, pots, seed, samples)`: exact enumeration of the
     runouts when cheap, otherwise Monte Carlo with an SE, using eval7
     `evaluate` only (DECISIONS 5).
   - Tests: heads-up results equal `exact.hand_vs_hand`; 3-way results agree
     with pokerkit `calculate_equities` within 3 SE; side-pot eligibility is
     checked on hand-built cases.
5. **`src/showdown/hh/allin_ev.py`:** the EV-adjusted net per player per hand,
   plus the count of multiway and Monte Carlo adjustments.
6. **`src/showdown/hh/grade.py`:** push/fold grading against
   `data/pushfold.json` (DECISIONS 27).
7. **`showdown analyze <file-or-dir> [--format phh|pokerstars] [--player NAME]`:**
   prints the stats table, the all-in EV-adjusted bb/100, a parse summary
   (parsed and failed, with reasons) and a grading summary.
8. **The Gate F fixture:**
   - `tests/fixtures/hh/` holds at least 30 hand-written PHH hands of our own:
     heads-up and 6-max, walks, 3-bets, showdowns won and lost, heads-up
     all-ins on every street, and multiway turn/river all-ins with a side pot,
     so they are exact.
   - It includes at least 5 short-stack heads-up push/fold hands for grading,
     and 3 PokerStars-format text hands written by us.
   - `tests/fixtures/hh/expected.json` holds every stat counted by hand, with
     the arithmetic written in a comment per hand.
9. **Gate F tests:**
   - `test_gate_f.py` (fast): fixture stats match exactly; the all-in EV
     adjustments match the hand-computed values to 1e-6 bb (exact cases only;
     Monte Carlo cases are checked against pokerkit within 3 SE in a separate
     test).
   - `test_gate_f_slow.py`: at least 99% of the 10,000 Pluribus hands parse.
     Failures are printed with reasons. It also runs `showdown analyze` on all
     of them (Done 4) and checks player and hand totals.
10. Record in GATES.md (Gate F), and in the README (`analyze` usage and
    stats definitions). Run `py gate.py --full`, commit and push.

---

## Phase 7: README truth pass (Done 1 to 5)

1. **README rewrite.** It must cover:
   - what each part does;
   - the borrowed table (pokerkit, eval7, OpenSpiel, phevaluator, with versions
     and licences);
   - the reference-data table (HoldemResources, b-inary, phh-dataset);
   - every gate's headline numbers, linked to GATES.md;
   - the known limits: class-level push/fold abstraction, integer depths, no
     antes or ICM, multiway Monte Carlo SE, Pluribus 6-max hands not
     gradable, localhost only;
   - the ClubWPT warning (DECISIONS 13).
2. **Check Done 1 to 5 one by one:**
   1. `py gate.py` passes;
   2. Gates A to F pass in GATES.md;
   3. the browser sessions from Phase 5;
   4. `showdown analyze` on Pluribus;
   5. the README.
   Record the results in GATES.md under "Done".
3. **SCOPE:**
   - Open question 5: answered "stay private for now"; Ian flips visibility
     himself.
   - Open question 6: still open.
   - The amendments log is up to date.
4. Update the memory file (`project_showdown.md` and its MEMORY.md line).
   Final `py gate.py --full`, commit and push.

---

## Design review
A read-only reviewer is checking:
- pokerkit's heads-up seat order;
- integer chips;
- dealing fixed cards;
- `HandHistory` iteration and `from_pokerstars`;
- the exact stat definitions;
- the top risks.

Its findings go into DECISIONS 23 to 27 before the code they affect is
written. If any finding contradicts this plan, the plan's intent stands, and
the deviation is recorded in DECISIONS.

## Stop conditions
- A gate fails twice (see Run rules). Stop, commit the evidence (not the
  failing feature) and report.
- A required download fails or its hash changes. Stop Phase 6 and report.
- Anything would need a new dependency, a scope change, a public action, or a
  site other than localhost or this repo's remote. Stop and ask.

## Verification (end to end)
- `py gate.py` and `py gate.py --full` pass at each phase's final commit.
- **Gate D:** 40 comparisons, all PASS. Exploitability ≤ 0.001 bb at all 20
  depths. The 1 bb all-jam check holds.
- **Gate E:** the 20,000-hand result is within 3 SE of the solver value, and 20
  scripted hands of each game complete over HTTP.
- **Gate F:** fixture stats are exact, all-in EV is within 1e-6 bb, and at
  least 99% of Pluribus hands parse.
- **Manual:**
  - `showdown pushfold chart 10`;
  - `showdown play`, with full trainer and Leduc sessions in the browser pane;
  - `showdown analyze data/external/phh/data/pluribus`.

## Files (main ones)
- **Phase 4:** `src/showdown/games/pushfold.py`, `src/showdown/pushfold.py`,
  `data/pushfold.json`, `tests/test_pushfold.py`, `tests/test_gate_d*.py`.
- **Phase 5:** `src/showdown/engine/pokerkit_adapter.py`,
  `src/showdown/bot/{policy,server}.py`, `src/showdown/bot/static/index.html`,
  `data/leduc_cfr_plus.json`, `tests/test_gate_e*.py`.
- **Phase 6:** `src/showdown/hh/{parse,replay,stats,allin_ev,grade}.py`,
  `src/showdown/equity/multiway.py`, `tests/fixtures/hh/`,
  `tests/test_gate_f*.py`.
- **Always:** `src/showdown/cli.py`, `DECISIONS.md`, `GATES.md`, `SCOPE.md`,
  `README.md`, `tests/external_data.py`.
- **Reused:**
  - `compile_game`, `cfr_plus`, `exploitability`, `policy_value` and
    `solve --out` (CLI);
  - `PreflopMatrix` and `exact.hand_vs_hand`;
  - `ranges` and `cards` helpers;
  - `pushfold.sb_value`, `closed_form_exploitability` and `compare`;
  - `tests/external_data.require`.
