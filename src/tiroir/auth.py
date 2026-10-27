"""Admin password (scrypt hash only, never the plain text) and login rate limiting.

password.json = {"scrypt": "<salt hex>$<hash hex>", "version": n}. Every change bumps `version`;
admin sessions remember the version they were opened with, so a new password logs out every device.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import threading
import time
from pathlib import Path

from .store import write_file

MIN_PASSWORD = 14
SCRYPT = dict(n=2**15, r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024)
FAIL_WINDOW = 900
FAIL_PER_IP = 5
FAIL_GLOBAL = 100


class PasswordError(ValueError):
    """The password does not meet the rules."""


def _hash(plain: str, salt: bytes) -> bytes:
    return hashlib.scrypt(plain.encode()[:256], salt=salt, **SCRYPT)


class Password:
    """The admin password file, re-read when it changes on disk (e.g. `tiroir set-password` while running)."""

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "password.json"
        self._cache: tuple[float, dict | None] = (-1.0, None)
        self._lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(2)  # at most 2 scrypt computations at once

    def _load(self) -> dict | None:
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            return None
        with self._lock:
            if self._cache[0] != mtime:
                try:
                    d = json.loads(self.path.read_text(encoding="utf-8"))
                    salt_hex, dig_hex = d["scrypt"].split("$")
                    d = {"salt": bytes.fromhex(salt_hex), "hash": bytes.fromhex(dig_hex), "version": int(d.get("version", 1))}
                except (OSError, ValueError, KeyError, AttributeError):
                    d = None
                self._cache = (mtime, d)
            return self._cache[1]

    def is_set(self) -> bool:
        return self._load() is not None

    def version(self) -> int:
        d = self._load()
        return d["version"] if d else 0

    def check(self, attempt: str) -> bool:
        d = self._load()
        if d is None:
            return False
        return hmac.compare_digest(_hash(attempt, d["salt"]), d["hash"])

    def set(self, plain: str) -> int:
        """Store a new password; returns its version. Raises PasswordError if too short."""
        if len(plain) < MIN_PASSWORD:
            raise PasswordError(f"at least {MIN_PASSWORD} characters")
        salt = secrets.token_bytes(16)
        version = self.version() + 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_file(self.path, json.dumps({"scrypt": f"{salt.hex()}${_hash(plain, salt).hex()}", "version": version}))
        return version


def first_run_password(pw: Password, env: dict[str, str] | None = None) -> None:
    """Docker-friendly start: TIROIR_PASSWORD is hashed once if no password is stored yet (then it is ignored)."""
    plain = (os.environ if env is None else env).get("TIROIR_PASSWORD", "")
    if plain and not pw.is_set():
        pw.set(plain)
        print("tiroir: password stored from TIROIR_PASSWORD; you can now remove it from the environment.", flush=True)


# ---------- rate limiting of login attempts ----------
def ip_key(raw: str) -> str:
    """Rate-limit key: the IPv4 address, or the /64 prefix for IPv6 (rotating inside a /64 is free)."""
    try:
        a = ipaddress.ip_address(raw.strip())
    except ValueError:
        return "unknown"
    return str(ipaddress.ip_network(f"{a}/64", strict=False)) if a.version == 6 else str(a)


class Attempts:
    """At most FAIL_PER_IP attempts per address and FAIL_GLOBAL in total per FAIL_WINDOW seconds.
    An attempt is booked BEFORE the scrypt check and released if the password is right."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.fails: dict[str, list[float]] = {}
        self.global_fails: list[float] = []

    def reserve(self, key: str) -> bool:
        now = time.time()
        with self.lock:
            self.fails = {k: kept for k, v in self.fails.items() if (kept := [t for t in v if now - t < FAIL_WINDOW])}
            self.global_fails = [t for t in self.global_fails if now - t < FAIL_WINDOW]
            mine = self.fails.get(key, [])
            if len(mine) >= FAIL_PER_IP or len(self.global_fails) >= FAIL_GLOBAL:
                return False
            self.fails[key] = mine + [now]
            self.global_fails = self.global_fails + [now]
            return True

    def release(self, key: str) -> None:
        with self.lock:
            if self.fails.get(key):
                self.fails[key] = self.fails[key][:-1]
            if self.global_fails:
                self.global_fails = self.global_fails[:-1]
