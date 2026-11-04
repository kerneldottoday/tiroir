"""API tokens, POST /api/drop and the terminal client (note, inbox, answer, done, count)."""
import io
import json
import sys

import pytest

from tiroir import cli, client
from tiroir.model import INBOX_ID
from tiroir.tokens import TokenError, Tokens


def _token(s, label="pc", role="edit"):
    return Tokens(s.data).add(label, role)[1]


def _bearer(tok):
    return {"Authorization": f"Bearer {tok}", "Sec-Fetch-Site": None, "X-Tiroir": None}


def _drawer(s, admin, name="WORK"):
    s.call("PUT", "/api/projects/pwork", admin, {"name": name})
    s.call("PUT", "/api/folders/fwork", admin, {"name": "general", "project": "pwork"})


# ---------- tokens ----------
def test_token_store_rules(tmp_path):
    t = Tokens(tmp_path)
    tid, tok = t.add("pc")
    assert tok.startswith("tir_") and tok not in (tmp_path / "tokens.json").read_text()
    assert t.context(tok)["role"] == "edit" and t.context(tok)["label"] == "pc"
    assert t.context("tir_wrong") is None and t.context("nope") is None and t.context(None) is None
    for bad in ("", "a b", "x" * 30):
        with pytest.raises(TokenError):
            t.add(bad)
    with pytest.raises(TokenError):
        t.add("ok", "admin")
    assert t.revoke(tid) == 1 and t.context(tok) is None and t.revoke(tid) == 0


def test_token_command_line(tmp_path, capsys):
    data = str(tmp_path)
    assert cli.main(["--data", data, "token", "add", "laptop", "--quiet"]) == 0
    tok = capsys.readouterr().out.strip()
    assert Tokens(tmp_path).context(tok)["label"] == "laptop"
    assert cli.main(["--data", data, "token", "list"]) == 0
    assert "laptop" in capsys.readouterr().out
    assert cli.main(["--data", data, "token", "add", "bad name"]) == 1
    assert cli.main(["--data", data, "token", "revoke", "laptop"]) == 0
    assert cli.main(["--data", data, "token", "revoke", "laptop"]) == 1


def test_bearer_reads_without_csrf_header_and_never_deletes(server):
    admin = server.login()
    server.call("PUT", "/api/notes/n1", admin, {"title": "keep me"})
    tok = _token(server)
    r = server.call("GET", "/api/me", headers=_bearer(tok))
    assert r.code == 200 and r.json["role"] == "edit" and r.json["label"] == "pc"
    assert server.call("PATCH", "/api/notes/n1", body={"title": "edited"}, headers=_bearer(tok)).code == 200
    assert server.call("DELETE", "/api/notes/n1", headers=_bearer(tok)).code == 403
    assert server.call("PUT", "/api/projects/px", body={"name": "x"}, headers=_bearer(tok)).code == 403
    assert server.call("GET", "/api/invites", headers=_bearer(tok)).code == 403
    assert server.call("GET", "/api/notes", headers=_bearer("tir_forged")).code == 401


def test_wrong_tokens_are_rate_limited(server):
    tok = _token(server)
    for _ in range(5):
        server.call("GET", "/api/me", headers=_bearer("tir_guess"))
    assert server.call("GET", "/api/me", headers=_bearer(tok)).code == 401  # this address is blocked for a while


# ---------- POST /api/drop ----------
def test_drop_to_inbox_and_to_a_drawer(server):
    admin = server.login()
    _drawer(server, admin)
    tok = _token(server)
    r = server.call("POST", "/api/drop", body={"text": "Call the bank\nbefore noon"}, headers=_bearer(tok))
    assert r.code == 200
    r2 = server.call("POST", "/api/drop", body={"text": "# Order wood", "project": "work", "status": "todo"}, headers=_bearer(tok))
    assert r2.code == 200 and r2.json["folder"] == "fwork"
    projects, folders, notes = server.board(admin)
    a, b = notes[r.json["id"]], notes[r2.json["id"]]
    assert (a["title"], a["body"], a["tag"]) == ("Call the bank", "before noon", "PC")
    assert folders[a["folder"]]["project"] == INBOX_ID
    assert (b["title"], b["status"]) == ("Order wood", "todo")


def test_drop_refusals(server):
    admin = server.login()
    view = _token(server, "reader", "view")
    edit = _token(server)
    assert server.call("POST", "/api/drop", body={"text": "x"}, headers=_bearer(view)).code == 403
    assert server.call("POST", "/api/drop", body={"text": "  "}, headers=_bearer(edit)).code == 400
    assert server.call("POST", "/api/drop", body={"text": "x", "project": "nope"}, headers=_bearer(edit)).code == 404
    assert server.call("POST", "/api/drop", body={"text": "x"}).code == 401
    no_header = {"X-Tiroir": None, "Sec-Fetch-Site": "cross-site"}
    assert server.call("POST", "/api/drop", admin, {"text": "x"}, headers=no_header).code == 403  # cookie: CSRF guard
    assert server.call("POST", "/api/drop", admin, {"text": "from the page"}).code == 200


# ---------- terminal client against a real server ----------
@pytest.fixture
def term(server, tmp_path, monkeypatch):
    tok = _token(server)
    monkeypatch.setenv("TIROIR_CLIENT_CONFIG", str(tmp_path / "conf" / "client.json"))
    monkeypatch.setenv("TIROIR_URL", server.base)
    monkeypatch.setenv("TIROIR_TOKEN", tok)
    return server


def test_note_inbox_answer_done(term, tmp_path, capsys):
    admin = term.login()
    _drawer(term, admin)
    assert cli.main(["note", "Buy", "screws", "--todo"]) == 0
    assert cli.main(["note", "Plan\\nwith a body", "-t", "WORK"]) == 0
    assert cli.main(["note", "x", "-t", "missing"]) == 1
    capsys.readouterr()
    term.call("PUT", "/api/notes/aq1", admin, {"title": "Deploy tonight?"})
    store = json.loads((term.data / "notes.json").read_text(encoding="utf-8"))  # an agent question (flag set by import only)
    store["notes"]["aq1"] = {**store["notes"]["aq1"], "ask": True, "src": "from-agents/bot/q.md", "status": "todo"}
    (term.data / "notes.json").write_text(json.dumps(store), encoding="utf-8")

    assert cli.main(["inbox"]) == 0
    out = capsys.readouterr().out
    assert "questions (1)" in out and "Deploy tonight?" in out and "inbox (1)" in out and "Buy screws" in out
    assert cli.main(["count", "--ttl", "0"]) == 0
    assert capsys.readouterr().out.strip() == "tiroir 1 ?1"

    assert cli.main(["answer", "aq1", "yes,", "go"]) == 0
    assert (term.data / "answers" / "bot" / "q.md").read_text(encoding="utf-8").endswith("yes, go\n")
    buy = next(n for n in term.board(admin)[2].values() if n["title"] == "Buy screws")
    assert cli.main(["done", buy["id"][:6]]) == 0
    capsys.readouterr()
    assert cli.main(["inbox"]) == 0 and "nothing waiting" in capsys.readouterr().out
    assert cli.main(["inbox", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"inbox": [], "questions": []}


def test_show_prints_the_whole_note(term, capsys):
    admin = term.login()
    _drawer(term, admin)
    assert cli.main(["note", "Bornes → câbles\\nline one\\nline two", "-t", "WORK", "--todo"]) == 0
    capsys.readouterr()
    nid = next(n["id"] for n in term.board(admin)[2].values() if n["title"] == "Bornes → câbles")
    assert cli.main(["show", nid[:6]]) == 0
    out = capsys.readouterr().out
    assert "Bornes → câbles" in out and "line one\nline two" in out and "WORK" in out and "todo" in out and nid[:8] in out
    assert cli.main(["show", nid[:6], "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["body"] == "line one\nline two"
    assert cli.main(["show", "zz"]) == 1 and "no note" in capsys.readouterr().err


def test_render_note_pure():
    board = {"projects": [{"id": "pw", "name": "WORK"}], "folders": [{"id": "fw", "name": "docs", "project": "pw"}]}
    n = {"id": "abcdef1234", "title": "Deploy\x1b[2J?", "body": "why\x1b]0;x\x07\nnow", "folder": "fw", "status": "todo",
         "tag": "BOT", "ask": True, "answer": "yes", "createdAt": 1_700_000_000_000, "src": "from-agents/bot/q.md"}
    out = client.render(n, board)
    assert "\x1b" not in out and "\x07" not in out
    assert out.splitlines()[0].startswith("abcdef12") and "Deploy[2J?" in out and "WORK › docs" in out
    assert "question" in out and "answer" in out and "yes" in out and "from-agents/bot/q.md" in out and "why]0;x\nnow" in out
    bare = client.render({"id": "z1", "title": "Plain"}, {})
    assert "Plain" in bare and "answer" not in bare


def test_piped_output_is_utf8(monkeypatch):
    raw = io.BytesIO()
    fake = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
    monkeypatch.setattr("sys.stdout", fake)
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    from tiroir import terminal
    terminal.utf8_when_piped()
    print("câbles → ok")
    sys.stdout.flush()
    assert raw.getvalue().decode("utf-8").strip() == "câbles → ok"


def test_note_from_stdin_and_count_cache(term, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("From a pipe\nline two\n"))
    assert cli.main(["note", "-"]) == 0
    capsys.readouterr()
    assert cli.main(["count"]) == 0 and capsys.readouterr().out.strip() == "tiroir 1"
    assert cli.main(["note", "second"]) == 0
    capsys.readouterr()
    assert cli.main(["count"]) == 0 and capsys.readouterr().out.strip() == "tiroir 1"  # cached
    assert cli.main(["count", "--ttl", "0"]) == 0 and capsys.readouterr().out.strip() == "tiroir 2"


def test_login_saves_settings(server, tmp_path, monkeypatch, capsys):
    conf = tmp_path / "c" / "client.json"
    monkeypatch.setenv("TIROIR_CLIENT_CONFIG", str(conf))
    monkeypatch.delenv("TIROIR_URL", raising=False)
    monkeypatch.delenv("TIROIR_TOKEN", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(_token(server, "laptop") + "\n"))
    assert cli.main(["login", "--url", server.base, "--token-stdin"]) == 0
    assert "laptop" in capsys.readouterr().out
    saved = json.loads(conf.read_text(encoding="utf-8"))
    assert saved["url"] == server.base and saved["token"].startswith("tir_")
    assert cli.main(["login", "--url", "ftp://nope", "--token-stdin"]) == 1


def test_client_errors_are_clear(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TIROIR_CLIENT_CONFIG", str(tmp_path / "none.json"))
    monkeypatch.delenv("TIROIR_URL", raising=False)
    monkeypatch.delenv("TIROIR_TOKEN", raising=False)
    assert cli.main(["inbox"]) == 1 and "no server address" in capsys.readouterr().err
    monkeypatch.setenv("TIROIR_URL", "http://127.0.0.1:9")
    assert cli.main(["inbox"]) == 1 and "no token" in capsys.readouterr().err
    monkeypatch.setenv("TIROIR_TOKEN", "tir_x")
    assert cli.main(["inbox"]) == 1 and "unreachable" in capsys.readouterr().err
    assert cli.main(["count"]) == 0 and capsys.readouterr().out == ""  # a status line stays quiet


def test_url_command_and_its_fallback(tmp_path):
    conf_path = tmp_path / "client.json"
    ok = f'"{sys.executable}" -c "print(\'https://abc.example.org\')"'
    assert client.url_from_command({"url_command": ok}, conf_path) == "https://abc.example.org"
    bad = f'"{sys.executable}" -c "print(\'not a url\')"'
    assert client.url_from_command({"url_command": bad}, conf_path) == "https://abc.example.org"  # last good one
    env = {"TIROIR_CLIENT_CONFIG": str(conf_path), "TIROIR_TOKEN": "tir_x"}
    client.write_config(conf_path, {"url_command": ok})
    assert client.settings(env=env)[0] == "https://abc.example.org"


def test_url_command_never_opens_a_window(tmp_path, monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        return type("R", (), {"stdout": "https://abc.example.org\n"})()

    monkeypatch.setattr(client.subprocess, "run", fake_run)
    assert client.url_from_command({"url_command": "ssh box cat url.txt"}, tmp_path / "client.json") == "https://abc.example.org"
    assert seen["creationflags"] == getattr(client.subprocess, "CREATE_NO_WINDOW", 0)  # Windows: no console pops up


def test_waiting_and_find_note_pure():
    board = {"folders": [{"id": "fi", "project": INBOX_ID}, {"id": "fw", "project": "pw"}],
             "notes": [{"id": "a1", "folder": "fi", "createdAt": 2}, {"id": "a2", "folder": "fi", "status": "done"},
                       {"id": "b1", "folder": "fw", "ask": True, "createdAt": 1}, {"id": "b2", "folder": "fw", "ask": True, "answer": "ok"},
                       {"id": "a3", "folder": "fi", "deletedAt": 5}]}
    inbox, questions = client.waiting(board)
    assert [n["id"] for n in inbox] == ["a1"] and [n["id"] for n in questions] == ["b1"]
    assert client.find_note(board, "b1")["id"] == "b1"
    with pytest.raises(client.ClientError):
        client.find_note(board, "a")  # ambiguous
    with pytest.raises(client.ClientError):
        client.find_note(board, "zz")
    assert client.count_text(0, 0) == "" and client.count_text(3, 0) == "tiroir 3" and client.count_text(0, 2) == "tiroir ?2"


# ---------- hardening (security review 1.3.0) ----------
def test_token_never_travels_in_clear_to_a_public_host():
    assert client.valid_url("https://tiroir.example.org/") == "https://tiroir.example.org"
    for ok in ("http://127.0.0.1:5950", "http://localhost:5950", "http://192.168.1.20", "http://100.101.102.103", "http://pi5:5950"):
        assert client.valid_url(ok), ok
    for bad in ("http://tiroir.example.org", "http://8.8.8.8", "ftp://x", "https://a/b", "https://a b", ""):
        assert client.valid_url(bad) is None, bad


def test_redirects_are_not_followed_with_the_token():
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    seen = []

    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.headers.get("Authorization"))
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:9/steal")
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Redirect)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with pytest.raises(client.ClientError, match="redirect refused"):
            client.call(f"http://127.0.0.1:{srv.server_address[1]}", "tir_secret", "GET", "/api/notes")
    finally:
        srv.shutdown()
    assert seen == ["Bearer tir_secret"]  # asked once, never resent elsewhere


def test_control_characters_are_stripped_from_titles():
    n = {"id": "a1", "title": "evil\x1b]0;pwned\x07 title", "folder": "f"}
    assert "\x1b" not in client.line(n, {"f": "tab\x1b[2J"}) and "evil]0;pwned title" in client.line(n, {})


def test_broken_tokens_file_is_never_overwritten(tmp_path):
    (tmp_path / "tokens.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(TokenError):
        Tokens(tmp_path).add("pc")
    with pytest.raises(TokenError):
        Tokens(tmp_path).revoke("pc")
    assert (tmp_path / "tokens.json").read_text(encoding="utf-8") == "{broken"


def test_last_use_is_kept_apart_from_the_tokens(tmp_path):
    t = Tokens(tmp_path)
    tid, tok = t.add("pc")
    before = (tmp_path / "tokens.json").read_text(encoding="utf-8")
    assert t.context(tok)
    assert (tmp_path / "tokens.json").read_text(encoding="utf-8") == before  # the server never rewrites tokens.json
    assert t.list()[0]["usedAt"] > 0
    t.revoke(tid)
    assert t.context(tok) is None
