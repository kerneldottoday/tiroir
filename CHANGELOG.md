# Changelog

## 1.1.0 (2026-10-27)

- Several cabinets, each with a name engraved on a plate above it. Arrows ‹ › around the name, keyboard arrows,
  a swipe on phones or the dots below switch cabinets with a sliding animation.
- Double-click the name to rename a cabinet, « + » after the last one to add one, « remove this cabinet » when it is empty.
- Drop a drawer on an arrow to move it to the neighbouring cabinet.
- Existing drawers go to a first cabinet (« main », or « principal » with `TIROIR_LANG=fr`). The agents' inbox shows in every cabinet.
- API: `/api/cabinets/<id>` (admin), `cabinet` field on drawers. A cabinet can be deleted only when empty, never the last one.

## 1.0.0 (2026-10-27)

First public version.

- The cabinet: one drawer per project, animated, drag to reorder, archive box and bin next to it, archive shelf.
- Tabs in perspective, free-form wall of sticky notes, mini-map, search, filters, shortcuts.
- Agent drop folder (`TIROIR_AGENTS_DIR`) feeding the *inbox* drawer.
- Invitation links (read or edit, scoped), 30-day trash with undo, misc drawer for tabs that lost their drawer.
- Safe storage: atomic and durable writes, three rotating backups, recovery of a damaged file.
- `tiroir` command: `serve`, `set-password` (logs out every admin device), `logout-all`, `export`.
- Settings through `TIROIR_*` variables, Docker image, English and French interface.
