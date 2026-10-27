"""A real Tiroir server per test, on a free port, with its own data folder."""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from tiroir.auth import Password
from tiroir.config import Config
from tiroir.server import make_server

PASSWORD = "correct horse battery staple"
SAME = {"Sec-Fetch-Site": "same-origin", "X-Tiroir": "1", "Content-Type": "application/json"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # see 303 / Set-Cookie as they are
        return None


OPENER = urllib.request.build_opener(_NoRedirect)


@dataclass
class Reply:
    code: int
    json: dict
    cookie: str
    headers: dict = field(default_factory=dict)
    text: str = ""


@dataclass
class Server:
    base: str
    data: Path
    app: object

    def call(self, method: str, path: str, cookie: str = "", body=None, form: dict | None = None,
             headers: dict | None = None) -> Reply:
        h = {**SAME, **(headers or {})}
        data = None
        if form is not None:
            h["Content-Type"] = "application/x-www-form-urlencoded"
            data = urllib.parse.urlencode(form).encode()
        elif body is not None:
            data = json.dumps(body).encode()
        if cookie:
            h["Cookie"] = "tiroir=" + cookie
        req = urllib.request.Request(self.base + path, data=data, method=method, headers={k: v for k, v in h.items() if v is not None})
        try:
            r = OPENER.open(req, timeout=10)
            code, raw, hdrs = r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            code, raw, hdrs = e.code, e.read(), e.headers
        set_cookie = hdrs.get("Set-Cookie") or ""
        tok = set_cookie.split("tiroir=", 1)[1].split(";", 1)[0] if "tiroir=" in set_cookie else ""
        try:
            js = json.loads(raw or b"{}")
        except ValueError:
            js = {}
        return Reply(code, js if isinstance(js, dict) else {}, tok, dict(hdrs), raw.decode("utf-8", "replace"))

    def login(self, password: str = PASSWORD) -> str:
        r = self.call("POST", "/login", form={"password": password})
        assert r.code == 303 and r.cookie, f"login failed ({r.code})"
        return r.cookie

    def board(self, cookie: str) -> tuple[dict, dict, dict]:
        js = self.call("GET", "/api/notes", cookie).json
        return ({p["id"]: p for p in js.get("projects", [])}, {f["id"]: f for f in js.get("folders", [])},
                {n["id"]: n for n in js.get("notes", [])})


def start(tmp_path: Path, notes: dict | None = None, **cfg) -> tuple[Server, object]:
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    if notes is not None:
        (data / "notes.json").write_text(json.dumps(notes), encoding="utf-8")
    Password(data).set(PASSWORD)
    settings = dict(data_dir=data, host="127.0.0.1", port=0, agents_dir=None, trust_proxy=(), cookie_secure="auto", lang="en")
    srv = make_server(Config(**{**settings, **cfg}))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return Server(f"http://127.0.0.1:{srv.server_address[1]}", data, srv.app), srv


@pytest.fixture
def server(tmp_path):
    s, srv = start(tmp_path)
    yield s
    srv.shutdown()


@pytest.fixture
def make(tmp_path):
    """Start a server with custom data or settings: make(notes={...}, agents_dir=..., trust_proxy=True)."""
    running = []

    def _make(**kw):
        s, srv = start(tmp_path, **kw)
        running.append(srv)
        return s

    yield _make
    for srv in running:
        srv.shutdown()
