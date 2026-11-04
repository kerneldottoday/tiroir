"""Terminal commands of the command line (login, note, inbox, show, answer, done, count): parsing and printing only,
the work is in client.py."""
from __future__ import annotations

import getpass
import os
import sys

from . import client


def add_client_commands(sub) -> None:
    lg = sub.add_parser("login", help="save the server address and a token for the terminal commands")
    lg.add_argument("--url", help="address of the server, e.g. https://tiroir.example.org")
    lg.add_argument("--url-command", help="command printing the address (for an address that changes)")
    lg.add_argument("--token-stdin", action="store_true", help="read the token from standard input")
    nt = sub.add_parser("note", help="drop a note: first line = title (« - » reads standard input)")
    nt.add_argument("text", nargs="+")
    nt.add_argument("-t", "--drawer", default="", help="drawer name (default: the inbox)")
    nt.add_argument("-s", "--status", default="", help="todo | doing | info | done")
    nt.add_argument("--todo", action="store_true", help="same as --status todo")
    nt.add_argument("--ask", action="store_true", help="a question waiting for your answer (read it back with « tiroir show <id> »)")
    ib = sub.add_parser("inbox", help="questions of agents and notes waiting in the inbox")
    ib.add_argument("--json", action="store_true")
    sh = sub.add_parser("show", help="print one note in full (title, text, answer)")
    sh.add_argument("id")
    sh.add_argument("--json", action="store_true")
    an = sub.add_parser("answer", help="answer an agent question (the agent reads it back)")
    an.add_argument("id")
    an.add_argument("text", nargs="+")
    dn = sub.add_parser("done", help="mark a note done")
    dn.add_argument("id")
    ct = sub.add_parser("count", help="short text for a status line, cached (empty when nothing waits)")
    ct.add_argument("--ttl", type=int, default=client.COUNT_TTL)
    for parser in (nt, ib, sh, an, dn, ct):
        parser.add_argument("--url", help="server address (else TIROIR_URL or the config file)")


def login(args) -> int:
    path = client.config_path()
    conf = client.read_config(path)
    if args.url:
        if not client.valid_url(args.url):
            print("tiroir: the address must look like https://host or http://host:port", file=sys.stderr)
            return 1
        conf = {**conf, "url": client.valid_url(args.url)}
    if args.url_command:
        conf = {**conf, "url_command": args.url_command}
    token = sys.stdin.readline().strip() if args.token_stdin else getpass.getpass("Token (tir_...): ").strip()
    if token:
        conf = {**conf, "token": token}
    client.write_config(path, conf)
    url, tok, _ = client.settings()
    me = client.call(url, tok, "GET", "/api/me")
    print(f"tiroir: connected to {url} as « {me.get('label', '')} » ({me.get('role', '')}). Settings in {path}")
    return 0


def run(args) -> str:
    if args.cmd == "count":
        hit = client.cached_count(client.config_path().parent, args.ttl)
        if hit is not None:
            return hit
    url, token, folder = client.settings(getattr(args, "url", None))
    if args.cmd == "note":
        text = sys.stdin.read() if args.text == ["-"] else " ".join(args.text).replace("\\n", "\n")
        return client.cmd_note(url, token, text, args.drawer, "todo" if args.todo else args.status, args.ask)
    if args.cmd == "inbox":
        return client.cmd_inbox(url, token, args.json)
    if args.cmd == "show":
        return client.cmd_show(url, token, args.id, args.json)
    if args.cmd == "answer":
        return client.cmd_answer(url, token, args.id, " ".join(args.text))
    if args.cmd == "done":
        return client.cmd_done(url, token, args.id)
    return client.cmd_count(url, token, folder, args.ttl)


def utf8_when_piped() -> None:
    """A console prints any text; a pipe (Git Bash, an agent, a file) gets UTF-8 instead of the Windows code page."""
    if not hasattr(sys.stdout, "reconfigure"):
        return
    piped = not sys.stdout.isatty() and not os.environ.get("PYTHONIOENCODING")
    sys.stdout.reconfigure(**({"encoding": "utf-8"} if piped else {}), errors="replace")


def run_client(args) -> int:
    utf8_when_piped()
    try:
        if args.cmd == "login":
            return login(args)
        out = run(args)
    except client.ClientError as exc:
        if args.cmd == "count":
            return 0  # a status line stays quiet
        print(f"tiroir: {exc}", file=sys.stderr)
        return 1
    if out:
        print(out)
    return 0
