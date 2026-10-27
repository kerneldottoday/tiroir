"""Agent header (project, status, question), answers written back, and sharing a whole cabinet."""
from test_agents import _wait_for

from tiroir.agents import answer_path, read_header, split_header
from tiroir.model import INBOX_ID, MAIN_CABINET

QUESTION = """---
project: Work
statut: à faire
question: oui
---
# Which supplier?
Two quotes: 410 € and 455 €.
"""


def test_header_parsing():
    head, rest = split_header(QUESTION)
    assert head == {"project": "Work", "statut": "à faire", "question": "oui"} and rest.startswith("# Which")
    assert read_header(head) == {"project": "Work", "status": "todo", "ask": True}
    assert split_header("# no header")[0] == {}
    assert read_header({})["status"] == "info"


def test_answer_path_is_confined(tmp_path):
    assert answer_path(tmp_path, "from-agents/bot/q.md") == (tmp_path / "answers" / "bot" / "q.md").resolve()
    for bad in ("from-agents/../x.md", "from-agents/bot/../../x", "elsewhere/bot/q.md", "from-agents/bot/.hidden", "from-agents/../..",
                "from-agents/bot/a..b"):
        assert answer_path(tmp_path, bad) is None


def test_question_goes_to_its_drawer_and_the_answer_comes_back(make, tmp_path):
    drop = tmp_path / "agents"
    (drop / "scout").mkdir(parents=True)
    s = make(agents_dir=drop)
    admin = s.login()
    s.call("PUT", "/api/projects/pw", admin, {"name": "Work"})
    s.call("PUT", "/api/folders/fw", admin, {"name": "general", "project": "pw", "order": 0})
    (drop / "scout" / "supplier.md").write_text(QUESTION, encoding="utf-8")
    s.app.last_import = 0
    _p, folders, notes = _wait_for(s, admin, lambda b: any(n.get("src") for n in b[2].values()))
    nid, note = next((k, n) for k, n in notes.items() if n.get("src"))
    assert note["folder"] == "fw" and note["status"] == "todo" and note["ask"] is True
    assert note["title"] == "Which supplier?" and "410" in note["body"]

    assert s.call("PATCH", f"/api/notes/{nid}", admin, {"answer": "Take the 410 € one.", "status": "done"}).code == 200
    answer = s.data / "answers" / "scout" / "supplier.md"
    assert answer.read_text(encoding="utf-8") == "# Which supplier?\n\nTake the 410 € one.\n"


def test_unknown_project_falls_back_to_the_inbox(make, tmp_path):
    drop = tmp_path / "agents"
    (drop / "scout").mkdir(parents=True)
    (drop / "scout" / "x.md").write_text("---\nproject: nowhere\n---\n# X\n", encoding="utf-8")
    s = make(agents_dir=drop)
    admin = s.login()
    _p, folders, notes = _wait_for(s, admin, lambda b: any(n.get("src") for n in b[2].values()))
    note = next(n for n in notes.values() if n.get("src"))
    assert folders[note["folder"]]["project"] == INBOX_ID and not note.get("ask")


def test_a_person_cannot_turn_a_note_into_an_agent_question(server):
    admin = server.login()
    server.call("PUT", "/api/notes/n1", admin, {"title": "x", "ask": True, "answer": "y"})
    assert not server.board(admin)[2]["n1"].get("ask")
    assert not (server.data / "answers").exists()


def test_share_a_whole_cabinet_including_later_drawers(server):
    admin = server.login()
    server.call("PUT", "/api/projects/pa", admin, {"name": "A"})
    server.call("PUT", "/api/folders/fa", admin, {"name": "general", "project": "pa"})
    server.call("PUT", "/api/cabinets/cpro", admin, {"name": "pro", "order": 1})
    server.call("PUT", "/api/projects/pb", admin, {"name": "B", "cabinet": "cpro"})
    server.call("PUT", "/api/folders/fb", admin, {"name": "general", "project": "pb"})
    server.call("PUT", "/api/notes/nb", admin, {"title": "in pro", "folder": "fb"})
    server.call("PUT", "/api/notes/na", admin, {"title": "in main", "folder": "fa"})
    inv = server.call("PUT", "/api/invites/g1", admin, {"label": "Guest", "role": "edit", "cabinets": ["cpro"]}).json
    assert inv["cabinets"] == ["cpro"] and inv["folders"] is None
    guest = server.call("GET", "/i/" + inv["token"]).cookie
    js = server.call("GET", "/api/notes", guest).json
    assert {n["id"] for n in js["notes"]} == {"nb"} and [c["id"] for c in js["cabinets"]] == ["cpro"]
    assert server.call("GET", "/api/me", guest).json["cabinets"] == ["cpro"]
    # a drawer added later to the shared cabinet is visible, one in another cabinet is not
    server.call("PUT", "/api/projects/pc", admin, {"name": "C", "cabinet": "cpro"})
    server.call("PUT", "/api/folders/fc", admin, {"name": "general", "project": "pc"})
    assert "fc" in {f["id"] for f in server.call("GET", "/api/notes", guest).json["folders"]}
    assert server.call("PUT", "/api/notes/g-new", guest, {"title": "by guest", "folder": "fc"}).code == 200
    assert server.call("PUT", "/api/notes/g-bad", guest, {"title": "x", "folder": "fa"}).code == 403
    # moving a drawer out of the shared cabinet takes it out of the guest's sight
    server.call("PATCH", "/api/projects/pb", admin, {"cabinet": MAIN_CABINET})
    assert "nb" not in {n["id"] for n in server.call("GET", "/api/notes", guest).json["notes"]}
