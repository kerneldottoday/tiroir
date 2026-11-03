"""Terminal client: talk to a Tiroir server with an API token (standard library only).

Settings, first found wins:
    url    --url, TIROIR_URL, « url_command » of the config file (its first output line), « url » of the config file
    token  TIROIR_TOKEN, « token » of the config file
Config file: TIROIR_CLIENT_CONFIG, else %APPDATA%\\tiroir\\client.json (Windows) or ~/.config/tiroir/client.json.
« url_command » is for a server whose address changes (e.g. a quick tunnel): the last good answer is kept as a fallback.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__

INBOX_ID = "parrivees"
URL_RE = re.compile(r"^(https?)://([A-Za-z0-9.-]+)(:\d{1,5})?/?$")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
TAILNET = ipaddress.ip_network("100.64.0.0/10")
TIMEOUT = 10
COUNT_TTL = 120


class ClientError(Exception):
    """A message for the user: no settings, server unreachable, refused request."""


# ---------- settings ----------
def config_path(env: dict | None = None) -> Path:
    e = os.environ if env is None else env
    if e.get("TIROIR_CLIENT_CONFIG"):
        return Path(e["TIROIR_CLIENT_CONFIG"]).expanduser()
    base = e.get("APPDATA") if os.name == "nt" else (e.get("XDG_CONFIG_HOME") or "")
    return Path(base or Path.home() / ".config") / "tiroir" / "client.json"


def read_config(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def write_config(path: Path, conf: dict) -> None:
    """Private from the first byte (0600 file in a 0700 folder): it holds the token and a command that is run."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(conf, ensure_ascii=False, indent=2))
    os.replace(tmp, path)


def local_host(host: str) -> bool:
    """localhost, a name without a dot (home network, Tailscale), or a loopback / private / Tailscale address."""
    if host == "localhost" or "." not in host:
        return True
    try:
        a = ipaddress.ip_address(host)
    except ValueError:
        return False
    return a.is_loopback or a.is_private or a in TAILNET


def valid_url(url: str) -> str | None:
    """https, or plain http only towards this machine or a private network (the token must never travel in clear)."""
    m = URL_RE.match((url or "").strip())
    if not m or (m.group(1) == "http" and not local_host(m.group(2).lower())):
        return None
    return m.group(0).rstrip("/")


def url_from_command(conf: dict, path: Path) -> str | None:
    """Run « url_command » (your own config file, never data from the server); keep the last good answer."""
    cache = path.with_name("last-url.txt")
    try:
        out = subprocess.run(conf["url_command"], shell=True, capture_output=True, text=True, timeout=12,
                             stdin=subprocess.DEVNULL).stdout
        url = valid_url((out.strip().splitlines() or [""])[0])
    except (OSError, subprocess.SubprocessError):
        url = None
    if url:
        cache.write_text(url, encoding="utf-8")
        return url
    try:
        return valid_url(cache.read_text(encoding="utf-8"))
    except OSError:
        return None


def settings(url: str | None = None, env: dict | None = None) -> tuple[str, str, Path]:
    """(url, token, config folder) or ClientError with what is missing."""
    e = os.environ if env is None else env
    path = config_path(e)
    conf = read_config(path)
    found = valid_url(url or "") or valid_url(e.get("TIROIR_URL", ""))
    if not found and conf.get("url_command"):
        found = url_from_command(conf, path)
    found = found or valid_url(conf.get("url", ""))
    token = e.get("TIROIR_TOKEN") or conf.get("token", "")
    if not found:
        raise ClientError(f"no server address: « tiroir login --url https://... » (config: {path})")
    if not token:
        raise ClientError(f"no token: create one on the server with « tiroir token add <name> », then « tiroir login » (config: {path})")
    return found, token, path.parent


# ---------- HTTP ----------
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # never resend the token to another address
        return None


OPENER = urllib.request.build_opener(_NoRedirect)


def call(url: str, token: str, method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url + path, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": f"tiroir-cli/{__version__}"})
    try:
        with OPENER.open(req, timeout=TIMEOUT) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            why = json.loads(exc.read() or b"{}").get("error", "")
        except ValueError:
            why = ""
        hint = " (token unknown or revoked?)" if exc.code == 401 else \
            " (redirect refused: give the final https address)" if 300 <= exc.code < 400 else ""
        raise ClientError(f"server said {exc.code} {why}{hint}".strip()) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ClientError(f"server unreachable ({url}): {getattr(exc, 'reason', exc)}") from exc
    except ValueError as exc:
        raise ClientError("the answer is not JSON: is this a Tiroir server?") from exc


# ---------- what the board says (pure, testable) ----------
def waiting(board: dict) -> tuple[list[dict], list[dict]]:
    """(inbox notes not done, questions of agents without an answer), oldest first."""
    inbox_tabs = {f["id"] for f in board.get("folders", []) if f.get("project") == INBOX_ID and not f.get("deletedAt")}
    live = [n for n in board.get("notes", []) if not n.get("deletedAt") and n.get("status") != "done"]
    live = sorted(live, key=lambda n: n.get("createdAt", 0))
    questions = [n for n in live if n.get("ask") and not str(n.get("answer", "")).strip()]
    asked = {n["id"] for n in questions}
    inbox = [n for n in live if n.get("folder") in inbox_tabs and n["id"] not in asked]
    return inbox, questions


def find_note(board: dict, prefix: str) -> dict:
    hits = [n for n in board.get("notes", []) if n["id"].startswith(prefix) and not n.get("deletedAt")]
    if len(hits) != 1:
        raise ClientError(f"« {prefix} »: {'no note' if not hits else f'{len(hits)} notes'} with this id (see « tiroir inbox »)")
    return hits[0]


def clean(text) -> str:
    """Text written by agents or guests, printed without terminal control characters."""
    return CONTROL.sub("", str(text or ""))


def line(n: dict, tabs: dict) -> str:
    mark = "?" if n.get("ask") else " "
    where = clean(tabs.get(n.get("folder", ""), ""))
    return f"{clean(n['id'])[:8]}  {mark} {where[:14]:<14}  {clean(n.get('title', ''))[:70]}"


# ---------- commands ----------
def cmd_note(url: str, token: str, text: str, project: str, status: str) -> str:
    r = call(url, token, "POST", "/api/drop", {"text": text, "project": project, "status": status})
    return f"tiroir: note {r.get('id', '')[:8]} dropped{' in ' + project if project else ' in the inbox'}."


def cmd_inbox(url: str, token: str, as_json: bool) -> str:
    board = call(url, token, "GET", "/api/notes")
    inbox, questions = waiting(board)
    if as_json:
        return json.dumps({"inbox": inbox, "questions": questions}, ensure_ascii=False, indent=2)
    tabs = {f["id"]: f.get("name", "") for f in board.get("folders", [])}
    out = [f"questions ({len(questions)})"] + [line(n, tabs) for n in questions] if questions else []
    out += [f"inbox ({len(inbox)})"] + [line(n, tabs) for n in inbox] if inbox else []
    return "\n".join(out) or "tiroir: nothing waiting."


def cmd_answer(url: str, token: str, prefix: str, text: str) -> str:
    note = find_note(call(url, token, "GET", "/api/notes"), prefix)
    call(url, token, "PATCH", f"/api/notes/{note['id']}", {"answer": text, "status": "done", "updatedAt": int(time.time() * 1000)})
    return f"tiroir: answered « {clean(note.get('title', ''))[:50]} »."


def cmd_done(url: str, token: str, prefix: str) -> str:
    note = find_note(call(url, token, "GET", "/api/notes"), prefix)
    call(url, token, "PATCH", f"/api/notes/{note['id']}", {"status": "done", "updatedAt": int(time.time() * 1000)})
    return f"tiroir: « {clean(note.get('title', ''))[:50]} » done."


def count_text(inbox: int, questions: int) -> str:
    parts = ([f"{inbox}"] if inbox else []) + ([f"?{questions}"] if questions else [])
    return f"tiroir {' '.join(parts)}" if parts else ""


def cached_count(folder: Path, ttl: int) -> str | None:
    """The cached status-line text if younger than `ttl` seconds (checked before any setting or network call)."""
    try:
        c = json.loads((folder / "count.json").read_text(encoding="utf-8"))
        return str(c["text"]) if time.time() - float(c["at"]) < ttl else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def cmd_count(url: str, token: str, folder: Path, ttl: int = COUNT_TTL) -> str:
    """Short text for a status line (« tiroir 3 ?1 », empty when nothing waits), cached `ttl` seconds."""
    cache = folder / "count.json"
    hit = cached_count(folder, ttl)
    if hit is not None:
        return hit
    inbox, questions = waiting(call(url, token, "GET", "/api/notes"))
    text = count_text(len(inbox), len(questions))
    folder.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"at": time.time(), "text": text, "inbox": len(inbox), "questions": len(questions)}), encoding="utf-8")
    return text
