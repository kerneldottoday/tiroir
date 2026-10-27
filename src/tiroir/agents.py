"""Agent drop folder: every new <agents_dir>/<agent>/<note>.md (or .txt) becomes a sticky note in the inbox drawer.

Agent content is untrusted data: read-only, no symlinks followed, size capped, separate quota, never executed,
and shown as plain text by the browser.
"""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from . import model

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
        title, body = _note_from_text(raw, p.stem)
        nid = "a" + hashlib.sha1(rel.encode()).hexdigest()[:12]
        n_max += 1
        note = model.clean_note({"title": title, "body": body, "status": "info", "tag": agent.upper(),
                                 "x": 1100 + (count % 3) * 270, "y": (count // 3) * 230, "z": n_max, "n": n_max,
                                 "folder": model.folder_for_tag(d, agent.upper(), names)})
        d["notes"][nid] = {**note, "src": rel}
        d["imported"][rel] = nid
        count += 1
        agent_notes += 1
        changed = True
    return changed
