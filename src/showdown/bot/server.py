"""The local play server: stdlib HTTP on 127.0.0.1 only, JSON API, one page (DECISIONS 12, 23)."""

from __future__ import annotations

import json
import random
import secrets
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from showdown import lessons
from showdown.bot.policy import LeducStrategy, PushFoldStrategy
from showdown.bot.sessions import LeducSession, PlayError, PushFoldSession, SixmaxSession
from showdown.sixmax_drill import LOG_DIR

HOST = "127.0.0.1"
MAX_BODY = 10_000


def _any(value: object, cast=str):
    """A filter value, or None for "any" or missing."""
    if value in (None, "", "any"):
        return None
    try:
        return cast(value)
    except (TypeError, ValueError):
        raise PlayError(f"bad filter value {value!r}") from None


@dataclass
class App:
    """Everything the handlers share: strategies, sessions and the launch token."""

    pushfold: PushFoldStrategy
    leduc: LeducStrategy
    log_dir: Path = LOG_DIR
    """Where the trainer's drill logs go (DECISIONS 62)."""
    token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    sessions: dict[str, object] = field(default_factory=dict)
    locks: dict[str, threading.Lock] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def create(self, body: dict) -> dict:
        seed = body.get("seed")
        rng = random.Random(seed if isinstance(seed, int) else secrets.randbits(64))
        game = body.get("game")
        if game == "pushfold":
            session: object = PushFoldSession(
                self.pushfold,
                seat=str(body.get("seat", "alternate")),
                depth_mode=str(body.get("depth_mode", "fixed")),
                depth=_int(body.get("depth", 10)),
                rng=rng,
            )
        elif game == "leduc":
            session = LeducSession(self.leduc, seat=str(body.get("seat", "alternate")), rng=rng)
        elif game == "trainer":
            family = _any(body.get("family"))
            session = SixmaxSession(
                self.pushfold,
                families=(family,) if family else ("sixmax", "open", "pushfold"),
                seat=_any(body.get("seat")),
                limpers=_any(body.get("limpers"), int),
                ante=_any(body.get("ante"), float),
                kind=_any(body.get("type")),
                seed=seed if isinstance(seed, int) else secrets.randbits(32),
                log_dir=self.log_dir,
            )
        else:
            raise PlayError("game must be pushfold, leduc or trainer")
        sid = secrets.token_urlsafe(12)
        with self._lock:
            self.sessions[sid] = session
            self.locks[sid] = threading.Lock()
        return {"session": sid, **session.view()}  # type: ignore[attr-defined]

    def _get(self, sid: object) -> tuple[object, threading.Lock]:
        with self._lock:
            if not isinstance(sid, str) or sid not in self.sessions:
                raise PlayError("unknown session")
            return self.sessions[sid], self.locks[sid]

    def hand(self, body: dict) -> dict:
        session, lock = self._get(body.get("session"))
        with lock:
            return session.new_hand()  # type: ignore[attr-defined]

    def act(self, body: dict) -> dict:
        session, lock = self._get(body.get("session"))
        with lock:
            return session.act(str(body.get("action")))  # type: ignore[attr-defined]

    def summary(self, sid: str | None) -> dict:
        session, lock = self._get(sid)
        with lock:
            return session.summary()  # type: ignore[attr-defined]


def _int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise PlayError("depth must be an integer") from None


def page(token: str, name: str = "index.html") -> bytes:
    html = resources.files("showdown.bot").joinpath(f"static/{name}").read_text("utf-8")
    return html.replace("{{TOKEN}}", token).encode("utf-8")


def lesson(lesson_id: str | None) -> dict:
    try:
        return lessons.card(str(lesson_id))
    except ValueError as error:
        raise PlayError(str(error)) from None


class PlayServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, app: App, port: int = 0) -> None:
        self.app = app
        super().__init__((HOST, port), Handler)

    @property
    def port(self) -> int:
        return self.server_address[1]

    @property
    def url(self) -> str:
        return f"http://{HOST}:{self.port}/"


class Handler(BaseHTTPRequestHandler):
    server: PlayServer
    server_version = "showdown"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # quiet; the CLI prints the URL and errors go back as JSON

    def _host_ok(self) -> bool:
        port = self.server.port
        return self.headers.get("Host", "") in (f"{HOST}:{port}", f"localhost:{port}")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

    def do_GET(self) -> None:  # noqa: N802
        if not self._host_ok():
            self._json(403, {"error": "forbidden host"})
            return
        url = urlparse(self.path)
        app = self.server.app
        if url.path == "/":
            self._send(200, page(app.token), "text/html; charset=utf-8")
        elif url.path == "/trainer":
            self._send(200, page(app.token, "trainer.html"), "text/html; charset=utf-8")
        elif url.path == "/api/summary":
            sid = parse_qs(url.query).get("session", [None])[0]
            self._dispatch(lambda: app.summary(sid))
        elif url.path == "/api/lesson":
            lesson_id = parse_qs(url.query).get("id", [None])[0]
            self._dispatch(lambda: lesson(lesson_id))
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        app = self.server.app
        if not self._host_ok() or self.headers.get("X-Showdown-Token") != app.token:
            self._json(403, {"error": "forbidden"})
            return
        routes = {"/api/session": app.create, "/api/hand": app.hand, "/api/act": app.act}
        route = routes.get(urlparse(self.path).path)
        if route is None:
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._json(413, {"error": "request too large"})
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "body must be JSON"})
            return
        if not isinstance(body, dict):
            self._json(400, {"error": "body must be a JSON object"})
            return
        self._dispatch(lambda: route(body))

    def _dispatch(self, call) -> None:
        try:
            self._json(200, call())
        except PlayError as error:
            self._json(400, {"error": str(error)})
