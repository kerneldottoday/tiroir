"""The board as plain data: validation, drawers (projects), tabs (folders), notes, trash and migrations.

Everything here works on the dict read from notes.json and has no I/O, so it is easy to test.
Vocabulary: a project is a drawer of the cabinet, a folder is a tab inside a drawer, a note is a sticky note on a wall.
"""
from __future__ import annotations

import hashlib
import re
import time

TRASH_DAYS = 30
MAX_NOTES = 2000
MAX_AGENT_NOTES = 500
MAX_FOLDERS = 200
MAX_PROJECTS = 100
INBOX_ID = "parrivees"  # drawer of agent notes (historical id, kept for existing data)
ORPHAN_ID = "pdivers"   # drawer that collects tabs whose drawer no longer exists
STATUSES = ("todo", "doing", "info", "done")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

NAMES = {
    "en": {"inbox": "inbox", "orphans": "misc", "tabs": ("general", "docs", "ideas")},
    "fr": {"inbox": "arrivées", "orphans": "divers", "tabs": ("général", "docs", "idées")},
}


def now_ms() -> int:
    return int(time.time() * 1000)


def to_int(v, lo: int, hi: int, default: int = 0) -> int:
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return default


def _id_or_keep(value, current: str) -> str:
    v = str(value or "")
    return v if v == "" or ID_RE.match(v) else current


# ---------- validation (client data is never trusted) ----------
def clean_note(d: dict, base: dict | None = None) -> dict:
    """Validate a note body; `base` = existing note for a partial update."""
    out = dict(base or {"title": "", "body": "", "status": "info", "tag": "", "x": 0, "y": 0, "z": 1, "n": 0,
                        "createdAt": now_ms(), "updatedAt": now_ms(), "src": ""})
    if "title" in d:
        out["title"] = str(d["title"])[:90]
    if "body" in d:
        out["body"] = str(d["body"])[:4000]
    if "tag" in d:
        out["tag"] = str(d["tag"])[:24]
    if "status" in d and d["status"] in STATUSES:
        out["status"] = d["status"]
    for k, lo, hi in (("x", -1_000_000, 1_000_000), ("y", -1_000_000, 1_000_000), ("z", 0, 10**9), ("n", 0, 10**6)):
        if k in d:
            out[k] = to_int(d[k], lo, hi, out.get(k, 0))
    if "updatedAt" in d:
        out["updatedAt"] = to_int(d["updatedAt"], 0, 10**14, out["updatedAt"])
    if "createdAt" in d and not (base or {}).get("createdAt"):
        out["createdAt"] = to_int(d["createdAt"], 0, 10**14, out["createdAt"])
    if "folder" in d:
        out["folder"] = _id_or_keep(d["folder"], out.get("folder", ""))
    out.setdefault("folder", "")
    return out


def clean_folder(d: dict, base: dict | None = None) -> dict | None:
    """Validate a tab (name required, 40 chars); None if the name is empty."""
    out = dict(base or {"name": "", "order": 0, "createdAt": now_ms()})
    if "name" in d:
        out["name"] = " ".join(str(d["name"]).split())[:40]
    if "order" in d:
        out["order"] = to_int(d["order"], 0, 10**6, out.get("order", 0))
    if "archived" in d:
        out["archived"] = d["archived"] is True
    if "project" in d:
        out["project"] = _id_or_keep(d["project"], out.get("project", ""))
    return out if out["name"] else None


def clean_project(d: dict, base: dict | None = None) -> dict | None:
    """Validate a drawer: same rules as a tab, without a parent."""
    out = clean_folder({k: v for k, v in d.items() if k != "project"}, base)
    return {k: v for k, v in out.items() if k != "project"} if out else None


# ---------- special drawers ----------
def ensure_inbox(d: dict, names: dict) -> None:
    p = d["projects"].get(INBOX_ID)
    if p is None:
        d["projects"][INBOX_ID] = {"name": names["inbox"], "order": 10**5, "createdAt": now_ms()}
    elif p.get("deletedAt"):
        d["projects"][INBOX_ID] = {k: v for k, v in p.items() if k != "deletedAt"}


def adopt_orphans(d: dict, names: dict) -> bool:
    """A live tab whose drawer no longer exists moves to the « misc » drawer, a real drawer that can be
    renamed, archived or thrown away. True if anything moved."""
    def live(pid: str) -> bool:
        return pid in d["projects"] and not d["projects"][pid].get("deletedAt")
    orphans = [fid for fid, f in d["folders"].items() if not f.get("deletedAt") and not live(f.get("project", ""))]
    if not orphans:
        return False
    p = d["projects"].get(ORPHAN_ID)
    if p is None:
        last = max((v.get("order", 0) for k, v in d["projects"].items() if k != INBOX_ID), default=-1)
        d["projects"][ORPHAN_ID] = {"name": names["orphans"], "order": last + 1, "createdAt": now_ms()}
    elif p.get("deletedAt"):
        d["projects"][ORPHAN_ID] = {k: v for k, v in p.items() if k != "deletedAt"}
    for fid in orphans:
        d["folders"][fid] = {**d["folders"][fid], "project": ORPHAN_ID}
    return True


def folder_for_tag(d: dict, tag: str, names: dict) -> str:
    """Id of the agent tab with this name in the inbox drawer; created if missing ("" if trashed or full)."""
    if not tag:
        return ""
    ensure_inbox(d, names)
    for fid, f in d["folders"].items():
        if f.get("project", INBOX_ID) == INBOX_ID and f.get("name", "").upper() == tag.upper():
            return "" if f.get("deletedAt") else fid
    if len(d["folders"]) >= MAX_FOLDERS:
        return ""
    fid = "f" + hashlib.sha1(tag.upper().encode()).hexdigest()[:12]
    d["folders"][fid] = {"name": tag[:40], "order": len(d["folders"]), "createdAt": now_ms(), "project": INBOX_ID}
    return fid


def purge_trash(d: dict) -> None:
    """Delete for good what stayed more than TRASH_DAYS days in the trash."""
    limit = (time.time() - TRASH_DAYS * 86400) * 1000
    for kind in ("notes", "folders", "projects"):
        for k in [k for k, v in d[kind].items() if v.get("deletedAt") and v["deletedAt"] < limit]:
            del d[kind][k]


# ---------- one-time migrations of older files ----------
def migrate_folders(d: dict, names: dict) -> None:
    """Oldest format: each note tag becomes a folder."""
    for nid in sorted(d["notes"], key=lambda k: d["notes"][k].get("n", 0)):
        note = d["notes"][nid]
        d["notes"][nid] = {**note, "folder": folder_for_tag(d, note.get("tag", ""), names)}


def migrate_projects(d: dict, names: dict) -> None:
    """Cabinet format: each folder becomes a drawer whose first tab keeps its notes, with the default tabs next to it;
    folders of agents go to the inbox drawer."""
    agents = {k.split("/")[1].upper() for k in d["imported"] if k.count("/") >= 2}
    tabs = names["tabs"]
    for fid, f in sorted(d["folders"].items(), key=lambda kv: kv[1].get("order", 0)):
        if f.get("deletedAt"):
            d["folders"][fid] = {**f, "project": ""}
        elif f.get("name", "").upper() in agents:
            ensure_inbox(d, names)
            d["folders"][fid] = {**f, "project": INBOX_ID}
        else:
            pid = "p" + fid[1:]
            d["projects"][pid] = {"name": f["name"], "order": f.get("order", 0), "createdAt": f.get("createdAt", now_ms())}
            if f.get("archived"):
                d["projects"][pid]["archived"] = True
            d["folders"][fid] = {**{k: v for k, v in f.items() if k != "archived"}, "name": tabs[0], "order": 0, "project": pid}
            for i, name in enumerate(tabs[1:], start=1):
                d["folders"][f"{fid}{i}"[:40]] = {"name": name, "order": i, "createdAt": now_ms(), "project": pid}
    ensure_inbox(d, names)


# ---------- changes requested through the API: None = done, otherwise (HTTP code, error) ----------

def mutate_note(d: dict, method: str, nid: str, data: dict, purge: bool = False):
    """DELETE = to the trash; DELETE ?purge=1 = for good (already trashed); PATCH {"restore": true} = back from the trash.
    Permissions are checked before (access.can_write)."""
    human = sum(1 for n in d["notes"].values() if not n.get("src"))
    note = d["notes"].get(nid)
    if method == "DELETE":
        if note is None:
            return None
        if purge:
            if not note.get("deletedAt"):
                return 409, {"error": "not in the trash"}
            del d["notes"][nid]
        else:
            d["notes"][nid] = {**note, "deletedAt": now_ms()}
    elif method == "PATCH" and data.get("restore") is True and note is not None:
        d["notes"][nid] = {k: v for k, v in note.items() if k not in ("deletedAt", "trashedWith")}
    elif method == "PUT":
        if note is None and human >= MAX_NOTES - MAX_AGENT_NOTES:
            return 507, {"error": "too many notes"}
        d["notes"][nid] = clean_note(data, note)
    else:
        if note is None:
            return 404, {"error": "missing"}
        d["notes"][nid] = clean_note(data, note)
    return None


def mutate_folder(d: dict, method: str, fid: str, data: dict, purge: bool = False):
    """DELETE = tab AND its notes to the trash (restored together); ?purge=1 = for good;
    PATCH {"restore": true} = back from the trash; {"archived": bool} = archives."""
    f = d["folders"].get(fid)
    if method == "DELETE":
        if f is None:
            return None
        if purge:
            if not f.get("deletedAt"):
                return 409, {"error": "not in the trash"}
            del d["folders"][fid]
            for nid in [k for k, v in d["notes"].items() if v.get("trashedWith") == fid]:
                del d["notes"][nid]
            return None
        now = now_ms()
        d["folders"][fid] = {**f, "deletedAt": now}
        for nid, n in d["notes"].items():
            if n.get("folder") == fid and not n.get("deletedAt"):
                d["notes"][nid] = {**n, "deletedAt": now, "trashedWith": fid}
        return None
    if method == "PATCH" and f is None:
        return 404, {"error": "missing"}
    if method == "PATCH" and data.get("restore") is True:
        d["folders"][fid] = {k: v for k, v in f.items() if k not in ("deletedAt", "trashedWith")}
        p = d["projects"].get(f.get("project", ""))
        if p and p.get("deletedAt"):  # its drawer was in the trash: it comes back too (empty of the rest)
            d["projects"][f["project"]] = {k: v for k, v in p.items() if k != "deletedAt"}
        for nid, n in d["notes"].items():
            if n.get("trashedWith") == fid:
                d["notes"][nid] = {k: v for k, v in n.items() if k not in ("deletedAt", "trashedWith")}
        return None
    if method == "PUT" and f is None and len(d["folders"]) >= MAX_FOLDERS:
        return 507, {"error": "too many tabs"}
    nf = clean_folder(data, f)
    if nf is None:
        return 400, {"error": "name"}
    d["folders"][fid] = nf
    return None


def mutate_project(d: dict, method: str, pid: str, data: dict, purge: bool = False):
    """A drawer. DELETE = it, its tabs and their notes to the trash at once (restored together);
    ?purge=1 = for good (already trashed); PATCH {"restore": true} = everything comes back.
    The inbox drawer of the agents can be neither deleted nor archived."""
    p = d["projects"].get(pid)
    if method == "DELETE":
        if p is None:
            return None
        if pid == INBOX_ID:
            return 409, {"error": "agents drawer"}
        return _purge_project(d, pid) if purge else _trash_project(d, pid, p)
    if method == "PATCH" and p is None:
        return 404, {"error": "missing"}
    if method == "PATCH" and data.get("restore") is True:
        d["projects"][pid] = {k: v for k, v in p.items() if k != "deletedAt"}
        back = {k for k, f in d["folders"].items() if f.get("trashedWith") == pid}
        for fid in back:
            d["folders"][fid] = {k: v for k, v in d["folders"][fid].items() if k not in ("deletedAt", "trashedWith")}
        for nid, n in d["notes"].items():
            if n.get("trashedWith") in back:
                d["notes"][nid] = {k: v for k, v in n.items() if k not in ("deletedAt", "trashedWith")}
        return None
    if method == "PUT" and p is None and len(d["projects"]) >= MAX_PROJECTS:
        return 507, {"error": "too many drawers"}
    if pid == INBOX_ID and data.get("archived") is True:
        return 409, {"error": "agents drawer"}
    np = clean_project(data, p)
    if np is None:
        return 400, {"error": "name"}
    d["projects"][pid] = np
    return None


def _trash_project(d: dict, pid: str, p: dict):
    now = now_ms()
    d["projects"][pid] = {**p, "deletedAt": now}
    for fid, f in list(d["folders"].items()):
        if f.get("project") == pid and not f.get("deletedAt"):
            d["folders"][fid] = {**f, "deletedAt": now, "trashedWith": pid}
            for nid, n in d["notes"].items():
                if n.get("folder") == fid and not n.get("deletedAt"):
                    d["notes"][nid] = {**n, "deletedAt": now, "trashedWith": fid}
    return None


def _purge_project(d: dict, pid: str):
    if not d["projects"][pid].get("deletedAt"):
        return 409, {"error": "not in the trash"}
    gone = {k for k, f in d["folders"].items() if f.get("project") == pid and f.get("deletedAt")}
    for k in gone:
        del d["folders"][k]
    for nid in [k for k, n in d["notes"].items() if n.get("trashedWith") in gone]:
        del d["notes"][nid]
    del d["projects"][pid]
    return None
