"""Runtime configuration, all driven by environment variables.

Everything that must survive a redeploy lives under DATA_DIR — both the SQLite
database and the uploaded photos. On Dokploy this directory is a persistent
volume mount; locally it defaults to ./data.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Persistence -----------------------------------------------------------
DATA_DIR = Path(os.environ.get("DATA_DIR", "./data")).resolve()
ALBUMS_DIR = DATA_DIR / "albums"
DB_PATH = DATA_DIR / "photobook.db"

# --- Auth ------------------------------------------------------------------
# The single owner's password. Anyone who knows it can create/manage albums.
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "changeme")
# Signs the session cookie. Generate a long random value in production.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-change-me")

# --- Public URL ------------------------------------------------------------
# Used to build absolute URLs for WhatsApp/OpenGraph previews. If unset we fall
# back to the request's own base URL at render time.
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")

# --- Anthropic / AI theming ------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
THEME_MODEL = os.environ.get("THEME_MODEL", "claude-opus-4-8")
# Hard cap on how long album creation will wait for the AI theme before
# falling back to a default. Keeps album creation snappy.
THEME_TIMEOUT_SECONDS = float(os.environ.get("THEME_TIMEOUT_SECONDS", "18"))

# --- Uploads ---------------------------------------------------------------
ALLOWED_IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
    ".heic", ".heif", ".tif", ".tiff",
}
# Per-file safety cap (bytes). 60 MB comfortably covers phone photos + RAW-ish.
MAX_FILE_BYTES = int(os.environ.get("MAX_FILE_BYTES", str(60 * 1024 * 1024)))
# Cap on a single uploaded zip after extraction, to guard against zip bombs.
MAX_ZIP_EXTRACTED_BYTES = int(
    os.environ.get("MAX_ZIP_EXTRACTED_BYTES", str(2 * 1024 * 1024 * 1024))
)
THUMB_MAX_EDGE = 600  # longest edge of generated thumbnails, px


def ensure_dirs() -> None:
    ALBUMS_DIR.mkdir(parents=True, exist_ok=True)
