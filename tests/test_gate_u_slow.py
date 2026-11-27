"""Gate U, bars 1 to 3 (DECISIONS 62): a scripted 300-drill trainer session over HTTP. Every
grade is checked against one worked out here, by DECISIONS 60's rule, from a fresh
`sixmax.answer` or `exploit.typed_spot`. Run with -s to see the report.
"""

import json
import os
import random
import threading
import time
import urllib.request
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pytest

from showdown import sixmax as S
from showdown.bot.policy import LeducStrategy, PushFoldStrategy
from showdown.bot.server import App, PlayServer
from showdown.equity.cards import class_index
from showdown.exploit import typed_spot

pytestmark = pytest.mark.slow

SEED, DRILLS, CHOICE_SEED = 20261128, 300, 7
MIN_FAMILY = 50
CUTS = ((3.0, "Correct"), (10.0, "Inaccuracy"), (25.0, "Wrong"))


def _post(srv, path: str, body: dict) -> dict:
    request = urllib.request.Request(
        srv.url.rstrip("/") + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Showdown-Token": srv.app.token},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


@pytest.fixture(scope="module")
def run(tmp_path_factory) -> dict:
    strategy = PushFoldStrategy.load()
    app = App(strategy, LeducStrategy.load(), log_dir=tmp_path_factory.mktemp("logs"))
    srv = PlayServer(app, 0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        sid = _post(srv, "/api/session", {"game": "trainer", "seed": SEED})["session"]
        pick = random.Random(CHOICE_SEED)
        seconds, answered = [], []
        for _ in range(DRILLS):
            start = time.perf_counter()
            v = _post(srv, "/api/hand", {"session": sid})
            seconds.append(time.perf_counter() - start)
            action = pick.choice([a["action"] for a in v["actions"]])
            answered.append(_post(srv, "/api/act", {"session": sid, "action": action})["result"])
        with urllib.request.urlopen(f"{srv.url}api/summary?session={sid}") as response:
            summary = json.loads(response.read())
    finally:
        srv.shutdown()
        srv.server_close()
    with open(summary["log"], encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    with ProcessPoolExecutor(max_workers=min(12, os.cpu_count() or 1)) as pool:
        expected = list(pool.map(_expected, rows))
    return {
        "rows": rows,
        "answered": answered,
        "seconds": seconds,
        "summary": summary,
        "expected": expected,
    }


def _expected(row: dict) -> tuple[str, float, float]:
    """DECISIONS 60's rule from a fresh answer: (label, bb lost, % lost)."""
    cls = class_index(row["class"])
    if row["family"] == "pushfold":
        strategy = PushFoldStrategy.load()
        kind = S.load_types()[row["villain_type"]]
        t = typed_spot(
            strategy.solution, strategy.matrix, row["depth"], row["seat"].lower(), kind, cls
        )
        ev, best, winners, size_only, pot = t.ev, t.best, set(t.band_winners), False, t.pot
    else:
        if row["family"] == "open":
            op = S.opener(row["opener"], row["opener_type"])
            spot = S.OpenSpot(row["seat"], op, row["open"], row["ante"])
            profile = S.compose("standard", row["table_type"])
        else:
            spot = S.Spot(row["seat"], row["limpers"], row["ante"])
            profile = S.compose(row["limpers_type"], row["table_type"])
        a = S.answer(spot, profile, cls)
        ev = dict(zip(a.actions, (float(e) for e in a.ev), strict=True))
        best, winners, pot = a.best, {w for _, _, w in a.flips}, spot.pot
        size_only = bool(winners) and all(S.kind(w) == S.kind(best) for w in winners)
    act = row["action"]
    lost = ev[best] - ev[act]
    pct = 100.0 * lost / pot
    if lost <= 1e-9 or (size_only and S.kind(act) == S.kind(best)):
        label = "Best"
    elif act in winners:
        label = "Correct"
    else:
        label = next((name for cut, name in CUTS if pct <= cut), "Blunder")
    return label, lost, pct


def test_bar1_grades_through_the_api(run) -> None:
    rows, answered, expected = run["rows"], run["answered"], run["expected"]
    assert len(answered) == DRILLS
    wrong = [
        (r["family"], r["seat"], r["class"], r["action"], r["grade"], e[0])
        for r, e in zip(rows, expected, strict=True)
        if r["grade"] != e[0]
    ]
    api_vs_log = [
        i
        for i, (a, r) in enumerate(zip(answered, rows, strict=True))
        if a["label"] != r["grade"] or a["lost"] != r["bb_lost"]
    ]
    off = max(abs(r["bb_lost"] - e[1]) for r, e in zip(rows, expected, strict=True))
    off_pct = max(abs(r["pct_lost"] - e[2]) for r, e in zip(rows, expected, strict=True))
    families = Counter(r["family"] for r in rows)
    by_family = {f: dict(Counter(r["grade"] for r in rows if r["family"] == f)) for f in families}
    print(
        f"\nbar 1: families {dict(families)}; mismatches {wrong}; API vs log {api_vs_log}; "
        f"worst bb gap {off:.2e}, % {off_pct:.2e}"
    )
    print(f"  (reported) labels by family: {by_family}")
    assert not wrong and not api_vs_log
    assert off < 1e-9 and off_pct < 1e-7
    assert all(families[f] >= MIN_FAMILY for f in ("sixmax", "open", "pushfold"))


def test_bar2_latency(run) -> None:
    seconds = np.array(run["seconds"])
    median, p95 = float(np.median(seconds)), float(np.percentile(seconds, 95))
    print(f"\nbar 2: median {median:.2f} s, 95th percentile {p95:.2f} s, max {seconds.max():.2f} s")
    assert median <= 2.0 and p95 <= 5.0


def test_bar3_the_log(run) -> None:
    rows, summary = run["rows"], run["summary"]
    assert len(rows) == summary["drills"] == DRILLS
    for label in S.LABELS:
        assert summary["grades"][label] == sum(r["grade"] == label for r in rows)
    assert abs(summary["bb_lost"] - sum(r["bb_lost"] for r in rows)) < 1e-9
    print(
        f"\nbar 3: {len(rows)} lines; {summary['grades']}; bb lost {summary['bb_lost']:.3f}; "
        f"accuracy {summary['accuracy']:.1%}"
    )
