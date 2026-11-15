"""Gate E, the fast bullet: a scripted human completes 20 hands of each game through
the play page's HTTP API (SCOPE, DECISIONS 23). The 20,000-hand bullet is in
test_gate_e_slow.py.
"""

import http.client
import json
import random
import re
import threading
import urllib.request
from importlib import resources

import pytest

from showdown.bot.policy import LeducStrategy, PushFoldStrategy
from showdown.bot.server import App, PlayServer


@pytest.fixture(scope="module")
def server():
    app = App(PushFoldStrategy.load(), LeducStrategy.load())
    srv = PlayServer(app, 0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def post(srv, path, body, token=None):
    request = urllib.request.Request(
        srv.url.rstrip("/") + path,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Showdown-Token": token if token is not None else srv.app.token,
        },
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def get(srv, path):
    with urllib.request.urlopen(srv.url.rstrip("/") + path) as response:
        return response.status, response.read()


def raw(srv, method, path, headers, body=b""):
    conn = http.client.HTTPConnection("127.0.0.1", srv.port)
    conn.request(method, path, body=body, headers=headers)
    response = conn.getresponse()
    data = response.read()
    conn.close()
    return response.status, data


def _check_pushfold_result(view):
    """The realised result must be one the push/fold model allows (DECISIONS 22)."""
    net, depth, seat = view["result"]["net_bb"], view["depth"], view["seat"]
    sb_folded = any(e["seat"] == "sb" and e["action"] == "fold" for e in view["events"])
    bb_folded = any(e["seat"] == "bb" and e["action"] == "fold" for e in view["events"])
    sign = 1 if seat == "sb" else -1
    if sb_folded:
        assert net == sign * -0.5
    elif bb_folded:
        assert net == sign * 1.0
    else:
        assert net in (depth, -depth, 0.0)
        assert len(view["result"]["board"]) == 5


def test_bound_to_localhost_only(server) -> None:
    assert server.server_address[0] == "127.0.0.1"


def test_twenty_pushfold_hands_through_the_api(server) -> None:
    rng = random.Random(20261114)
    plans = [
        {"seat": "alternate", "depth_mode": "fixed", "depth": 10, "hands": 8},
        {"seat": "bb", "depth_mode": "random", "depth": 10, "hands": 6},
        {"seat": "sb", "depth_mode": "fixed", "depth": 1, "hands": 3},
        {"seat": "bb", "depth_mode": "fixed", "depth": 2, "hands": 3},
    ]
    finished = 0
    for n, plan in enumerate(plans):
        hands = plan.pop("hands")
        session = post(server, "/api/session", {"game": "pushfold", "seed": n, **plan})["session"]
        losses, decisions, net = [], 0, 0.0
        for _ in range(hands):
            view = post(server, "/api/hand", {"session": session})
            before = []
            while view["your_turn"]:
                assert "result" not in view
                before.append(json.dumps(view))
                view = post(
                    server,
                    "/api/act",
                    {"session": session, "action": rng.choice(["fold", "all-in"])},
                )
            for text in before:  # the bot's cards never leak before the hand ends
                for c in view["result"]["bot_cards"]:
                    assert f'"{c}"' not in text
            _check_pushfold_result(view)
            losses += [g["loss"] for g in view["grades"]]
            decisions += len(view["grades"])
            net += view["result"]["net_bb"]
            finished += 1
        summary = json.loads(get(server, f"/api/summary?session={session}")[1])
        assert summary["decisions"] == decisions
        assert summary["bb_lost"] == pytest.approx(sum(losses), abs=1e-12)
        assert summary["net_bb"] == pytest.approx(net, abs=1e-12)
        assert summary["hands"] == hands
    assert finished == 20


def test_twenty_leduc_hands_through_the_api(server) -> None:
    rng = random.Random(7)
    finished, total = 0, 0.0
    for seat, hands in (("alternate", 12), ("second", 8)):
        session = post(server, "/api/session", {"game": "leduc", "seat": seat, "seed": hands})
        session_id = session["session"]
        net = 0.0
        for _ in range(hands):
            view = post(server, "/api/hand", {"session": session_id})
            while view["your_turn"]:
                assert "result" not in view
                action = rng.choice(view["actions"])["action"]
                view = post(server, "/api/act", {"session": session_id, "action": action})
            assert abs(view["result"]["net_chips"]) <= 13
            net += view["result"]["net_chips"]
            finished += 1
        status, body = get(server, f"/api/summary?session={session_id}")
        summary = json.loads(body)
        assert status == 200
        assert summary["hands"] == hands
        assert summary["net_chips"] == pytest.approx(net)
        total += net
    assert finished == 20


def test_page_and_routes(server) -> None:
    status, body = get(server, "/")
    page = body.decode()
    assert status == 200
    assert server.app.token in page
    assert "{{TOKEN}}" not in page
    html = resources.files("showdown.bot").joinpath("static/index.html").read_text("utf-8")
    called = set(re.findall(r'api\("(/api/[a-z]+)', html))
    assert called == {"/api/session", "/api/hand", "/api/act"}
    assert not re.search(r"https?://", html)  # nothing loads from the network


def test_requests_are_checked(server) -> None:
    good = {"Host": f"127.0.0.1:{server.port}", "Content-Type": "application/json"}
    token = {**good, "X-Showdown-Token": server.app.token}
    assert raw(server, "GET", "/", {"Host": "evil.example:80"})[0] == 403
    assert raw(server, "POST", "/api/session", good, b'{"game": "leduc"}')[0] == 403
    assert raw(server, "POST", "/api/session", {**token, "Host": "x:1"}, b"{}")[0] == 403
    assert raw(server, "POST", "/api/nowhere", token, b"{}")[0] == 404
    assert raw(server, "GET", "/nowhere", good)[0] == 404
    assert raw(server, "POST", "/api/session", token, b"not json")[0] == 400
    assert raw(server, "POST", "/api/session", token, b"[1]")[0] == 400
    assert raw(server, "POST", "/api/session", token, b'{"game": "chess"}')[0] == 400
    assert raw(server, "POST", "/api/hand", token, b'{"session": "nope"}')[0] == 400
    big = {**token, "Content-Length": "999999"}
    assert raw(server, "POST", "/api/session", big, b"{}")[0] == 413
    depth = b'{"game": "pushfold", "depth": "deep"}'
    assert raw(server, "POST", "/api/session", token, depth)[0] == 400
    localhost = {**good, "Host": f"localhost:{server.port}"}
    assert raw(server, "GET", "/", localhost)[0] == 200
