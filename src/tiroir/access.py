"""Sessions and invitations (standard library only).

- Roles: "admin" (password, every right), "edit" (guest: create / edit notes), "view" (guest: read only).
  Only the admin deletes, manages drawers and tabs, the trash and the invitations.
- An invitation is a secret link /i/<token>, a role and a scope: every tab (folders = None) or a list of tabs.
  Deleting the invitation ends at once every session opened with that link.
- Sessions are stored on disk as the SHA-256 of the cookie (never the cookie itself): they survive restarts.
  Admin sessions remember the password version: a new password ends them all.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

SESSION_DAYS = 30
MAX_INVITES = 100
MAX_SESSIONS = 500
ROLES = ("view", "edit")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


class Store:
    """sessions.json and invites.json in the data folder (0600, atomic writes)."""

    def __init__(self, data_dir: Path) -> None:
        self.sessions_path = data_dir / "sessions.json"
        self.invites_path = data_dir / "invites.json"
        self.lock = threading.Lock()

    # ---------- files ----------
    @staticmethod
    def _read(path: Path) -> dict:
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _write(path: Path, obj: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)

    # ---------- sessions ----------
    @staticmethod
    def _key(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def new_session(self, role: str, invite: str = "", pw_version: int = 0) -> str:
        tok = secrets.token_urlsafe(32)
        now = time.time()
        entry = {"exp": now + SESSION_DAYS * 86400, "role": "admin" if role == "admin" else "guest", "invite": invite}
        if role == "admin":
            entry["pwv"] = pw_version
        with self.lock:
            s = {k: v for k, v in self._read(self.sessions_path).items() if v.get("exp", 0) > now}
            if len(s) >= MAX_SESSIONS:  # keep the most recent ones
                s = dict(sorted(s.items(), key=lambda kv: kv[1].get("exp", 0))[-(MAX_SESSIONS - 1):])
            self._write(self.sessions_path, {**s, self._key(tok): entry})
        return tok

    def drop_session(self, token: str | None) -> None:
        if not token:
            return
        with self.lock:
            s = self._read(self.sessions_path)
            key = self._key(token)
            if key in s:
                self._write(self.sessions_path, {k: v for k, v in s.items() if k != key})

    def drop_all(self) -> int:
        """Log out every device (admin and guests). Returns how many sessions were ended."""
        with self.lock:
            n = len(self._read(self.sessions_path))
            self._write(self.sessions_path, {})
        return n

    def context(self, token: str | None, pw_version: int) -> dict | None:
        """Rights of the session: {"role": admin|edit|view, "folders": None (all) or list, "label": str}; None if invalid."""
        if not token or len(token) > 100:
            return None
        sess = self._read(self.sessions_path).get(self._key(token))
        if not sess or sess.get("exp", 0) <= time.time():
            return None
        if sess.get("role") == "admin":
            if sess.get("pwv", 0) != pw_version:
                return None  # the password changed since this session was opened
            return {"role": "admin", "folders": None, "label": "admin", "invite": ""}
        inv = self._read(self.invites_path).get(sess.get("invite", ""))
        if not inv:
            return None  # invitation deleted: session ended
        return {"role": inv["role"], "folders": inv.get("folders"), "label": inv.get("label", ""), "invite": sess["invite"]}

    # ---------- invitations ----------
    def list_invites(self) -> list[dict]:
        return [{"id": k, **v} for k, v in self._read(self.invites_path).items()]

    def find_invite(self, token: str) -> str | None:
        if not token or len(token) > 100:
            return None
        found = None
        for iid, inv in self._read(self.invites_path).items():
            if hmac.compare_digest(inv.get("token", ""), token):
                found = iid
        return found

    def save_invite(self, iid: str, data: dict) -> tuple[int, dict]:
        """Create (token generated) or edit an invitation. Returns (HTTP code, invitation or error)."""
        if not ID_RE.match(iid):
            return 400, {"error": "id"}
        with self.lock:
            invs = self._read(self.invites_path)
            base = invs.get(iid)
            if base is None and len(invs) >= MAX_INVITES:
                return 507, {"error": "too many invitations"}
            inv = dict(base or {"token": secrets.token_urlsafe(24), "createdAt": int(time.time() * 1000), "role": "view",
                                "folders": None, "label": ""})
            if "label" in data:
                inv["label"] = " ".join(str(data["label"]).split())[:40]
            if data.get("role") in ROLES:
                inv["role"] = data["role"]
            if "folders" in data:
                f = data["folders"]
                inv["folders"] = None if f is None else [x for x in f if isinstance(x, str) and ID_RE.match(x)][:200] \
                    if isinstance(f, list) else inv.get("folders")
            if not inv["label"]:
                return 400, {"error": "name"}
            self._write(self.invites_path, {**invs, iid: inv})
        return 200, {"id": iid, **inv}

    def delete_invite(self, iid: str) -> None:
        with self.lock:
            invs = self._read(self.invites_path)
            if iid in invs:
                self._write(self.invites_path, {k: v for k, v in invs.items() if k != iid})
            s = self._read(self.sessions_path)
            kept = {k: v for k, v in s.items() if v.get("invite") != iid}
            if len(kept) != len(s):
                self._write(self.sessions_path, kept)


# ---------- access rules for notes (pure, testable) ----------
def in_scope(ctx: dict, folder: str, existing: set[str]) -> bool:
    """Is the tab (id, or "" / unknown = no tab) inside the session's scope?"""
    scope = ctx.get("folders")
    if scope is None:
        return True
    f = folder if folder in existing else ""
    return f != "" and f in scope


def can_see(ctx: dict, note: dict, existing: set[str]) -> bool:
    if note.get("deletedAt") and ctx["role"] != "admin":
        return False
    return in_scope(ctx, note.get("folder", ""), existing)


def can_write(ctx: dict, method: str, note: dict | None, data: dict, existing: set[str]) -> str | None:
    """None if allowed, else the reason. Admin: everything. Edit: create / edit inside its scope, never delete."""
    if ctx["role"] == "admin":
        return None
    if ctx["role"] != "edit":
        return "read only"
    if method == "DELETE" or "restore" in data:
        return "admin only"
    if note is not None and not can_see(ctx, note, existing):
        return "out of your scope"
    if note is None and method != "PUT":
        return "missing"
    target = data.get("folder", note.get("folder", "") if note else "")
    if not in_scope(ctx, str(target or ""), existing):
        return "tab out of your scope"
    return None
