"""Tiny SQLite data layer. WAL mode, idempotent schema, thread-safe access."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any, Optional

from . import config

_local = threading.local()


def _conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        config.ensure_dirs()
        conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        _local.conn = conn
    return conn


def init_db() -> None:
    conn = _conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS albums (
            id           TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            share_token  TEXT NOT NULL UNIQUE,
            theme        TEXT NOT NULL DEFAULT '{}',
            cover_id     TEXT,
            created_at   REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS photos (
            id            TEXT PRIMARY KEY,
            album_id      TEXT NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
            ext           TEXT NOT NULL,
            original_name TEXT,
            contributor   TEXT,
            width         INTEGER,
            height        INTEGER,
            created_at    REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_photos_album ON photos(album_id, created_at);
        CREATE TABLE IF NOT EXISTS waitlist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT NOT NULL UNIQUE,
            created_at  REAL NOT NULL
        );
        """
    )
    conn.commit()


# --- Albums ----------------------------------------------------------------

def create_album(album_id: str, title: str, share_token: str, theme: dict) -> None:
    conn = _conn()
    conn.execute(
        "INSERT INTO albums (id, title, share_token, theme, created_at) VALUES (?,?,?,?,?)",
        (album_id, title, share_token, json.dumps(theme), time.time()),
    )
    conn.commit()


def get_album(album_id: str) -> Optional[sqlite3.Row]:
    return _conn().execute("SELECT * FROM albums WHERE id=?", (album_id,)).fetchone()


def get_album_by_token(token: str) -> Optional[sqlite3.Row]:
    return _conn().execute(
        "SELECT * FROM albums WHERE share_token=?", (token,)
    ).fetchone()


def list_albums() -> list[sqlite3.Row]:
    return _conn().execute(
        "SELECT * FROM albums ORDER BY created_at DESC"
    ).fetchall()


def update_album_title(album_id: str, title: str) -> None:
    conn = _conn()
    conn.execute("UPDATE albums SET title=? WHERE id=?", (title, album_id))
    conn.commit()


def update_album_theme(album_id: str, theme: dict) -> None:
    conn = _conn()
    conn.execute(
        "UPDATE albums SET theme=? WHERE id=?", (json.dumps(theme), album_id)
    )
    conn.commit()


def set_cover(album_id: str, photo_id: Optional[str]) -> None:
    conn = _conn()
    conn.execute("UPDATE albums SET cover_id=? WHERE id=?", (photo_id, album_id))
    conn.commit()


def delete_album(album_id: str) -> None:
    conn = _conn()
    conn.execute("DELETE FROM albums WHERE id=?", (album_id,))
    conn.commit()


# --- Photos ----------------------------------------------------------------

def add_photo(
    photo_id: str,
    album_id: str,
    ext: str,
    original_name: str,
    contributor: Optional[str],
    width: Optional[int],
    height: Optional[int],
) -> None:
    conn = _conn()
    conn.execute(
        """INSERT INTO photos
           (id, album_id, ext, original_name, contributor, width, height, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (photo_id, album_id, ext, original_name, contributor, width, height, time.time()),
    )
    conn.commit()


def list_photos(album_id: str) -> list[sqlite3.Row]:
    return _conn().execute(
        "SELECT * FROM photos WHERE album_id=? ORDER BY created_at ASC", (album_id,)
    ).fetchall()


def get_photo(photo_id: str) -> Optional[sqlite3.Row]:
    return _conn().execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()


def count_photos(album_id: str) -> int:
    row = _conn().execute(
        "SELECT COUNT(*) AS n FROM photos WHERE album_id=?", (album_id,)
    ).fetchone()
    return int(row["n"]) if row else 0


def delete_photo(photo_id: str) -> None:
    conn = _conn()
    conn.execute("DELETE FROM photos WHERE id=?", (photo_id,))
    conn.commit()


# --- Waitlist -------------------------------------------------------------

def add_waitlist(email: str) -> bool:
    """Store a waitlist email. Returns False if it was already present."""
    conn = _conn()
    cur = conn.execute(
        "INSERT OR IGNORE INTO waitlist (email, created_at) VALUES (?,?)",
        (email, time.time()),
    )
    conn.commit()
    return cur.rowcount > 0


def list_waitlist() -> list[sqlite3.Row]:
    return _conn().execute(
        "SELECT * FROM waitlist ORDER BY created_at DESC"
    ).fetchall()


def count_waitlist() -> int:
    row = _conn().execute("SELECT COUNT(*) AS n FROM waitlist").fetchone()
    return int(row["n"]) if row else 0


def album_theme(album: sqlite3.Row) -> dict[str, Any]:
    try:
        return json.loads(album["theme"]) or {}
    except (ValueError, TypeError):
        return {}
