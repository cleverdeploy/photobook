# Photobook

A self-hosted, AI-themed shared photo album app, live at
**https://photobook.wasim.dev**.

- **Owner-only login** to create albums (give each a title).
- Each album gets an **AI-generated visual theme** from its title (gardening →
  earthy greens + 🪴🌱🌻; beach → sandy blues + 🏖️🌊; etc.) via the Claude API.
- **Drop photos in** as a group or a `.zip`. HEIC/iPhone photos and EXIF
  orientation are handled.
- Get a **share link** to paste into WhatsApp — it renders a nice preview card.
- **Anyone with the link can add their own photos** — no account needed.

## Stack

FastAPI + SQLite + Pillow (HEIC via `pillow-heif`), server-rendered Jinja
templates, no Node build step. Themed pages are pure CSS driven by the per-album
theme JSON. Claude `claude-opus-4-8` generates themes (`messages.parse` with a
strict Pydantic schema, prompt caching, and a deterministic fallback).

## Run locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit values
set -a; . ./.env; set +a
uvicorn app.main:app --reload --port 8080
# → http://localhost:8080  (log in with OWNER_PASSWORD)
```

Without an `ANTHROPIC_API_KEY` the app still works — it uses a deterministic
fallback palette instead of an AI theme.

## Persistence

Everything that must survive a restart/redeploy lives under `DATA_DIR`
(`/data` in Docker): the SQLite DB and all photos. On Dokploy this is a named
volume mounted at `/data`.

## Deploy

GitHub repo `cleverdeploy/photobook` → Dokploy builds the `Dockerfile` and
serves it on port 8080 behind Traefik + Let's Encrypt. DNS for
`photobook.wasim.dev` is an A record to the Hetzner VM (Cloudflare, DNS-only).
See `deploy.py` for the idempotent Playwright deploy script. Required env vars
in Dokploy: `OWNER_PASSWORD`, `SECRET_KEY`, `BASE_URL=https://photobook.wasim.dev`,
`ANTHROPIC_API_KEY`.
