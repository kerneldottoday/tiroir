"""Command line: tiroir [serve] | set-password | logout-all | export | version."""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from dataclasses import replace
from pathlib import Path

from . import __version__
from .access import Store as AccessStore
from .auth import Password, PasswordError, first_run_password
from .config import Config, from_env
from .server import make_server
from .store import NotesStore, StoreError


def serve(cfg: Config) -> int:
    pw = Password(cfg.data_dir)
    first_run_password(pw)
    if not pw.is_set():
        print("tiroir: no password yet. Run « tiroir set-password » first (or set TIROIR_PASSWORD once).", file=sys.stderr)
        return 1
    srv = make_server(cfg)
    agents = f", agent drop folder {cfg.agents_dir}" if cfg.agents_dir else ""
    print(f"tiroir {__version__}: http://{cfg.host}:{cfg.port} (data in {cfg.data_dir}{agents})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def set_password(cfg: Config, from_stdin: bool) -> int:
    if from_stdin:
        plain = sys.stdin.readline().rstrip("\r\n")
    else:
        plain = getpass.getpass("New password (14 characters or more): ")
        if getpass.getpass("Same password again: ") != plain:
            print("tiroir: the two passwords differ, nothing changed.", file=sys.stderr)
            return 1
    try:
        version = Password(cfg.data_dir).set(plain)
    except PasswordError as exc:
        print(f"tiroir: password refused ({exc}), nothing changed.", file=sys.stderr)
        return 1
    note = " Every device signed in as admin is now logged out." if version > 1 else ""
    print(f"tiroir: password saved in {cfg.data_dir / 'password.json'} (hash only).{note}")
    return 0


def export(cfg: Config, out: str | None) -> int:
    """The whole board as JSON (notes, tabs, drawers, trash included)."""
    try:
        d = NotesStore(cfg.data_dir).read()
    except StoreError as exc:
        print(f"tiroir: {exc}", file=sys.stderr)
        return 1
    text = json.dumps({k: d[k] for k in ("cabinets", "projects", "folders", "notes")}, ensure_ascii=False, indent=2)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"tiroir: {len(d['notes'])} notes written to {out}")
    else:
        sys.stdout.write(text + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tiroir", description="A filing cabinet for your sticky notes, on your own server.")
    p.add_argument("--data", help="data folder (default: TIROIR_DATA_DIR or ~/.local/share/tiroir)")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("serve", help="start the server (default)")
    s.add_argument("--host")
    s.add_argument("--port", type=int)
    sp = sub.add_parser("set-password", help="set or change the admin password (logs out every admin device)")
    sp.add_argument("--stdin", action="store_true", help="read the password from standard input")
    sub.add_parser("logout-all", help="end every session (admin and guests)")
    ex = sub.add_parser("export", help="print the whole board as JSON")
    ex.add_argument("-o", "--out", help="write to this file instead of the screen")
    sub.add_parser("version", help="print the version")
    args = p.parse_args(argv)

    cfg = from_env()
    if args.data:
        cfg = replace(cfg, data_dir=Path(args.data).expanduser())
    if args.cmd == "set-password":
        return set_password(cfg, args.stdin)
    if args.cmd == "logout-all":
        print(f"tiroir: {AccessStore(cfg.data_dir).drop_all()} sessions ended.")
        return 0
    if args.cmd == "export":
        return export(cfg, args.out)
    if args.cmd == "version":
        print(__version__)
        return 0
    if args.cmd == "serve":
        cfg = replace(cfg, host=args.host or cfg.host, port=args.port or cfg.port)
    return serve(cfg)


if __name__ == "__main__":
    sys.exit(main())
