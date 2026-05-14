"""
SQLite-based offline queue.
Stores failed uploads locally and retries them when connectivity returns.

The DB lives in the per-user state dir (NOT the install folder). On
PyInstaller bundles the install folder is read-only / temp-extracted,
so writing the queue there would either fail or get wiped.
"""

import os
import platform
import sqlite3
from typing import List, Dict

from paths import state_dir

DB_PATH = str(state_dir() / "queue.db")
_PERMS_TIGHTENED = False


def _tighten_db_perms():
    """Make queue.db user-readable only (POSIX). The DB contains image
    bytes — set 0600 so other users on the box can't read screenshots."""
    global _PERMS_TIGHTENED
    if _PERMS_TIGHTENED or platform.system() == "Windows":
        return
    try:
        os.chmod(DB_PATH, 0o600)
        _PERMS_TIGHTENED = True
    except OSError:
        pass


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=5)
    # WAL lets readers and writers proceed concurrently — without it the
    # default rollback journal serialises every operation on the DB. The
    # agent has multiple concurrent consumers (capture loop, upload retry,
    # UI status poll, updater) and was hitting random "database is locked"
    # errors under load. busy_timeout gives the kernel up to 5s to wait for
    # a lock before failing instead of erroring immediately. Both pragmas
    # are safe to set on every connection — WAL is per-DB, not per-conn.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_queue():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_uploads (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                image_bytes BLOB    NOT NULL,
                monitor_idx INTEGER NOT NULL,
                os_platform TEXT    NOT NULL,
                captured_at TEXT    NOT NULL,
                attempts    INTEGER DEFAULT 0,
                created_at  TEXT    DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
    _tighten_db_perms()


def enqueue(image_bytes: bytes, monitor_idx: int, os_platform: str, captured_at: str):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO pending_uploads (image_bytes, monitor_idx, os_platform, captured_at) VALUES (?,?,?,?)",
            (image_bytes, monitor_idx, os_platform, captured_at),
        )
        conn.commit()


def get_pending(limit: int = 5) -> List[Dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, image_bytes, monitor_idx, os_platform, captured_at, attempts "
            "FROM pending_uploads WHERE attempts < 5 ORDER BY created_at LIMIT ?",
            (limit,),
        ).fetchall()

    return [
        {
            "id": r[0],
            "image_bytes": r[1],
            "monitor_idx": r[2],
            "os_platform": r[3],
            "captured_at": r[4],
            "attempts": r[5],
        }
        for r in rows
    ]


def mark_done(item_id: int):
    with _connect() as conn:
        conn.execute("DELETE FROM pending_uploads WHERE id = ?", (item_id,))
        conn.commit()


def increment_attempts(item_id: int):
    with _connect() as conn:
        conn.execute(
            "UPDATE pending_uploads SET attempts = attempts + 1 WHERE id = ?",
            (item_id,),
        )
        conn.commit()


def queue_size() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM pending_uploads").fetchone()[0]
