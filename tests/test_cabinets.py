"""Cabinets: several cabinets of drawers, each with a name."""
from test_drawers import LEGACY

from tiroir.model import INBOX_ID, MAIN_CABINET


def test_existing_drawers_go_to_the_main_cabinet(make):
    s = make(notes=LEGACY, lang="fr")
    admin = s.login()
    js = s.call("GET", "/api/notes", admin).json
    cabinets = {c["id"]: c for c in js["cabinets"]}
    assert cabinets == {MAIN_CABINET: {**cabinets[MAIN_CABINET], "name": "principal"}}
    drawers = {p["id"]: p for p in js["projects"]}
    assert drawers["pwork"]["cabinet"] == MAIN_CABINET
    assert "cabinet" not in drawers[INBOX_ID]  # the inbox shows in every cabinet


def test_create_rename_and_move_a_drawer(make):
    s = make(notes=LEGACY)
    admin = s.login()
    assert s.call("PUT", "/api/cabinets/cpro", admin, {"name": "  work   stuff ", "order": 1}).code == 200
    assert s.call("PATCH", "/api/cabinets/cpro", admin, {"name": "pro"}).code == 200
    assert s.call("PATCH", "/api/projects/pwork", admin, {"cabinet": "cpro"}).code == 200
    js = s.call("GET", "/api/notes", admin).json
    assert {c["id"]: c["name"] for c in js["cabinets"]} == {MAIN_CABINET: "main", "cpro": "pro"}
    assert next(p for p in js["projects"] if p["id"] == "pwork")["cabinet"] == "cpro"
    assert s.call("PUT", "/api/cabinets/cx", admin, {"name": "   "}).code == 400


def test_a_drawer_in_an_unknown_cabinet_goes_to_the_first_one(server):
    admin = server.login()
    server.call("PUT", "/api/projects/pz", admin, {"name": "z", "cabinet": "cnowhere"})
    js = server.call("GET", "/api/notes", admin).json
    assert next(p for p in js["projects"] if p["id"] == "pz")["cabinet"] == MAIN_CABINET


def test_only_an_empty_cabinet_can_go_and_never_the_last(make):
    s = make(notes=LEGACY)
    admin = s.login()
    assert s.call("DELETE", f"/api/cabinets/{MAIN_CABINET}", admin).code == 409  # the last one
    s.call("PUT", "/api/cabinets/cpro", admin, {"name": "pro"})
    s.call("PATCH", "/api/projects/pwork", admin, {"cabinet": "cpro"})
    assert s.call("DELETE", "/api/cabinets/cpro", admin).code == 409  # not empty
    s.call("PATCH", "/api/projects/pwork", admin, {"cabinet": MAIN_CABINET})
    assert s.call("DELETE", "/api/cabinets/cpro", admin).code == 200
    assert [c["id"] for c in s.call("GET", "/api/notes", admin).json["cabinets"]] == [MAIN_CABINET]


def test_trashed_drawers_do_not_keep_a_cabinet_busy(make):
    s = make(notes=LEGACY)
    admin = s.login()
    s.call("PUT", "/api/cabinets/cpro", admin, {"name": "pro"})
    s.call("PATCH", "/api/projects/pwork", admin, {"cabinet": "cpro"})
    s.call("DELETE", "/api/projects/pwork", admin)
    assert s.call("DELETE", "/api/cabinets/cpro", admin).code == 200
    s.call("PATCH", "/api/projects/pwork", admin, {"restore": True})  # back from the trash: lands in the first cabinet
    js = s.call("GET", "/api/notes", admin).json
    assert next(p for p in js["projects"] if p["id"] == "pwork")["cabinet"] == MAIN_CABINET


def test_guests_see_only_cabinets_holding_their_tabs(make):
    s = make(notes=LEGACY)
    admin = s.login()
    s.call("PUT", "/api/cabinets/cpro", admin, {"name": "pro"})
    inv = s.call("PUT", "/api/invites/g1", admin, {"label": "Guest", "role": "view", "folders": ["fwork"]}).json
    guest = s.call("GET", "/i/" + inv["token"]).cookie
    assert [c["id"] for c in s.call("GET", "/api/notes", guest).json["cabinets"]] == [MAIN_CABINET]
    assert s.call("PUT", "/api/cabinets/cg", guest, {"name": "x"}).code == 403
