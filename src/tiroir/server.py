"""HTTP server of Tiroir (standard library only).

Listens on TIROIR_HOST:TIROIR_PORT (127.0.0.1 by default): put it behind a reverse proxy or a tunnel to reach it from outside.
Session cookie HttpOnly + SameSite=Strict (+ Secure when served over https), CSRF guard (Sec-Fetch-Site + X-Tiroir header),
login attempts booked before the scrypt check, strict Content-Security-Policy, no logging of URLs or addresses.
"""
from __future__ import annotations

import ipaddress
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import access, agents, model
from .auth import Attempts, Password, ip_key
from .config import Config
from .store import NotesStore, StoreError

STATIC = Path(__file__).resolve().parent / "static"
COOKIE = "tiroir"
MAX_BODY = 20_000
IMPORT_EVERY = 10
FONTS = {f"inter-{v}{w}.woff2" for v in ("", "ext-") for w in (400, 500, 600)}
PUBLIC_STATIC = {"app.css", "home.css", "cabinet.css", "login.css", "theme.js", "i18n.js"} | FONTS
AUTH_STATIC = {"app.js", "home.js", "cabinet.js", "meubles.js", "partage.js"}
KINDS = ("notes", "folders", "projects", "cabinets", "invites")
HEADERS = {
    "Content-Security-Policy": ("default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                                "font-src 'self'; connect-src 'self'; img-src 'self' data:; "
                                "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
}
MESSAGES = {
    "en": {"wrong": "Wrong password.", "busy": "Server busy, try again in a moment.",
           "slow": "Too many attempts. Try again in a few minutes.",
           "bad_invite": "Invalid or revoked invitation link.", "no_password": "No password yet: run « tiroir set-password ».",
           "placeholder": "password", "enter": "Enter", "opening": "Opening Tiroir..."},
    "fr": {"wrong": "Mot de passe incorrect.", "busy": "Serveur occupé, réessaie dans un instant.",
           "slow": "Trop d'essais. Réessaie dans quelques minutes.", "bad_invite": "Lien d'invitation invalide ou révoqué.",
           "no_password": "Aucun mot de passe : lance « tiroir set-password ».",
           "placeholder": "mot de passe", "enter": "Entrer", "opening": "Ouverture du Tiroir..."},
}


class App:
    """Everything a request needs; one per server (tests run several side by side)."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.names = model.NAMES[cfg.lang]
        self.store = NotesStore(cfg.data_dir)
        self.password = Password(cfg.data_dir)
        self.access = access.Store(cfg.data_dir)
        self.attempts = Attempts()
        self.import_lock = threading.Lock()
        self.last_import = 0.0

    def migrate(self) -> None:
        """One-time upgrades of older files, then tabs without a drawer go to the misc drawer."""
        with self.store.lock:
            raw = self.store.raw()
            if raw is None:
                return
            d = self.store.read()
            changed = False
            if "folders" not in raw:
                model.migrate_folders(d, self.names)
                changed = True
            if "projects" not in raw:
                model.migrate_projects(d, self.names)
                changed = True
            orphans = model.adopt_orphans(d, self.names)
            if model.adopt_drawers(d, self.names) or orphans or changed:
                self.store.write(d)

    def maybe_import(self) -> None:
        """Import agent notes outside the main lock, at most once every IMPORT_EVERY seconds."""
        if self.cfg.agents_dir is None or time.time() - self.last_import <= IMPORT_EVERY:
            return
        if not self.import_lock.acquire(blocking=False):
            return
        try:
            self.last_import = time.time()
            with self.store.lock:
                snapshot = json.loads(json.dumps(self.store.read()))
            if not agents.import_agent_notes(snapshot, self.cfg.agents_dir, self.names):
                return
            with self.store.lock:
                cur = self.store.read()
                for kind in ("projects", "folders"):
                    for k, v in snapshot[kind].items():
                        if k not in cur[kind] and (kind != "folders" or len(cur["folders"]) < model.MAX_FOLDERS):
                            cur[kind][k] = v
                for k, v in snapshot["notes"].items():
                    src = v.get("src")
                    if src and k not in cur["notes"] and snapshot["imported"].get(src) == k and src not in cur["imported"]:
                        cur["notes"][k] = v
                        cur["imported"][src] = k
                self.store.write(cur)
        finally:
            self.import_lock.release()


class Handler(BaseHTTPRequestHandler):
    server_version = "tiroir"
    sys_version = ""
    timeout = 10  # a slow client never holds a thread forever

    def log_message(self, fmt, *args):  # no log of URLs or addresses
        pass

    @property
    def app(self) -> App:
        return self.server.app  # type: ignore[attr-defined]

    # ---------- request helpers ----------
    def proxied(self) -> bool:
        """Proxy headers are believed only when the request comes from a trusted proxy (TIROIR_TRUST_PROXY)."""
        try:
            peer = ipaddress.ip_address(self.client_address[0])
        except ValueError:
            return False
        return any(peer in net for net in self.app.cfg.trust_proxy if net.version == peer.version)

    def ip(self) -> str:
        if self.proxied():
            fwd = self.headers.get("CF-Connecting-IP") or (self.headers.get("X-Forwarded-For") or "").split(",")[0]
            if fwd.strip():
                return ip_key(fwd)
        return ip_key(self.client_address[0])

    def https(self) -> bool:
        return self.proxied() and (self.headers.get("X-Forwarded-Proto") or "").lower() == "https"

    def secure_cookie(self) -> bool:
        mode = self.app.cfg.cookie_secure
        if mode != "auto":
            return mode == "always"
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return self.https() or host in ("localhost", "127.0.0.1", "::1")  # plain http on a LAN: no Secure flag

    def lang(self) -> dict:
        return MESSAGES["fr" if (self.headers.get("Accept-Language") or "").lower().startswith("fr") else "en"]

    def cookie(self) -> str | None:
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == COOKIE:
                return v
        return None

    def ctx(self) -> dict | None:
        return self.app.access.context(self.cookie(), self.app.password.version())

    def session_cookie(self, tok: str, max_age: int = access.SESSION_DAYS * 86400) -> str:
        return f"{COOKIE}={tok}; HttpOnly;{' Secure;' if self.secure_cookie() else ''} SameSite=Strict; Path=/; Max-Age={max_age}"

    def send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        hsts = {"Strict-Transport-Security": "max-age=31536000"} if self.https() else {}
        for k, v in {**HEADERS, **hsts, **(extra or {})}.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def json(self, code: int, obj) -> None:
        self.send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def same_origin(self) -> bool:
        """Request made by our own page. Sec-Fetch-Site (cannot be forged by a web page) wins; else compare Origin and Host."""
        fetch_site = self.headers.get("Sec-Fetch-Site")
        if fetch_site:
            return fetch_site in ("same-origin", "none")
        origin = self.headers.get("Origin")
        return not origin or origin.split("://", 1)[-1] == self.headers.get("Host", "")

    def body(self) -> bytes | None:
        try:
            n = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            return None
        return None if n < 0 or n > MAX_BODY else self.rfile.read(n)

    def login_page(self, msg: str = "", code: int = 200) -> None:
        t = self.lang()
        html = (STATIC / "login.html").read_text(encoding="utf-8")
        for key, val in (("MSG", msg), ("PLACEHOLDER", t["placeholder"]), ("ENTER", t["enter"]),
                         ("LANG", "fr" if t is MESSAGES["fr"] else "en")):
            html = html.replace("{{" + key + "}}", val)
        self.send(code, html.encode(), "text/html; charset=utf-8")

    def redirect_https(self) -> bool:
        """Behind a trusted proxy, plain http is sent to https (a Secure cookie would be refused otherwise)."""
        if self.proxied() and (self.headers.get("X-Forwarded-Proto") or "").lower() == "http":
            host = (self.headers.get("Host") or "").split("/")[0]
            if host.replace(".", "").replace("-", "").replace(":", "").isalnum() and len(host) <= 100:
                self.send(308, b"", "text/plain", {"Location": f"https://{host}{urlsplit(self.path).path or '/'}"})
                return True
        return False

    def guarded(self, action) -> None:
        """Run an action on the board; if notes.json cannot be recovered, answer 503 without writing anything."""
        try:
            action()
        except StoreError:
            self.json(503, {"error": "storage unreadable: no write until notes.json is repaired"})

    # ---------- GET ----------
    def do_GET(self) -> None:
        if self.redirect_https():
            return
        path = urlsplit(self.path).path
        if path == "/":
            if self.ctx():
                self.send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            else:
                self.login_page("" if self.app.password.is_set() else self.lang()["no_password"])
        elif path.startswith("/static/"):
            self.static(path[len("/static/"):])
        elif path.startswith("/i/"):
            self.accept_invite(path[len("/i/"):])
        elif path.startswith("/api/"):
            self.guarded(lambda: self.api_get(path))
        else:
            self.send(404, b"", "text/plain")

    def static(self, name: str) -> None:
        if name in FONTS:
            self.send(200, (STATIC / name).read_bytes(), "font/woff2", {"Cache-Control": "public, max-age=31536000, immutable"})
        elif name in PUBLIC_STATIC or (name in AUTH_STATIC and self.ctx()):
            ctype = "text/css; charset=utf-8" if name.endswith(".css") else "application/javascript; charset=utf-8"
            self.send(200, (STATIC / name).read_bytes(), ctype)
        else:
            self.send(404, b"", "text/plain")

    def api_get(self, path: str) -> None:
        ctx = self.ctx()
        if not ctx:
            self.json(401, {"error": "auth"})
        elif path == "/api/me":
            self.json(200, {"role": ctx["role"], "folders": ctx["folders"], "label": ctx["label"]})
        elif path == "/api/invites":
            if ctx["role"] != "admin":
                self.json(403, {"error": "admin only"})
            else:
                self.json(200, {"invites": self.app.access.list_invites()})
        elif path == "/api/notes":
            self.json(200, self.board(ctx))
        else:
            self.json(404, {"error": "unknown"})

    def board(self, ctx: dict) -> dict:
        """What this session may see: notes, tabs and drawers (a guest only sees drawers holding one of its tabs)."""
        self.app.maybe_import()
        with self.app.store.lock:
            d = self.app.store.read()
        existing = set(d["folders"])
        admin = ctx["role"] == "admin"
        notes = [{"id": k, **v} for k, v in d["notes"].items() if access.can_see(ctx, v, existing)]
        folders = [{"id": k, **v} for k, v in d["folders"].items()
                   if access.in_scope(ctx, k, existing) and (admin or not v.get("deletedAt"))]
        shown = {f.get("project", "") for f in folders}
        projects = [{"id": k, **v} for k, v in d["projects"].items() if admin or k in shown]
        held = {p.get("cabinet", "") for p in projects}
        cabinets = [{"id": k, **v} for k, v in d["cabinets"].items() if admin or k in held]
        return {"notes": notes, "folders": folders, "projects": projects, "cabinets": cabinets}

    def accept_invite(self, token: str) -> None:
        """Invitation link: opens a guest session then reloads « / » with a page (a direct redirect coming from
        another site, e.g. a chat app, would not send back the SameSite=Strict cookie)."""
        key = self.ip()
        if not self.app.attempts.reserve(key):
            self.login_page(self.lang()["slow"], 429)
            return
        iid = self.app.access.find_invite(token)
        if not iid:
            time.sleep(0.5)
            self.login_page(self.lang()["bad_invite"], 404)
            return
        self.app.attempts.release(key)
        tok = self.app.access.new_session("guest", iid)
        page = ('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=/">'
                f'<title>Tiroir</title><p style="font-family:sans-serif">{self.lang()["opening"]}</p>').encode()
        self.send(200, page, "text/html; charset=utf-8", {"Set-Cookie": self.session_cookie(tok), "Referrer-Policy": "no-referrer"})

    # ---------- POST /login /logout ----------
    def do_POST(self) -> None:
        if self.redirect_https():
            return
        path = urlsplit(self.path).path
        if path == "/login":
            self.login()
        elif path == "/logout":
            if self.headers.get("X-Tiroir") != "1" or not self.same_origin():
                self.send(403, b"", "text/plain")
                return
            self.app.access.drop_session(self.cookie())
            self.send(204, b"", "text/plain", {"Set-Cookie": self.session_cookie("", 0)})
        else:
            self.send(404, b"", "text/plain")

    def login(self) -> None:
        if not self.same_origin():
            self.send(403, b"", "text/plain")
            return
        key, t = self.ip(), self.lang()
        if not self.app.attempts.reserve(key):
            self.login_page(t["slow"], 429)
            return
        raw = self.body()
        if raw is None:
            self.send(400, b"", "text/plain")
            return
        pw = self.app.password
        if not pw.slots.acquire(blocking=False):
            self.app.attempts.release(key)
            self.login_page(t["busy"], 429)
            return
        try:
            ok = pw.check((parse_qs(raw.decode("utf-8", "replace")).get("password") or [""])[0])
        finally:
            pw.slots.release()
        if ok:
            self.app.attempts.release(key)
            tok = self.app.access.new_session("admin", pw_version=pw.version())
            self.send(303, b"", "text/plain", {"Location": "/", "Set-Cookie": self.session_cookie(tok)})
            return
        time.sleep(0.7)
        self.login_page(t["wrong"], 401)

    # ---------- PUT / PATCH / DELETE /api/<kind>/<id> ----------
    def do_PUT(self) -> None:
        self.guarded(lambda: self.mutate("PUT"))

    def do_PATCH(self) -> None:
        self.guarded(lambda: self.mutate("PATCH"))

    def do_DELETE(self) -> None:
        self.guarded(lambda: self.mutate("DELETE"))

    def request_data(self, method: str) -> dict | None:
        if method == "DELETE":
            return {}
        raw = self.body()
        if raw is None:
            return None
        try:
            data = json.loads(raw or b"{}")
        except (TypeError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def mutate(self, method: str) -> None:
        path = urlsplit(self.path).path
        kind = next((k for k in KINDS if path.startswith(f"/api/{k}/")), None)
        ctx = self.ctx() if kind else None
        oid = path[len(f"/api/{kind}/"):] if kind else ""
        if not kind:
            self.send(404, b"", "text/plain")
        elif not ctx:
            self.json(401, {"error": "auth"})
        elif self.headers.get("X-Tiroir") != "1" or not self.same_origin():
            self.json(403, {"error": "origin"})
        elif kind != "notes" and ctx["role"] != "admin":
            self.json(403, {"error": "admin only"})
        elif not model.ID_RE.match(oid):
            self.json(400, {"error": "id"})
        else:
            data = self.request_data(method)
            if data is None:
                self.json(400, {"error": "body"})
            elif kind == "invites":
                self.invite(method, oid, data)
            else:
                self.change(ctx, kind, method, oid, data)

    def invite(self, method: str, iid: str, data: dict) -> None:
        if method == "DELETE":
            self.app.access.delete_invite(iid)
            self.json(200, {"ok": True})
        else:
            self.json(*self.app.access.save_invite(iid, data))

    def change(self, ctx: dict, kind: str, method: str, oid: str, data: dict) -> None:
        purge = "purge=1" in urlsplit(self.path).query.split("&")
        with self.app.store.lock:
            d = self.app.store.read()
            model.purge_trash(d)
            if kind == "notes":
                why = access.can_write(ctx, method, d["notes"].get(oid), data, set(d["folders"]))
                err = (403, {"error": why}) if why else model.mutate_note(d, method, oid, data, purge)
            elif kind == "projects":
                err = model.mutate_project(d, method, oid, data, purge)
            elif kind == "cabinets":
                err = model.mutate_cabinet(d, method, oid, data, purge)
            else:
                err = model.mutate_folder(d, method, oid, data, purge)
            if err:
                self.json(*err)
                return
            model.adopt_orphans(d, self.app.names)
            model.adopt_drawers(d, self.app.names)
            self.app.store.write(d)
        self.json(200, {"ok": True})


def make_server(cfg: Config) -> ThreadingHTTPServer:
    """A ready-to-serve server (not started). Used by `tiroir serve` and by the tests."""
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    app = App(cfg)
    app.migrate()
    srv = ThreadingHTTPServer((cfg.host, cfg.port), Handler)
    srv.daemon_threads = True
    srv.app = app  # type: ignore[attr-defined]
    return srv
