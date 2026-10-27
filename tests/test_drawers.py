"""Drawers (projects): migration of older files, API, trash, archives, the inbox and the misc drawer."""
from tiroir.model import INBOX_ID, ORPHAN_ID

LEGACY = {  # a file from before drawers: folders only, two of them filled by agents
    "notes": {
        "n1": {"title": "plan", "folder": "fwork", "status": "todo"},
        "n2": {"title": "agent report", "folder": "fbot", "status": "info", "src": "from-agents/bot/r.md"},
    },
    "folders": {"fwork": {"name": "Work", "order": 0}, "fbot": {"name": "BOT", "order": 1}, "fold": {"name": "old", "deletedAt": 1}},
    "imported": {"from-agents/bot/r.md": "n2"},
}


def test_migration_keeps_every_note(make):
    s = make(notes=LEGACY)
    admin = s.login()
    projects, folders, notes = s.board(admin)
    assert set(notes) == {"n1", "n2"}
    assert INBOX_ID in projects and projects[INBOX_ID]["name"] == "inbox"
    assert folders["fbot"]["project"] == INBOX_ID
    work = projects["pwork"]
    assert work["name"] == "Work"
    tabs = sorted(f["name"] for f in folders.values() if f.get("project") == "pwork")
    assert tabs == ["docs", "general", "ideas"]
    assert notes["n1"]["folder"] == "fwork" and folders["fwork"]["name"] == "general"
    live = [f for f in folders.values() if not f.get("deletedAt")]
    assert all(f.get("project") in projects for f in live)


def test_french_names(make):
    s = make(notes=LEGACY, lang="fr")
    projects, folders, _n = s.board(s.login())
    assert projects[INBOX_ID]["name"] == "arrivées"
    assert sorted(f["name"] for f in folders.values() if f.get("project") == "pwork") == ["docs", "général", "idées"]


def test_drawer_api(server):
    admin = server.login()
    assert server.call("PUT", "/api/projects/pt", admin, {"name": "  Test   drawer ", "order": 5}).code == 200
    assert server.call("PUT", "/api/folders/ft", admin, {"name": "docs", "project": "pt"}).code == 200
    projects, folders, _n = server.board(admin)
    assert projects["pt"]["name"] == "Test drawer" and folders["ft"]["project"] == "pt"
    assert server.call("PATCH", "/api/folders/ft", admin, {"project": "../../x"}).code == 200
    assert server.board(admin)[1]["ft"]["project"] == "pt"
    assert server.call("PUT", "/api/projects/pt", admin, {"name": "   "}).code == 400
    assert server.call("PUT", "/api/projects/px", "", {"name": "x"}).code == 401


def test_whole_drawer_to_trash_and_back(server):
    admin = server.login()
    server.call("PUT", "/api/projects/pt", admin, {"name": "T"})
    server.call("PUT", "/api/folders/ft", admin, {"name": "docs", "project": "pt"})
    server.call("PUT", "/api/notes/nt", admin, {"title": "inside", "folder": "ft"})
    assert server.call("DELETE", "/api/projects/pt", admin).code == 200
    projects, folders, notes = server.board(admin)
    assert projects["pt"].get("deletedAt") and folders["ft"].get("deletedAt") and notes["nt"].get("deletedAt")
    assert server.call("PATCH", "/api/projects/pt", admin, {"restore": True}).code == 200
    projects, folders, notes = server.board(admin)
    assert not (projects["pt"].get("deletedAt") or folders["ft"].get("deletedAt") or notes["nt"].get("deletedAt"))
    # restoring a single tab of a trashed drawer brings the drawer back
    server.call("DELETE", "/api/projects/pt", admin)
    server.call("PATCH", "/api/folders/ft", admin, {"restore": True})
    assert not server.board(admin)[0]["pt"].get("deletedAt")
    assert server.call("DELETE", "/api/projects/pt?purge=1", admin).code == 409
    server.call("DELETE", "/api/projects/pt", admin)
    assert server.call("DELETE", "/api/projects/pt?purge=1", admin).code == 200
    projects, folders, notes = server.board(admin)
    assert "pt" not in projects and "ft" not in folders and "nt" not in notes


def test_archive_drawer_but_never_the_inbox(make):
    s = make(notes=LEGACY)
    admin = s.login()
    assert s.call("PATCH", "/api/projects/pwork", admin, {"archived": True}).code == 200
    assert s.board(admin)[0]["pwork"]["archived"] is True
    assert s.call("PATCH", f"/api/projects/{INBOX_ID}", admin, {"archived": True}).code == 409
    assert s.call("DELETE", f"/api/projects/{INBOX_ID}", admin).code == 409


def test_orphan_tabs_go_to_misc(server):
    admin = server.login()
    server.call("PUT", "/api/folders/forph", admin, {"name": "lost", "project": "pmissing"})
    projects, folders, _n = server.board(admin)
    assert folders["forph"]["project"] == ORPHAN_ID and projects[ORPHAN_ID]["name"] == "misc"
    assert server.call("DELETE", f"/api/projects/{ORPHAN_ID}", admin).code == 200
    assert server.board(admin)[1]["forph"].get("deletedAt")


def test_orphans_from_an_old_file_are_adopted_at_start(make):
    s = make(notes={"notes": {}, "folders": {"fz": {"name": "z", "project": "pgone"}}, "projects": {}, "imported": {}})
    _p, folders, _n = s.board(s.login())
    assert folders["fz"]["project"] == ORPHAN_ID
