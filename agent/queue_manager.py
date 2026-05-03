"""
SQLite-based offline queue.
Stores failed uploads locally and retries them when connectivity returns.
"""

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "queue.db")


def init_queue():
    with sqlite3.connect(DB_PATH) as conn:
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


def enqueue(image_bytes: bytes, monitor_idx: int, os_platform: str, captured_at: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO pending_uploads (image_bytes, monitor_idx, os_platform, captured_at) VALUES (?,?,?,?)",
            (image_bytes, monitor_idx, os_platform, captured_at),
        )
        conn.commit()


def get_pending(limit: int = 5) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
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
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM pending_uploads WHERE id = ?", (item_id,))
        conn.commit()


def increment_attempts(item_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE pending_uploads SET attempts = attempts + 1 WHERE id = ?",
            (item_id,),
        )
        conn.commit()


def queue_size() -> int:
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT COUNT(*) FROM pending_uploads").fetchone()[0]
