"""The trainer page (DECISIONS 62), fast checks: the session's families, filters and views,
the server's routes, and the lesson cards. Gate U's bars are in test_gate_u_slow.py."""

import json
import threading
import urllib.error
import urllib.request

import pytest

from showdown import lessons
from showdown import sixmax as S
from showdown.bot.policy import LeducStrategy, PushFoldStrategy
from showdown.bot.server import App, PlayServer
from showdown.bot.sessions import PlayError, SixmaxSession


@pytest.fixture(scope="module")
def strategy() -> PushFoldStrategy:
    return PushFoldStrategy.load()


def _session(strategy, tmp_path, **kw) -> SixmaxSession:
    return SixmaxSession(strategy, samples=1_500, log_dir=tmp_path, **kw)


@pytest.mark.parametrize("family", ["sixmax", "open", "pushfold"])
def test_each_family_deals_grades_and_logs(strategy, tmp_path, family) -> None:
    s = _session(strategy, tmp_path, families=(family,), seed=4)
    for _ in range(2):
        v = s.new_hand()
        assert v["family"] == family and v["your_turn"] and len(v["seats"]) == 6
        assert sum(seat["role"] == "you" for seat in v["seats"]) == 1
        assert all("card" in seat for seat in v["seats"] if seat["role"] not in ("you", "folded"))
        with pytest.raises(PlayError):
            s.new_hand()
        action = v["actions"][-1]["action"]
        r = s.act(action)["result"]
        assert r["label"] in S.LABELS and r["lesson"]["id"] in lessons.IDS
        assert r["why"] and r["standard"].startswith("Against a standard player")
        assert {e["action"] for e in r["ev"]} == {a["action"] for a in v["actions"]}
        with pytest.raises(PlayError):
            s.act(action)
    summary = s.summary()
    assert summary["drills"] == 2 and sum(summary["grades"].values()) == 2
    with open(summary["log"], encoding="utf-8") as f:
        rows = [json.loads(x) for x in f]
    assert len(rows) == 2 and all(r["family"] == family for r in rows)
    if family == "open":
        assert "Gate Z" in v["note"]


def test_filters(strategy, tmp_path) -> None:
    s = _session(strategy, tmp_path, seat="BB", limpers=2, ante=0.5, kind="station", seed=1)
    assert s.families == ("sixmax",)
    v = s.new_hand()
    you = next(x for x in v["seats"] if x["role"] == "you")
    assert you["seat"] == "BB" and "2 limpers" in v["headline"] and "ante 0.5" in v["headline"]
    assert {x.get("type") for x in v["seats"] if x["role"] != "you"} - {None} == {"station"}
    assert _session(strategy, tmp_path, seat="SB", limpers=0).families == FAMILIES_ALL
    for bad in (
        {"seat": "XX"},
        {"limpers": 5},
        {"ante": 1.0},
        {"kind": "fish"},
        {"families": ("poker",)},
        {"seat": "UTG", "limpers": 1},
    ):
        with pytest.raises(PlayError):
            _session(strategy, tmp_path, **bad)
    with pytest.raises(PlayError, match="actions"):
        s.act("shove")


FAMILIES_ALL = ("sixmax", "open", "pushfold")


def test_lesson_choice() -> None:
    assert lessons.lesson_for("pushfold", "SB", 0, "fold", "raise") == "pushfold-vs-types"
    assert lessons.lesson_for("open", "BTN", 0, "call", "raise") == "loose-openers"
    assert lessons.lesson_for("open", "BB", 0, "call", "fold") == "tight-openers"
    assert lessons.lesson_for("sixmax", "BB", 2, "limp", "raise") == "blinds-vs-limpers"
    assert lessons.lesson_for("sixmax", "BTN", 2, "fold", "limp") == "dont-fold-behind-limpers"
    assert lessons.lesson_for("sixmax", "BTN", 1, "limp", "raise") == "isolate-limpers"
    assert lessons.lesson_for("sixmax", "BTN", 0, "fold", "raise") == "steal-tight-blinds"
    assert lessons.lesson_for("sixmax", "HJ", 0, "raise", "fold") == "open-tighter"
    for lesson_id in lessons.IDS:
        c = lessons.card(lesson_id)
        assert c["title"] and c["summary"] and "Ian approves" in c["text"]
    with pytest.raises(ValueError):
        lessons.card("nope")


@pytest.fixture(scope="module")
def server(strategy, tmp_path_factory):
    app = App(strategy, LeducStrategy.load(), log_dir=tmp_path_factory.mktemp("logs"))
    srv = PlayServer(app, 0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _post(srv, path, body):
    request = urllib.request.Request(
        srv.url.rstrip("/") + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Showdown-Token": srv.app.token},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def test_the_routes(server) -> None:
    with urllib.request.urlopen(server.url + "trainer") as response:
        page = response.read().decode()
    assert server.app.token in page and "showdown trainer" in page
    with urllib.request.urlopen(server.url) as response:
        assert "/trainer" in response.read().decode()
    with urllib.request.urlopen(server.url + "api/lesson?id=open-tighter") as response:
        assert json.loads(response.read())["title"].startswith("Open tighter")
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(server.url + "api/lesson?id=nope")
    assert error.value.code == 400
    created = _post(server, "/api/session", {"game": "trainer", "family": "pushfold", "seed": 3})
    v = _post(server, "/api/hand", {"session": created["session"]})
    assert v["family"] == "pushfold"
    r = _post(server, "/api/act", {"session": created["session"], "action": "fold"})
    assert r["result"]["label"] in S.LABELS
    with pytest.raises(urllib.error.HTTPError):
        _post(server, "/api/session", {"game": "trainer", "limpers": "many"})
