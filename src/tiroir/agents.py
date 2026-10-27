"""Agent drop folder: every new <agents_dir>/<agent>/<note>.md (or .txt) becomes a sticky note.

An optional header at the top routes and qualifies the note:
    ---
    project: BUSLYTICS      (or « projet ») -> first tab of that drawer instead of the inbox
    status: todo            (todo | doing | info | done, or à faire | en cours | fait)
    question: yes           -> the note waits for your answer; the answer is written back for the agent
    ---

Agent content is untrusted data: read-only, no symlinks followed, size capped, separate quota, never executed,
and shown as plain text by the browser.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path

from . import model
from .store import write_file

MAX_AGENT_DIRS = 20
MAX_FILES_PER_DIR = 200
MAX_READ = 6000
MAX_FILE = 200_000


def read_agent_file(p: Path, root: Path) -> str | None:
    """At most MAX_READ bytes of a regular file directly inside an agent folder, without following symlinks."""
    try:
        if p.parent.is_symlink() or p.is_symlink() or p.resolve().parent.parent != root:
            return None
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(p, flags)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE:
                return None
            return os.read(fd, MAX_READ).decode("utf-8", "replace")
        finally:
            os.close(fd)
    except OSError:
        return None


STATUS_WORDS = {"todo": "todo", "à faire": "todo", "a faire": "todo", "doing": "doing", "en cours": "doing",
                "info": "info", "done": "done", "fait": "done"}
YES = ("1", "true", "yes", "oui", "y", "o")


def split_header(raw: str) -> tuple[dict, str]:
    """Optional header between two « --- » lines at the top: « key: value » lines (keys lowercased)."""
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, raw
    for i, ln in enumerate(lines[1:30], start=1):
        if ln.strip() == "---":
            head = {}
            for item in lines[1:i]:
                key, sep, val = item.partition(":")
                if sep and key.strip():
                    head[key.strip().lower()] = val.strip()[:80]
            return head, "\n".join(lines[i + 1:])
    return {}, raw


def read_header(head: dict) -> dict:
    """project / projet, status / statut, question / ask: what the agent asks for this note."""
    status = STATUS_WORDS.get((head.get("status") or head.get("statut") or "").lower(), "")
    ask = (head.get("question") or head.get("ask") or "").lower() in YES
    return {"project": head.get("project") or head.get("projet") or "", "status": status or ("todo" if ask else "info"), "ask": ask}


def drawer_tab(d: dict, project_name: str) -> str:
    """First live tab of the live drawer with this name (case ignored), or "" if there is none."""
    name = project_name.strip().lower()
    if not name:
        return ""
    pid = next((k for k, p in d["projects"].items() if not p.get("deletedAt") and p.get("name", "").lower() == name), "")
    tabs = sorted((f.get("order", 0), k) for k, f in d["folders"].items() if f.get("project") == pid and pid and not f.get("deletedAt"))
    return tabs[0][1] if tabs else ""


def _note_from_text(raw: str, stem: str) -> tuple[str, str]:
    """Title = first markdown heading (or the file name), body = the other non-empty lines."""
    lines = [ln.rstrip() for ln in raw.splitlines()]
    title = next((ln.lstrip("# ").strip() for ln in lines if ln.strip().startswith("#")), "") or stem.replace("-", " ")
    body = [ln for ln in lines if not ln.strip().startswith("#") and ln.strip() and set(ln.strip()) != {"-"}]
    return title, "\n".join(body)[:700]


def _agent_files(root: Path):
    """(agent folder, file) pairs, sorted, within the folder and file caps."""
    try:
        dirs = sorted((e for e in os.scandir(root) if e.is_dir(follow_symlinks=False)), key=lambda e: e.name)[:MAX_AGENT_DIRS]
    except OSError:
        return
    for ent in dirs:
        try:
            files = sorted((e for e in os.scandir(ent.path) if e.is_file(follow_symlinks=False)), key=lambda e: e.name)
        except OSError:
            continue
        for fe in files[:MAX_FILES_PER_DIR]:
            yield ent.name, Path(fe.path)


def import_agent_notes(d: dict, agents_dir: Path | None, names: dict) -> bool:
    """Add one note per new agent file. True if the board changed."""
    if agents_dir is None or not agents_dir.is_dir() or agents_dir.is_symlink():
        return False
    root = agents_dir.resolve()
    changed = False
    n_max = max([n.get("n", 0) for n in d["notes"].values()] or [0])
    agent_notes = sum(1 for n in d["notes"].values() if n.get("src"))
    count = len(d["imported"])
    for agent, p in _agent_files(root):
        rel = f"from-agents/{agent}/{p.name}"
        if p.suffix not in (".md", ".txt") or rel in d["imported"]:
            continue
        if agent_notes >= model.MAX_AGENT_NOTES or len(d["notes"]) >= model.MAX_NOTES:
            break
        raw = read_agent_file(p, root)
        if raw is None:
            continue
        head, text = split_header(raw)
        meta = read_header(head)
        title, body = _note_from_text(text, p.stem)
        nid = "a" + hashlib.sha1(rel.encode()).hexdigest()[:12]
        n_max += 1
        folder = drawer_tab(d, meta["project"]) or model.folder_for_tag(d, agent.upper(), names)
        note = model.clean_note({"title": title, "body": body, "status": meta["status"], "tag": agent.upper(),
                                 "x": 1100 + (count % 3) * 270, "y": (count // 3) * 230, "z": n_max, "n": n_max,
                                 "folder": folder})
        d["notes"][nid] = {**note, "src": rel, **({"ask": True} if meta["ask"] else {})}
        d["imported"][rel] = nid
        count += 1
        agent_notes += 1
        changed = True
    return changed


SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.,()+-]{0,120}$")


def answer_path(data_dir: Path, src: str) -> Path | None:
    """Where the answer to an agent question goes: <data_dir>/answers/<agent>/<same file name>.
    Agent and file names must be plain names (no « .. », no separator, no leading dot)."""
    parts = src.split("/")
    if len(parts) != 3 or parts[0] != "from-agents":
        return None
    agent, name = parts[1], parts[2]
    if not all(SAFE_NAME.match(x) and ".." not in x for x in (agent, name)):
        return None
    root = (data_dir / "answers").resolve()
    target = (root / agent / name).resolve()
    return target if target.parent.parent == root else None


def write_answer(data_dir: Path, note: dict) -> bool:
    """Write (or rewrite) the answer file of an answered agent question. True if written."""
    target = answer_path(data_dir, note.get("src", ""))
    if target is None or not note.get("ask") or not note.get("answer", "").strip():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    write_file(target, f"# {note.get('title', '')}\n\n{note['answer'].strip()}\n")
    return True
