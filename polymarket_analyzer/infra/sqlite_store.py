from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

SQLITE_DB_FILENAME = "polymarket_analyzer.sqlite"
SQLITE_DB_DIRNAME = "db"


def sqlite_db_path(cwd: Path | None = None) -> Path:
    base = cwd or Path.cwd()
    if base.name == "src-tauri" and base.parent:
        base = base.parent
    db_dir = base / SQLITE_DB_DIRNAME
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / SQLITE_DB_FILENAME


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS secrets (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at_ms INTEGER NOT NULL
        );
        """
    )
    conn.commit()
    return conn


def sqlite_save_secret(key: str, value: str, cwd: Path | None = None) -> None:
    k = key.strip()
    if not k:
        raise ValueError("secret key is empty")
    if not value:
        raise ValueError("secret value is empty")
    path = sqlite_db_path(cwd)
    conn = _connect(path)
    try:
        conn.execute(
            """
            INSERT INTO secrets(key, value, updated_at_ms) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at_ms=excluded.updated_at_ms
            """,
            (k, value, int(time.time() * 1000)),
        )
        conn.commit()
    finally:
        conn.close()


def sqlite_load_secret(key: str, cwd: Path | None = None) -> str | None:
    k = key.strip()
    if not k:
        raise ValueError("secret key is empty")
    path = sqlite_db_path(cwd)
    if not path.exists():
        return None
    conn = _connect(path)
    try:
        row = conn.execute("SELECT value FROM secrets WHERE key = ?", (k,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def sqlite_delete_secret(key: str, cwd: Path | None = None) -> None:
    k = key.strip()
    if not k:
        raise ValueError("secret key is empty")
    path = sqlite_db_path(cwd)
    if not path.exists():
        return
    conn = _connect(path)
    try:
        conn.execute("DELETE FROM secrets WHERE key = ?", (k,))
        conn.commit()
    finally:
        conn.close()


def sqlite_get_path_str(cwd: Path | None = None) -> str:
    return os.fspath(sqlite_db_path(cwd))
