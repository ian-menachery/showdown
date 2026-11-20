"""Gate Q's seven bars (DECISIONS 49): the re-solved preflop model. Run with `py gate.py --full`.

Each test reads what the solves write and skips, with the reason, until that exists (Ian's
pick, 2026-11-19; a skip is never a pass, DECISIONS 6):
- bar 4 reads `data/preflop_r_fit.json` after both fit rounds (`showdown preflop fit-r`);
- the others read the product model, `data/preflop_model.json` once `showdown preflop build`
  has written it (and moved the old one to `data/preflop_model_v1.json`).

Bar 5's fixture, tests/fixtures/live/model_spots_q.toml, is written by hand from `showdown
preflop chart` after the product solve and before its test runs. Once the product model
exists, a missing fixture fails bar 5. Every count a bar names is asserted here.
"""

import functools
import json
import os
import random
import re
import subprocess
import sys
import tomllib
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
import pytest
from live_sim import FOUR_X_OPENING, phh_text, play
from pokerkit import HandHistory
from test_gate_q import TERMINALS_PER_DEAL, check_terminals
from test_gate_r_slow import HANDS, SEED, simulate
from test_preflop_fit import FLOPS

from showdown import preflop_fit
from showdown import preflop_model as pm
from showdown.cfr import compile_game, exploitability
from showdown.equity.cards import CLASS_NAMES, class_of, make_combo, parse_cards
from showdown.equity.matrix import PreflopMatrix
from showdown.games.preflop import POTS, PreflopGame
from showdown.live import hand, solve
from showdown.live.advisor import RAISES, Advisor
from showdown.live.spot import DECISIONS, Spot
from showdown.postflop.spot import SETTINGS, TREE_T1

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "tests" / "fixtures" / "live"
FIXTURE = LIVE / "model_spots_q.toml"
NOT_YET = "Gate Q evidence: needs {} (DECISIONS 49); not a pass"
FLOP_BINARY = "c45af752"
# Bar 1
SOLVES = 27
EXPLOITABILITY_MAX = 1e-3
# Bar 3
JAM_MAX, THREEBETS_MIN = 0.10, 0.05
# Bar 4
SETTLE = 0.02
CELLS = 9
# Bar 5
SPOTS_MIN, PER_DECISION, PER_SIZE, SUGGESTED_PER_SIZE, OFF_SIZE = 30, 4, 4, 2, 2
P95_MS = 300
# Bars 6 and 7
BAR6_MIN, BAR6_4X_MIN, BAR7_MIN = 100, 20, 30
FOUR_X_SEED, FOUR_X_HANDS, FOUR_X_CHIPS = 20261119, 200, (250, 1000)
"""Bar 6's 4x hands (DECISIONS 49's amendment): 200, seed 20261119, stacks of 25 to 100 bb."""
P95_S = {"turn": 3.0, "river": 1.0}
FIXES = ("fits the legal sizes", "more than can be matched", "is not legal here", "not fold")
"""DECISIONS 41's notes when the legality rule changes an action."""


@pytest.fixture(scope="module")
def model() -> pm.PreflopModel:
    found = pm.PreflopModel.load(ROOT / pm.DEFAULT_MODEL)
    if found.version != 2:
        pytest.skip(NOT_YET.format("the product solve, `showdown preflop build`"))
    return found


@pytest.fixture(scope="module")
def fit_data() -> dict:
    if not preflop_fit.FIT_PATH.exists():
        pytest.skip(NOT_YET.format("the R fit, `showdown preflop fit-r --round 1` and 2"))
    data = preflop_fit.load()
    if len(data["rounds"]) < 2:
        pytest.skip(NOT_YET.format("the R fit's round 2, `showdown preflop fit-r --round 2`"))
    return data


@pytest.fixture(scope="module")
def matrix() -> PreflopMatrix:
    return PreflopMatrix.load(ROOT / pm.DEFAULT_MATRIX)


# --- bar 1: exploitability --------------------------------------------------------------


def test_bar1_exploitability_at_every_depth_for_every_r_set(model) -> None:
    assert model.iterations == 1000 and model.checks == []
    got = sorted((s.stack, s.shift) for s in model.solutions)
    assert got == sorted((float(g), shift) for g in pm.GRID for shift in pm.SHIFTS)
    assert len(got) == SOLVES == len(pm.GRID) * len(pm.SHIFTS)
    for s in sorted(model.solutions, key=lambda s: (s.shift, s.stack)):
        print(f"{s.stack:>5g} bb, shift {s.shift:+.2f}: {s.exploitability:.2e} bb/hand")
    worst = max(s.exploitability for s in model.solutions)
    print(f"worst {worst:.2e} bb/hand (bar {EXPLOITABILITY_MAX:g})")
    assert worst <= EXPLOITABILITY_MAX


@pytest.mark.parametrize("stack", [25.0, 100.0])
def test_bar1_stored_exploitability_matches_a_fresh_best_response(model, matrix, stack) -> None:
    s = model.at(stack)
    tree = compile_game(PreflopGame(stack, matrix, r=s.r))
    policy = []
    for key in tree.infoset_key:
        _, name, node = key.split(":")
        policy.append(list(s.strategy[node][name]))
    assert exploitability(tree, policy) == pytest.approx(s.exploitability, abs=1e-12)


# --- bar 2: payoffs ---------------------------------------------------------------------


@pytest.mark.parametrize("stack", [25.0, 100.0])
@pytest.mark.parametrize("shift", list(pm.SHIFTS))
def test_bar2_every_terminal_matches_the_closed_form(model, matrix, stack, shift) -> None:
    r = model.at(stack, shift=shift).r
    tree = compile_game(PreflopGame(stack, matrix, r=r))
    checked = check_terminals(tree, matrix, stack, r)
    print(f"\n{stack:g} bb, shift {shift:+.2f}, R {r}: {checked} terminals")
    assert checked == 169 * 169 * TERMINALS_PER_DEAL


# --- bar 3: the jam lean at 50 bb -----------------------------------------------------


def bb_shares(s: pm.DepthSolution, pairs: np.ndarray) -> dict[str, float]:
    """The BB's actions facing the open, as shares of the deals that reach that decision:
    each BB class weighted by its combos against the SB's opening range."""
    sb_open = np.array([s.strategy[""][n][s.actions[""].index("raise")] for n in CLASS_NAMES])
    reaching = sb_open @ pairs.astype(float)
    rows = np.array([s.strategy["r"][n] for n in CLASS_NAMES])
    return dict(zip(s.actions["r"], reaching @ rows / reaching.sum(), strict=True))


def test_bar3_the_bb_jams_less_and_3bets_at_50_bb(model, matrix) -> None:
    old = pm.PreflopModel.load(pm.v1_model_path())
    for depth in (25, 50, 100):
        new = bb_shares(model.at(depth), matrix.pair_counts)
        was = bb_shares(old.at(depth), matrix.pair_counts)
        print(
            f"{depth} bb: "
            + ", ".join(f"{a} {p:.1%}" for a, p in new.items())
            + "; the old model: "
            + ", ".join(f"{a} {p:.1%}" for a, p in was.items())
        )
    shares = bb_shares(model.at(50), matrix.pair_counts)
    assert sum(shares.values()) == pytest.approx(1.0, abs=1e-9)
    assert shares["all-in"] <= JAM_MAX
    assert shares["raise"] + shares["raise 4x"] >= THREEBETS_MIN


# --- bar 4: R settles -----------------------------------------------------------------


def test_bar4_r_settles_between_the_rounds(fit_data) -> None:
    assert fit_data["seed"] == 20261119 and fit_data["flops"] == FLOPS
    assert fit_data["binary"].startswith(FLOP_BINARY)
    assert fit_data["tree"] == TREE_T1 and fit_data["settings"] == SETTINGS
    assert fit_data["iterations"] == 1000 and len(fit_data["rounds"]) == 2
    one, two = preflop_fit.round_cells(fit_data, 1), preflop_fit.round_cells(fit_data, 2)
    cells = [(p, d) for p in POTS for d in preflop_fit.FIT_DEPTHS]
    assert len(cells) == CELLS
    assert fit_data["rounds"][0]["preflop_r"] == {
        str(d): dict.fromkeys(POTS, 0.9) for d in preflop_fit.FIT_DEPTHS
    }
    assert fit_data["rounds"][1]["preflop_r"] == {
        str(d): {p: one[p][d]["r"] for p in POTS} for d in preflop_fit.FIT_DEPTHS
    }
    both = []
    for p, d in cells:
        for n, cell in ((1, one[p][d]), (2, two[p][d])):
            if cell["measured"]:
                assert [x["flop"] for x in cell["flops"]] == FLOPS, (n, p, d)
                assert cell["r"] == pytest.approx(np.mean([x["r"] for x in cell["flops"]]))
            print(
                f"round {n} {p:>4} {d:>3} bb: R {cell['r']:.4f}"
                + (f" (SE {cell['se']:.4f})" if cell["measured"] else f" ({cell['source']})")
            )
        if one[p][d]["measured"] and two[p][d]["measured"]:
            both.append((p, d))
    unmeasured = [(p, d, two[p][d]["r"]) for p, d in cells if (p, d) not in both]
    print(f"unmeasured in a round, not failing the bar: {unmeasured}")
    for pot in POTS:
        assert any(p == pot for p, _ in both), f"the {pot} pot is measured in both rounds nowhere"
    for p, d in both:
        change = abs(two[p][d]["r"] - one[p][d]["r"])
        assert change <= SETTLE, (p, d, change)


def test_the_product_uses_round_2s_r(model, fit_data) -> None:
    by_depth, stored = preflop_fit.product_r(fit_data)
    assert model.r_fit == stored
    for s in model.solutions:
        want = pm.shifted(by_depth[s.stack], s.shift)
        assert s.r == pytest.approx(want, abs=1e-12), (s.stack, s.shift)


# --- bar 5: advisor spots --------------------------------------------------------------


def _rows() -> list[dict]:
    if not FIXTURE.exists():
        return []
    return tomllib.loads(FIXTURE.read_text(encoding="utf-8"))["spots"]


ROWS = _rows()
SHOWN_AT_R = {"fold": "fold", "call": "call", "raise": "raise 3x", "raise 4x": "raise 4x"}
SHOWN_AT_R["all-in"] = "jam"
SHOWN = {"fold": "fold", "call": "call", "raise": "raise", "all-in": "jam"}


def faced_size(row: dict) -> str | None:
    """A 3-bet's size by DECISIONS 49's ratio rule, worked from the row: the faced 3-bet is
    (pot + to call) / 2; the BB's own, facing the jam, is the stack less the call."""
    if row["decision"] == "sb_vs_3bet":
        made = (row["pot"] + row["to_call"]) / 2
    elif row["decision"] == "bb_vs_4bet_jam":
        made = row["bb"] - row["to_call"]
    else:
        return None
    return "3x" if made / row.get("open", 2.5) <= 3.5 else "4x"


def node_of(row: dict) -> str:
    size = faced_size(row)
    node = DECISIONS[row["decision"]][1]
    if size == "4x":
        node = {"sb_vs_3bet": "r4", "bb_vs_4bet_jam": "r4j"}[row["decision"]]
    return node


def _spot(row: dict) -> Spot:
    return Spot.parse(
        row["hero"],
        seat=row["seat"],
        effective_bb=row["bb"],
        pot_bb=row.get("pot", 1.5),
        to_call_bb=row.get("to_call", 0.0),
        preflop=row["decision"],
        open_bb=row.get("open"),
    )


@functools.cache
def stored_json() -> dict:
    return json.loads((ROOT / pm.DEFAULT_MODEL).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def advisor(model, tmp_path_factory) -> Advisor:
    return Advisor.load(log_path=tmp_path_factory.mktemp("live") / "advice.jsonl")


def test_bar5_the_fixture_has_the_spots(model) -> None:
    assert FIXTURE.exists(), f"write {FIXTURE.name} by hand from `showdown preflop chart`"
    assert len(ROWS) >= SPOTS_MIN and all(r["bb"] > 20 for r in ROWS)
    for decision in DECISIONS:
        assert sum(r["decision"] == decision for r in ROWS) >= PER_DECISION, decision
    for decision in ("sb_vs_3bet", "bb_vs_4bet_jam"):
        for size in ("3x", "4x"):
            n = sum(r["decision"] == decision and faced_size(r) == size for r in ROWS)
            assert n >= PER_SIZE, (decision, size, n)
    suggested = Counter()
    for r in ROWS:
        if r["decision"] == "bb_vs_raise" and r["action"] == "raise":
            faced = (r["pot"] + r["to_call"]) / 2
            for size, times in (("3x", 3), ("4x", 4)):
                suggested[size] += abs(r["size"] - round(times * faced, 2)) < 1e-9
    assert suggested["3x"] >= SUGGESTED_PER_SIZE and suggested["4x"] >= SUGGESTED_PER_SIZE
    assert sum("note" in r for r in ROWS) >= OFF_SIZE


@pytest.mark.parametrize("row", ROWS, ids=lambda r: f"{r['hero']}-{r['bb']}-{r['decision']}")
def test_bar5_spot(model, advisor, row) -> None:
    s = advisor.suggest(_spot(row))
    assert s.action == row["action"], s
    assert s.source.startswith(f"model chart, fitted R, {row['depth']:g} bb ("), s.source
    assert ("depends on R" in s.notes) == row["r"]
    assert s.size_bb == row.get("size")
    size_notes = [n for n in s.notes if n.startswith("model assumes")]
    assert size_notes == ([row["note"]] if "note" in row else [])
    # The mix equals the stored strategy, read from the JSON without the model's loader.
    (stored,) = [
        x for x in stored_json()["solutions"] if x["stack"] == row["depth"] and x["shift"] == 0.0
    ]
    node = node_of(row)
    name = CLASS_NAMES[class_of(make_combo(*parse_cards(row["hero"])))]
    shown = SHOWN_AT_R if node == "r" else SHOWN
    want = {
        shown[a]: stored["strategy"][node][name][k] for k, a in enumerate(stored["actions"][node])
    }
    assert s.mix == pytest.approx(want, abs=1e-12)


_LATENCY_SCRIPT = r"""
import json, sys, time, tomllib
from showdown import preflop_model as pm
from showdown.live.advisor import Advisor
from showdown.live.spot import Spot
load = lambda p: tomllib.loads(open(p, encoding="utf-8").read())
fixture, model_fixture, jam_fixture, new = (load(p) for p in sys.argv[1:5])
fixed, old, model = Advisor.load(ranges="fixed"), Advisor.load(pm.v1_model_path()), Advisor.load()
jobs = []
for row in fixture["river"] + fixture["turn"] + fixture["flop"]:
    jobs.append((fixed, Spot.parse(row["hero"], row["board"], seat=row["seat"], effective_bb=50,
        pot_bb=row["pot"], to_call_bb=row["to_call"], pot_type=row.get("pot_type", "srp"),
        villain_range=row.get("villain"), mode=row.get("mode", "hint"))))
for hero, seat, bb, decision in fixture["preflop"]["spots"] + fixture["preflop"]["none"]:
    jobs.append((fixed, Spot.parse(hero, seat=seat, effective_bb=bb, preflop=decision)))
rows = model_fixture["spots"] + model_fixture["none"]
rows += model_fixture["range"] + model_fixture["range_flop"]
for row in rows:
    jobs.append((old, Spot.parse(row["hero"], row.get("board", ""), seat=row["seat"],
        effective_bb=row["bb"], pot_bb=row.get("pot", 1.5), to_call_bb=row.get("to_call", 0.0),
        pot_type=row.get("pot_type", "srp"), preflop=row.get("decision", "sb_first"))))
for row in jam_fixture["worked"] + jam_fixture["default"] + jam_fixture["none"]:
    jobs.append((old, Spot.parse(row["hero"], seat=row["seat"], effective_bb=row["bb"],
        pot_bb=row["pot"], to_call_bb=row["to_call"], preflop=row["decision"],
        villain_range=row.get("villain"), villain_top=row.get("villain_top"))))
for row in new["spots"]:
    jobs.append((model, Spot.parse(row["hero"], seat=row["seat"], effective_bb=row["bb"],
        pot_bb=row.get("pot", 1.5), to_call_bb=row.get("to_call", 0.0),
        preflop=row["decision"], open_bb=row.get("open"))))
times = []
for advisor, spot in jobs:
    start = time.perf_counter()
    advisor.suggest(spot)
    times.append((time.perf_counter() - start) * 1000)
print(json.dumps({"times": times, "new": len(new["spots"])}))
"""


def test_bar5_latency_over_the_old_and_new_spots(model) -> None:
    """DECISIONS 32's method: a separate process without coverage, on an idle laptop."""
    assert FIXTURE.exists(), f"write {FIXTURE.name} by hand from `showdown preflop chart`"
    env = {k: v for k, v in os.environ.items() if not k.startswith("COV_CORE")}
    paths = [LIVE / n for n in ("spots.toml", "model_spots.toml", "jam_spots.toml")] + [FIXTURE]
    out = subprocess.run(
        [sys.executable, "-c", _LATENCY_SCRIPT, *map(str, paths)],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    ).stdout
    got = json.loads(out)
    times = got["times"]
    p95 = float(np.percentile(times, 95))
    print(f"\n{len(times)} suggestions ({got['new']} new), 95th percentile {p95:.0f} ms")
    assert got["new"] == len(ROWS) >= SPOTS_MIN
    assert p95 <= P95_MS


# --- bars 6 and 7: live solves --------------------------------------------------------


def in_4x_pot(d: hand.Decision) -> bool:
    """A 3-bet-and-call pot whose 3-bet is over 3.5 times the open (DECISIONS 49's rule)."""
    pre = [m for m in d.history if m.street == "preflop"]
    if [m.kind for m in pre] != ["raise", "raise", "call"]:
        return False
    return pre[1].to_bb / pre[0].to_bb > 3.5


@pytest.fixture(scope="module")
def replayed(model):
    """(every solved (hand, decision, spot, suggestion), fallback reasons), Gate V bar 2's way."""
    advisor = Advisor.load(samples=500)
    rng = random.Random(SEED)
    solved, fallbacks = [], Counter()
    for k in range(HANDS):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            replay = hand.replay_history(HandHistory.loads(simulate(rng)), f"sim{k}")
        for d in replay.decisions:
            spot = d.spot()
            s = advisor.suggest(spot)
            if d.street not in ("turn", "river"):
                continue
            if s.source.startswith(solve.SOURCE):
                solved.append((k, d, spot, s))
            else:
                fallbacks[re.sub(r"[\d.]+", "N", s.source.split("no live solve: ")[-1])] += 1
    return solved, fallbacks


def check_legal(k: int, d: hand.Decision, s) -> None:
    """Gate V bar 2's rule: a legal action, its size within pokerkit's limits and the cap."""
    legal, why = d.legal, (k, d.seat, d.street, d.legal, s)
    if s.action in ("fold", "call"):
        assert legal.to_call_bb > 0, why
    elif s.action == "check":
        assert legal.to_call_bb == 0, why
    else:
        assert s.action in RAISES and legal.can_raise, why
        assert legal.raise_min_bb - 1e-9 <= s.size_bb <= legal.raise_max_bb + 1e-9, why
        assert s.size_bb <= legal.cap_bb + 1e-9, why


def test_bar6_every_live_solve_answer_is_legal(replayed) -> None:
    solved, fallbacks = replayed
    counts = Counter()
    for k, d, _, s in solved:
        counts[(d.street, s.action)] += 1
        check_legal(k, d, s)
    fours = sum(in_4x_pot(d) for _, d, _, _ in solved)
    print(f"\n{len(solved)} live-solve answers, {fours} in 4x 3-bet pots (reported)")
    print(f"actions {dict(sorted(counts.items()))}")
    print(f"fallbacks on the turn and river: {dict(fallbacks.most_common())}")
    assert len(solved) >= BAR6_MIN


def simulate_4x(rng: random.Random) -> str:
    """One of bar 6's 4x hands (the amendment): stacks of 25 to 100 bb, open, 3-bet, call."""
    _, stacks, actions = play(rng, FOUR_X_CHIPS, FOUR_X_OPENING)
    return phh_text(stacks, actions)


def test_bar6_every_live_solve_answer_in_the_4x_hands_is_legal(model) -> None:
    advisor = Advisor.load(samples=500)
    rng = random.Random(FOUR_X_SEED)
    solved, counts, fallbacks = 0, Counter(), Counter()
    for k in range(FOUR_X_HANDS):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            replay = hand.replay_history(HandHistory.loads(simulate_4x(rng)), f"4x{k}")
        for d in replay.decisions:
            s = advisor.suggest(d.spot())
            if d.street not in ("turn", "river"):
                continue
            assert in_4x_pot(d), (k, d.history)
            if not s.source.startswith(solve.SOURCE):
                fallbacks[re.sub(r"[\d.]+", "N", s.source.split("no live solve: ")[-1])] += 1
                continue
            check_legal(k, d, s)
            counts[(d.street, s.action)] += 1
            solved += 1
    print(f"\n{solved} live-solve answers in {FOUR_X_HANDS} 4x hands")
    print(f"actions {dict(sorted(counts.items()))}")
    print(f"fallbacks on the turn and river: {dict(fallbacks.most_common())}")
    assert solved >= BAR6_4X_MIN


_LIVE_SCRIPT = r"""
import json, random, sys, warnings
sys.path.insert(0, "tests")
from live_sim import full_history, play
from pokerkit import HandHistory
from showdown.live.advisor import Advisor
from showdown.live.table import frames_from_history
from showdown.live.tracker import Tracker
tracker = Tracker(Advisor.load(), None)
rng, out = random.Random(int(sys.argv[1])), []
for k in range(int(sys.argv[2])):
    state, _, _ = play(rng)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        hh = HandHistory.loads(full_history(state).dumps())
        frames = list(frames_from_history(hh, "sb" if k % 2 == 0 else "bb"))
    for frame in frames:
        for e in tracker.feed(frame):
            if e.kind == "advice" and e.live_solve:
                out.append([e.decision.street, e.since_card_ms, e.suggestion.source])
print(json.dumps(out))
"""


def test_bar7_live_latency_from_the_card(model) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("COV_CORE")}
    out = subprocess.run(
        [sys.executable, "-c", _LIVE_SCRIPT, str(SEED), str(HANDS)],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    ).stdout
    rows = json.loads(out)
    print(f"\n{len(rows)} decisions with a live solve started")
    for street, bar in P95_S.items():
        times = [ms / 1000 for s, ms, _ in rows if s == street]
        assert len(times) >= BAR7_MIN, (street, len(times))
        p95 = float(np.percentile(times, 95))
        print(f"{street}: {len(times)}, median {np.median(times):.2f} s, p95 {p95:.2f} s")
        assert p95 <= bar


# --- reported, not gated ----------------------------------------------------------------


def test_report_frequencies_and_the_saved_hands(model, matrix) -> None:
    """Every node's average frequencies at every depth beside the old model's, and Gate R's
    three saved hands under both models. Prints only."""
    old = pm.PreflopModel.load(pm.v1_model_path())
    pairs = matrix.pair_counts
    for depth in pm.GRID:
        new_s, old_s = model.at(depth), old.at(depth)
        for node in new_s.actions:
            reach = new_s.reach(node, pairs)
            mean = np.mean([new_s.strategy[node][n] for n in CLASS_NAMES], axis=0)
            line = f"{depth:>3g} bb {node!r:>6} reach {reach:7.3%}: " + ", ".join(
                f"{a} {p:.1%}" for a, p in zip(new_s.actions[node], mean, strict=True)
            )
            if node in old_s.actions:
                was = np.mean([old_s.strategy[node][n] for n in CLASS_NAMES], axis=0)
                line += "; old " + ", ".join(
                    f"{a} {p:.1%}" for a, p in zip(old_s.actions[node], was, strict=True)
                )
            print(line)
    for path in sorted((LIVE / "hands").glob("*.phh")):
        replayed = hand.load(path)
        for name, advisor in (
            ("new", Advisor.load(samples=500)),
            ("old", Advisor.load(pm.v1_model_path(), samples=500)),
        ):
            for d in replayed.decisions:
                if d.seat == "sb" and d.hole is not None:
                    s = advisor.suggest(d.spot())
                    print(f"{path.stem} {name} {d.street}: {s.action} {s.size_bb or ''} {s.mix}")
