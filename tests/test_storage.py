"""A damaged notes.json must NEVER erase the board."""
import json

from tiroir.store import NotesStore


def test_backups_rotate(tmp_path):
    st = NotesStore(tmp_path)
    for i in range(5):
        st.write({"notes": {f"n{i}": {"title": str(i)}}})
    assert json.loads((tmp_path / "notes.json.bak1").read_text())["notes"] == {"n3": {"title": "3"}}
    assert (tmp_path / "notes.json.bak3").exists() and not (tmp_path / "notes.json.bak4").exists()


def test_damaged_file_is_restored_from_backup(tmp_path):
    st = NotesStore(tmp_path)
    st.write({"notes": {"a": {"title": "keep me"}}})
    st.write({"notes": {"a": {"title": "keep me"}, "b": {"title": "me too"}}})
    (tmp_path / "notes.json").write_text('{"notes": {"a": tru', encoding="utf-8")  # cut in the middle of a write
    d = st.read()
    assert d["notes"] == {"a": {"title": "keep me"}}  # newest valid backup
    assert list(tmp_path.glob("notes.corrupt-*.json")), "the damaged file is kept aside"


def test_no_valid_copy_means_503_and_nothing_written(server):
    admin = server.login()
    server.call("PUT", "/api/notes/n1", admin, {"title": "x"})
    for p in server.data.glob("notes.json.bak*"):
        p.unlink()
    (server.data / "notes.json").write_text("garbage", encoding="utf-8")
    assert server.call("PUT", "/api/notes/n2", admin, {"title": "y"}).code == 503
    assert server.call("GET", "/api/notes", admin).code == 503
    assert (server.data / "notes.json").read_text(encoding="utf-8") == "garbage"
