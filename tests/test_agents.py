"""Agent drop folder: a .md file becomes a note in the inbox drawer, safely."""
import os
import time

import pytest

from tiroir.model import INBOX_ID


def _wait_for(s, admin, pred, tries=30):
    for _ in range(tries):
        board = s.board(admin)
        if pred(board):
            return board
        s.app.last_import = 0  # skip the 10 s throttle
        time.sleep(0.05)
    raise AssertionError("agent note never arrived")


def test_agent_file_becomes_a_note(make, tmp_path):
    drop = tmp_path / "agents"
    (drop / "scout").mkdir(parents=True)
    (drop / "scout" / "2026-10-27-report.md").write_text("# Night report\n\nAll good.\n---\n", encoding="utf-8")
    (drop / "scout" / "ignored.exe").write_text("x", encoding="utf-8")
    s = make(agents_dir=drop)
    admin = s.login()
    projects, folders, notes = _wait_for(s, admin, lambda b: any(n.get("src") for n in b[2].values()))
    note = next(n for n in notes.values() if n.get("src"))
    assert note["title"] == "Night report" and note["body"] == "All good."
    assert note["src"] == "from-agents/scout/2026-10-27-report.md"
    assert folders[note["folder"]]["name"] == "SCOUT" and folders[note["folder"]]["project"] == INBOX_ID
    assert INBOX_ID in projects and len([n for n in notes.values() if n.get("src")]) == 1


def test_long_agent_note_is_kept_whole(make, tmp_path):
    drop = tmp_path / "agents"
    (drop / "scout").mkdir(parents=True)
    lines = [f"line {i:03d} " + "x" * 40 for i in range(120)]  # ~6 000 characters
    (drop / "scout" / "long.md").write_text("# Long report\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    s = make(agents_dir=drop)
    admin = s.login()
    notes = _wait_for(s, admin, lambda b: any(n.get("src") for n in b[2].values()))[2]
    body = next(n for n in notes.values() if n.get("src"))["body"]
    assert len(body) == 4000 and "line 079" in body  # 50 characters a line; was cut at 700 (line 013) before 1.3.1


def test_agent_note_is_imported_once(make, tmp_path):
    drop = tmp_path / "agents"
    (drop / "bot").mkdir(parents=True)
    (drop / "bot" / "a.md").write_text("# A", encoding="utf-8")
    s = make(agents_dir=drop)
    admin = s.login()
    _wait_for(s, admin, lambda b: len(b[2]) == 1)
    s.app.last_import = 0
    assert len(s.board(admin)[2]) == 1


@pytest.mark.skipif(os.name == "nt", reason="symlinks need extra rights on Windows")
def test_symlink_is_not_followed(make, tmp_path):
    secret = tmp_path / "secret.md"
    secret.write_text("# secret", encoding="utf-8")
    drop = tmp_path / "agents"
    (drop / "bot").mkdir(parents=True)
    (drop / "bot" / "link.md").symlink_to(secret)
    s = make(agents_dir=drop)
    admin = s.login()
    s.app.last_import = 0
    assert not s.board(admin)[2]
