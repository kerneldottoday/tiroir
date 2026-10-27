"""Rights, invitations, trash and archives through the HTTP API."""


def _two_tabs(server, admin):
    server.call("PUT", "/api/projects/p1", admin, {"name": "Work"})
    for fid, name in (("fa", "alpha"), ("fb", "beta")):
        assert server.call("PUT", f"/api/folders/{fid}", admin, {"name": name, "project": "p1"}).code == 200
    server.call("PUT", "/api/notes/na", admin, {"title": "in alpha", "folder": "fa"})
    server.call("PUT", "/api/notes/nb", admin, {"title": "in beta", "folder": "fb"})


def test_login_and_me(server):
    admin = server.login()
    assert server.call("GET", "/api/me", admin).json["role"] == "admin"
    assert server.call("POST", "/login", form={"password": "wrong password!!"}).code == 401
    assert server.call("GET", "/api/notes").code == 401


def test_invitations_scope_and_rights(server):
    admin = server.login()
    _two_tabs(server, admin)
    inv_v = server.call("PUT", "/api/invites/tview", admin, {"label": "Reader", "role": "view", "folders": None}).json
    inv_e = server.call("PUT", "/api/invites/tedit", admin, {"label": "Editor", "role": "edit", "folders": ["fa"]}).json
    assert inv_v.get("token") and inv_e.get("folders") == ["fa"]
    assert server.call("PUT", "/api/invites/tempty", admin, {"label": "  ", "role": "view"}).code == 400

    view = server.call("GET", "/i/" + inv_v["token"]).cookie
    edit = server.call("GET", "/i/" + inv_e["token"]).cookie
    assert view and edit
    assert server.call("GET", "/i/not-a-real-token").code == 404
    assert server.call("GET", "/api/me", view).json["role"] == "view"
    projects, folders, notes = server.board(edit)
    assert set(folders) == {"fa"} and set(notes) == {"na"} and set(projects) == {"p1"}

    assert server.call("PUT", "/api/notes/x1", view, {"title": "x", "folder": "fa"}).code == 403
    assert server.call("PUT", "/api/notes/x2", edit, {"title": "by guest", "folder": "fa"}).code == 200
    assert server.call("PUT", "/api/notes/x3", edit, {"title": "x", "folder": "fb"}).code == 403
    assert server.call("PATCH", "/api/notes/x2", edit, {"folder": "fb"}).code == 403
    assert server.call("PATCH", "/api/notes/x2", edit, {"title": "changed"}).code == 200
    assert server.call("DELETE", "/api/notes/x2", edit).code == 403
    assert server.call("PUT", "/api/folders/fx", edit, {"name": "x"}).code == 403
    assert server.call("DELETE", "/api/folders/fa", view).code == 403
    assert server.call("GET", "/api/invites", edit).code == 403

    assert server.call("DELETE", "/api/invites/tedit", admin).code == 200
    assert server.call("GET", "/api/notes", edit).code == 401
    assert server.call("GET", "/i/" + inv_e["token"]).code == 404
    server.call("DELETE", "/api/invites/tview", admin)
    assert server.call("GET", "/api/notes", view).code == 401


def test_note_trash_restore_purge(server):
    admin = server.login()
    _two_tabs(server, admin)
    assert server.call("DELETE", "/api/notes/na", admin).code == 200
    assert server.board(admin)[2]["na"].get("deletedAt")
    assert server.call("PATCH", "/api/notes/na", admin, {"restore": True}).code == 200
    assert not server.board(admin)[2]["na"].get("deletedAt")
    assert server.call("DELETE", "/api/notes/na?purge=1", admin).code == 409
    server.call("DELETE", "/api/notes/na", admin)
    assert server.call("DELETE", "/api/notes/na?purge=1", admin).code == 200
    assert "na" not in server.board(admin)[2]


def test_tab_archive_and_trash_with_its_notes(server):
    admin = server.login()
    _two_tabs(server, admin)
    assert server.call("PATCH", "/api/folders/fa", admin, {"archived": True}).code == 200
    assert server.board(admin)[1]["fa"]["archived"] is True
    assert server.call("DELETE", "/api/folders/fa", admin).code == 200
    note = server.board(admin)[2]["na"]
    assert note.get("deletedAt") and note.get("trashedWith") == "fa"
    assert server.call("PATCH", "/api/folders/fa", admin, {"restore": True}).code == 200
    assert not server.board(admin)[2]["na"].get("deletedAt")
    server.call("DELETE", "/api/folders/fa", admin)
    assert server.call("DELETE", "/api/folders/fa?purge=1", admin).code == 200
    _, folders, notes = server.board(admin)
    assert "fa" not in folders and "na" not in notes


def test_client_cannot_fake_an_agent_note(server):
    admin = server.login()
    server.call("PUT", "/api/notes/fake", admin, {"title": "x", "src": "from-agents/bot/x.md"})
    assert not server.board(admin)[2]["fake"].get("src")
