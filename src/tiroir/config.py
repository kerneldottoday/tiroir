"""Settings, read once from environment variables (no config file needed)."""
from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path

COOKIE_MODES = ("auto", "always", "never")
LANGS = ("en", "fr")


@dataclass(frozen=True)
class Config:
    data_dir: Path          # notes.json, password.json, sessions.json, invites.json
    host: str
    port: int
    agents_dir: Path | None  # drop folder for agent notes (<agents_dir>/<agent>/<note>.md); None = disabled
    trust_proxy: tuple      # networks whose proxy headers are believed (empty = none)
    cookie_secure: str      # auto | always | never
    lang: str               # language of the drawers created by the server (inbox, misc, default tabs)


def default_data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or (os.environ.get("APPDATA") if os.name == "nt" else "")
    return Path(base or Path.home() / ".local" / "share") / "tiroir"


LOOPBACK = ("127.0.0.0/8", "::1/128")


def parse_proxies(value: str | None) -> tuple:
    """TIROIR_TRUST_PROXY: empty/0 = trust nobody, 1/true = a proxy on this machine, or a list of networks
    ("172.16.0.0/12, 10.0.0.5") such as the Docker network of a reverse proxy container."""
    v = (value or "").strip().lower()
    if v in ("", "0", "false", "no", "off"):
        return ()
    items = LOOPBACK if v in ("1", "true", "yes", "on") else [x.strip() for x in v.split(",") if x.strip()]
    try:
        return tuple(ipaddress.ip_network(x, strict=False) for x in items)
    except ValueError as exc:
        raise SystemExit(f"tiroir: TIROIR_TRUST_PROXY: {exc}") from exc


def from_env(env: dict[str, str] | None = None) -> Config:
    """Build the settings from TIROIR_* variables; invalid values fail fast with a clear message."""
    e = dict(os.environ if env is None else env)
    try:
        port = int(e.get("TIROIR_PORT", "5950"))
    except ValueError as exc:
        raise SystemExit("tiroir: TIROIR_PORT must be a number") from exc
    if not 1 <= port <= 65535:
        raise SystemExit("tiroir: TIROIR_PORT must be between 1 and 65535")
    cookie = e.get("TIROIR_COOKIE_SECURE", "auto").strip().lower()
    if cookie not in COOKIE_MODES:
        raise SystemExit(f"tiroir: TIROIR_COOKIE_SECURE must be one of {', '.join(COOKIE_MODES)}")
    lang = e.get("TIROIR_LANG", "en").strip().lower()[:2]
    agents = e.get("TIROIR_AGENTS_DIR", "").strip()
    return Config(
        data_dir=Path(e.get("TIROIR_DATA_DIR") or default_data_dir()).expanduser(),
        host=e.get("TIROIR_HOST", "127.0.0.1"),
        port=port,
        agents_dir=Path(agents).expanduser() if agents else None,
        trust_proxy=parse_proxies(e.get("TIROIR_TRUST_PROXY")),
        cookie_secure=cookie,
        lang=lang if lang in LANGS else "en",
    )
