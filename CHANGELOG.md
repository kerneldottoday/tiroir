# Changelog

## 1.0.0 (2026-10-27)

First public version.

- The cabinet: one drawer per project, animated, drag to reorder, archive box and bin next to it, archive shelf.
- Tabs in perspective, free-form wall of sticky notes, mini-map, search, filters, shortcuts.
- Agent drop folder (`TIROIR_AGENTS_DIR`) feeding the *inbox* drawer.
- Invitation links (read or edit, scoped), 30-day trash with undo, misc drawer for tabs that lost their drawer.
- Safe storage: atomic and durable writes, three rotating backups, recovery of a damaged file.
- `tiroir` command: `serve`, `set-password` (logs out every admin device), `logout-all`, `export`.
- Settings through `TIROIR_*` variables, Docker image, English and French interface.
