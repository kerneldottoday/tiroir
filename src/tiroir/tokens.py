"""API tokens: a terminal, a script or an agent talks to Tiroir with « Authorization: Bearer <token> ».

tokens.json = {"<id>": {"hash": sha256 of the token, "label": str, "role": "edit"|"view", "createdAt": ms}};
tokens-used.json = {"<id>": ms} (last use, kept apart so the server never rewrites tokens.json).
The token itself is shown once, at creation, and never stored. A token can never delete (same rights as an
« edit » invitation on every tab); revoking it is immediate. Created and revoked from the server's command line only.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from pathlib import Path

from .store import write_file

PREFIX = "tir_"
ROLES = ("edit", "view")
MAX_TOKENS = 50
LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,23}$")
TOUCH_EVERY = 3600  # « last used » is written at most once an hour per token


class TokenError(ValueError):
    """Bad label or role, or too many tokens."""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Tokens:
    """tokens.json in the data folder, re-read at every check (a revoke from the command line works at once)."""

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "tokens.json"
        self.used_path = data_dir / "tokens-used.json"
        self.lock = threading.Lock()

    @staticmethod
    def _load(path: Path, strict: bool = False) -> dict:
        """Content of a JSON file; {} if missing. strict: a broken file raises instead of looking empty."""
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            if strict:
                raise TokenError(f"{path.name} is unreadable, fix or remove it first") from exc
            return {}
        if not isinstance(d, dict):
            if strict:
                raise TokenError(f"{path.name} is unreadable, fix or remove it first")
            return {}
        return d

    def _read(self, strict: bool = False) -> dict:
        return self._load(self.path, strict)

    def _write(self, d: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_file(self.path, json.dumps(d, ensure_ascii=False))

    def add(self, label: str, role: str = "edit") -> tuple[str, str]:
        """New token; returns (id, token). The token is shown once and never stored."""
        if not LABEL_RE.match(label or ""):
            raise TokenError("label: 1-24 letters, digits, « _ . - »")
        if role not in ROLES:
            raise TokenError(f"role: one of {', '.join(ROLES)}")
        token = PREFIX + secrets.token_urlsafe(32)
        with self.lock:
            d = self._read(strict=True)
            if len(d) >= MAX_TOKENS:
                raise TokenError(f"at most {MAX_TOKENS} tokens")
            tid = "k" + secrets.token_hex(4)
            entry = {"hash": _hash(token), "label": label, "role": role, "createdAt": int(time.time() * 1000)}
            self._write({**d, tid: entry})
        return tid, token

    def list(self) -> list[dict]:
        used = self._load(self.used_path)
        return [{"id": k, "label": v.get("label"), "role": v.get("role"), "createdAt": v.get("createdAt"), "usedAt": used.get(k, 0)}
                for k, v in self._read().items()]

    def revoke(self, tid_or_label: str) -> int:
        """Remove the token with this id, or every token with this label. Returns how many were removed."""
        with self.lock:
            d = self._read(strict=True)
            kept = {k: v for k, v in d.items() if tid_or_label not in (k, v.get("label"))}
            if len(kept) != len(d):
                self._write(kept)
        return len(d) - len(kept)

    def context(self, token: str | None) -> dict | None:
        """Rights of a token, like a session: {"role", "folders": None, "label", "invite": ""}; None if unknown."""
        if not token or not token.startswith(PREFIX) or len(token) > 100:
            return None
        digest = _hash(token)
        d = self._read()
        found = None
        for tid, entry in d.items():
            if hmac.compare_digest(str(entry.get("hash", "")), digest):
                found = tid
        if found is None:
            return None
        entry = d[found]
        self._touch(found)
        return {"role": entry.get("role") if entry.get("role") in ROLES else "view", "folders": None,
                "label": entry.get("label", ""), "invite": "", "token": found}

    def _touch(self, tid: str) -> None:
        now = int(time.time() * 1000)
        with self.lock:
            used = self._load(self.used_path)
            if now - int(used.get(tid) or 0) < TOUCH_EVERY * 1000:
                return
            live = set(self._read())
            write_file(self.used_path, json.dumps({k: v for k, v in {**used, tid: now}.items() if k in live}))
