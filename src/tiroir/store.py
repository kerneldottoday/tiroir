"""notes.json on disk: atomic and durable writes, rotating backups, and recovery.

An unreadable file is NEVER treated as an empty board (the next write would erase everything):
it is set aside, the newest valid backup is restored, and without one every read and write is refused.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

BACKUPS = 3


class StoreError(Exception):
    """notes.json is unreadable and no valid backup exists: reads and writes are refused."""


def write_file(path: Path, text: str) -> None:
    """Atomic AND durable: temp file, fsync, rename, fsync of the directory (survives a power cut)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    if hasattr(os, "O_DIRECTORY"):  # POSIX only
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def parse_store(p: Path) -> dict | None:
    """Content of a valid file, None if unreadable or malformed."""
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and isinstance(d.get("notes", {}), dict) else None


class NotesStore:
    """The whole board in one JSON file. Callers hold `lock` around read-modify-write."""

    def __init__(self, data_dir: Path) -> None:
        self.dir = data_dir
        self.path = data_dir / "notes.json"
        self.lock = threading.Lock()

    def backup_path(self, i: int) -> Path:
        return self.dir / f"notes.json.bak{i}"

    def exists(self) -> bool:
        return self.path.exists()

    def raw(self) -> dict | None:
        """The file as stored, without defaults (used by one-time migrations)."""
        return parse_store(self.path)

    def read(self) -> dict:
        if self.path.exists():
            d = parse_store(self.path)
            if d is None:
                d = self._recover()
        else:
            d = {}
        for key in ("notes", "imported", "folders", "projects", "cabinets"):
            d.setdefault(key, {})
        return d

    def write(self, d: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self._rotate()
        write_file(self.path, json.dumps(d, ensure_ascii=False))

    def _rotate(self) -> None:
        """Before each write: valid notes.json -> .bak1 -> .bak2 -> .bak3 (the oldest is overwritten)."""
        if parse_store(self.path) is None:
            return  # never push a damaged file into the backups
        for i in range(BACKUPS, 1, -1):
            if self.backup_path(i - 1).exists():
                os.replace(self.backup_path(i - 1), self.backup_path(i))
        write_file(self.backup_path(1), self.path.read_text(encoding="utf-8"))

    def _recover(self) -> dict:
        """Unreadable notes.json: keep a copy (notes.corrupt-<date>.json), then restore the newest valid backup."""
        keep = self.dir / f"notes.corrupt-{time.strftime('%Y%m%d-%H%M%S')}.json"
        try:
            keep.write_bytes(self.path.read_bytes())
            os.chmod(keep, 0o600)
        except OSError:
            pass
        for i in range(1, BACKUPS + 1):
            d = parse_store(self.backup_path(i))
            if d is not None:
                print(f"tiroir: notes.json unreadable, kept as {keep.name}; restored from {self.backup_path(i).name}", flush=True)
                write_file(self.path, json.dumps(d, ensure_ascii=False))
                return d
        raise StoreError("notes.json unreadable and no valid backup")
