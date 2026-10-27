# tiroir

**A filing cabinet for your sticky notes, on your own server. Your AI agents can drop notes in it too.**

One drawer per project, tabs inside each drawer, a free-form wall of sticky notes behind each tab.
A small Python package with no dependency and no database: it installs in ten seconds and keeps everything in a single JSON file you own.

![Tiroir: open a drawer, pick a tab, work on the wall](docs/demo.gif)

[Version française](README.fr.md)

## Why

Trello is heavy, Keep is flat, and most "AI agent boards" want an account and an API key.
Tiroir is a quiet place for your own projects, built around a physical metaphor (cabinet → drawer → tab → wall),
and any script or agent can add a note by writing a Markdown file in a folder. No SDK, no token.

## Features

- **Cabinets**: as many as you like, each with its name on a plate; slide from one to the next with the arrows, the keyboard or a swipe.
- **The cabinet**: one drawer per project, with animated opening and closing. Drag drawers to reorder them, drop one on the archive box (left) or the bin (right).
- **Tabs and wall**: sticky notes you place freely, zoom and pan, a mini-map, four states (to do, doing, info, done), search and filters, keyboard shortcuts (`N` new note, `F` fit all, `/` search).
- **Agent inbox**: every `<agents_dir>/<agent>/<note>.md` becomes a note in the *inbox* drawer, under a tab named after the agent. Read-only, symlinks refused, size capped.
- **Sharing**: invitation links, read-only or edit, for every tab or a chosen few, revocable at once. Only the admin deletes.
- **Trash for 30 days** for notes, tabs and whole drawers, with undo.
- **Your data stays safe**: atomic writes with `fsync`, three rotating backups, and a damaged file is never mistaken for an empty board.
- Light and dark themes, English and French interface, works on a phone.

## Install

Python 3.10 or newer.

```bash
pipx install git+https://github.com/kerneldottoday/tiroir   # or: pip install git+https://...
tiroir set-password      # 14 characters or more; only a scrypt hash is stored
tiroir                   # http://127.0.0.1:5950
```

### Docker

```bash
docker build -t tiroir .
docker run -d --name tiroir -p 127.0.0.1:5950:5950 -v tiroir-data:/data tiroir
docker exec -it tiroir tiroir set-password
```

`docker-compose.yml` shows a full setup behind [Caddy](https://caddyserver.com) with automatic HTTPS.

## Settings

All optional, through environment variables.

| Variable | Default | What it does |
|---|---|---|
| `TIROIR_DATA_DIR` | `~/.local/share/tiroir` | Where `notes.json`, the password hash and the sessions live |
| `TIROIR_HOST` / `TIROIR_PORT` | `127.0.0.1` / `5950` | Address to listen on |
| `TIROIR_AGENTS_DIR` | *(off)* | Drop folder for agent notes |
| `TIROIR_TRUST_PROXY` | `0` | Believe the proxy headers (client address, `https`) of a reverse proxy: `1` for one on the same machine, or its networks, e.g. `172.16.0.0/12` for a Docker network |
| `TIROIR_COOKIE_SECURE` | `auto` | `auto`: Secure cookie on https and localhost, plain on a home network over http. `always` / `never` to force |
| `TIROIR_LANG` | `en` | Names of the drawers the server creates (`en` or `fr`). The interface follows the browser |
| `TIROIR_PASSWORD` | | Used once at first start if no password is stored (handy with Docker), then ignored |

## Command line

```text
tiroir [serve] [--host H] [--port P]   start the server
tiroir set-password [--stdin]          set or change the password (logs out every admin device)
tiroir logout-all                      end every session, admin and guests
tiroir export [-o board.json]          the whole board as JSON
tiroir --data DIR ...                  use another data folder
```

## For agents

Write a Markdown file, that's all:

```bash
mkdir -p "$TIROIR_AGENTS_DIR/research-bot"
cat > "$TIROIR_AGENTS_DIR/research-bot/2026-10-27-oak-prices.md" <<'EOF'
# Oak worktop prices
Four suppliers found, cheapest 410 € for 3 m.
EOF
```

Within ten seconds the note appears in the *inbox* drawer, tab `RESEARCH-BOT`. The first heading is the title,
the rest is the body (700 characters kept). Each file is imported once. Agent text is shown as plain text and never executed.

## Expose it

Tiroir listens on `127.0.0.1` by default. To reach it from your phone, put it behind a reverse proxy with HTTPS
(Caddy, nginx, Traefik) or a tunnel (Cloudflare Tunnel, Tailscale), and tell Tiroir where that proxy is with `TIROIR_TRUST_PROXY`.

## Security

Password stored as a scrypt hash, HttpOnly + SameSite=Strict session cookie, CSRF guard, five attempts per address
every fifteen minutes, strict Content-Security-Policy, no third-party request, no log of URLs or addresses.
Changing the password logs out every admin device. See [SECURITY.md](SECURITY.md) to report a flaw.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]" pytest-cov
pytest --cov=tiroir
ruff check src tests
python demo/make_seed.py # fictional board for screenshots
```

## License

[AGPL-3.0-or-later](LICENSE). You can use, change and self-host it freely; if you offer a modified version as a service, share your changes.
