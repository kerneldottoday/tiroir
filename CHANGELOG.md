# Changelog

## 1.2.0 (2026-10-27)

- **Agents ask, you answer.** An optional header in the agent file (`project`, `status`, `question: yes`) files the note
  in the right drawer; a question shows with a yellow ring and a ❓ on the drawer front; your answer is written to
  `<data>/answers/<agent>/<file>` for the agent to read.
- **Checkboxes and links**: lines `- [ ]` become checkboxes you tick right on the card (progress shown as 1/3), http(s) addresses become links.
  « + checkbox » in the note panel.
- **Drawer fronts** show what matters: ❓ questions waiting, new agent notes since your last visit, notes to do.
- **Search everywhere** with Ctrl+K (or « search » on the cabinet): every cabinet, every drawer, opens the note on its wall.
- **Share a whole cabinet**: the person sees its drawers, including the ones you add later, and nothing else.
- **Installable app** (manifest and icons): add Tiroir to your phone's home screen.

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
