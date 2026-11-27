"""Gate W2, bar 1 (DECISIONS 63): the leak finder classifies the generated fixture and types
its players exactly as labelled. The fixture and its labels were committed before any of the
review code. Also here: the stats' and typing's pieces, the CLI and the Review route."""

import json
import threading
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from showdown import sixmax as S
from showdown import sixmax_review as V
from showdown.bot.policy import LeducStrategy, PushFoldStrategy
from showdown.bot.server import App, PlayServer
from showdown.cli import main
from showdown.hh.parse import load, parse_pokerstars

FIXTURE = Path(__file__).parent / "fixtures" / "sixmax_review_w2"
LABELS = tomllib.loads((FIXTURE / "labels.toml").read_text(encoding="utf-8"))


def key(source: str) -> str:
    path, _, hand = source.partition("#")
    return Path(path).stem + (f"#{hand}" if hand else "")


@pytest.fixture(scope="module")
def parsed():
    return load([FIXTURE])


def test_bar1_every_hand_matches_its_label(parsed) -> None:
    assert parsed.found == parsed.parsed == 48 and not parsed.failures
    families, causes = set(), set()
    for record in parsed.records:
        label = LABELS[key(record.source)]
        d = V.classify(record, "Hero", opens=True)
        if "cause" in label:
            assert d.cause == label["cause"], key(record.source)
            causes.add(d.cause)
            continue
        got = {
            "seat": d.seat,
            "ante": d.ante,
            "family": d.family,
            "hand": d.hand,
            "action": d.action,
        }
        got |= (
            {"opener": d.opener, "open": d.open} if d.family == "open" else {"limpers": d.limpers}
        )
        assert d.cause is None and got == label, key(record.source)
        families.add(d.family)
    assert families == {"sixmax", "open"}
    assert causes == {"raised before you", "open called before you", "open size"}
    assert sum(v.get("family") == "open" for v in LABELS.values()) >= 15


def test_bar1_every_player_is_typed_as_labelled(parsed) -> None:
    stats = V.player_stats(parsed.records)
    types = S.load_types()
    players = {k.removeprefix("player."): v for k, v in LABELS.items() if k.startswith("player.")}
    assert set(stats) == set(players)
    for name, label in players.items():
        r = V.rates(stats[name])
        assert stats[name]["hands"] == label["hands"]
        assert set(r) == set(label) - {"hands", "type"}
        for k, v in r.items():
            assert v == pytest.approx(label[k], abs=1e-12), (name, k)
        assert V.type_of(stats[name], types) == label["type"], name
    thin = [n for n, p in players.items() if p["hands"] < 30 and n != "Hero"]
    full = [n for n, p in players.items() if p["hands"] >= 30 and n != "Hero"]
    assert len(thin) == 2 and len(full) >= 4


def test_pieces() -> None:
    assert V._majority([], {}) == "standard"
    assert V._majority(["a", "b", "c"], {"a": "nit", "b": "lag", "c": "lag"}) == "lag"
    assert V._majority(["a", "b"], {"a": "nit", "b": "lag"}) == "nit"
    d = V.Decision("x", seat="BTN", family="open", opener="CO", open=2.5, open_size=2.5)
    d.kind, d.size = "raise", 7.5
    assert V._open_action(d, False) == "3-bet to 7.5"
    d.size = 9.0
    assert V._open_action(d, False) == "3-bet to 10"
    assert V._open_action(d, True) == "jam"
    d.size = 40.0
    assert V._open_action(d, False) == "jam"
    s = V.Decision("x", seat="BTN", limpers=1, kind="raise", size=4.5)
    assert V._sixmax_action(s) == "iso to 4"
    s.kind = "limp"
    assert V._sixmax_action(s) == "overlimp"


def test_the_command(capsys) -> None:
    argv = [
        "sixmax",
        "review",
        str(FIXTURE / "session.txt"),
        "--player",
        "Hero",
        "--samples",
        "1500",
    ]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "Leak finder for Hero" in out and "3 hands, 3 parsed, 0 failed" in out
    assert "Grades: Best" in out and "Opponents: 5 typed" in out and "Graded: 3 (" in out


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    app = App(PushFoldStrategy.load(), LeducStrategy.load(), log_dir=tmp_path_factory.mktemp("l"))
    srv = PlayServer(app, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _post(srv, body):
    request = urllib.request.Request(
        srv.url + "api/review",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Showdown-Token": srv.app.token},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def test_the_review_route(server) -> None:
    text = (FIXTURE / "session.txt").read_text(encoding="utf-8")
    assert parse_pokerstars(text, "x.txt").parsed == 3
    r = _post(server, {"text": text, "name": "session.txt"})
    assert r["player"] == "Hero" and r["report"][0].startswith("Leak finder for Hero")
    assert r["summary"]["graded"] == 3
    with pytest.raises(urllib.error.HTTPError) as error:
        _post(server, {"text": "", "name": "x.txt"})
    assert error.value.code == 400
