"""
Pre-upload screenshot review queue.

After each capture the screenshots sit here until either:
  - the employee explicitly removes them (deleted → never uploaded), or
  - the review window expires (auto-approved → normal upload path), or
  - the employee clicks "Upload all now" (bulk approve).

DB  : state_dir() / review.db   (SQLite, 0600 perms on POSIX)
Files: state_dir() / pending_review / <id>.jpg        (full image for upload)
                                    / <id>_preview.jpg (640px JPEG for UI display)
"""

import os
import platform
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from io import BytesIO

from PIL import Image

from paths import state_dir

# Lazily imported to avoid circular deps at module load time
# (config imports nothing from the agent core; this is safe)
from config import REVIEW_WINDOW_MINUTES

_DB_PATH = state_dir() / "review.db"
_IMAGES_DIR = state_dir() / "pending_review"
_PREVIEW_WIDTH = 640   # pixels — larger than upload thumbnails, good for review


# ── Internal helpers ────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    # WAL + busy_timeout: see the same comment in queue_manager.py.
    # Critical here because the review queue is the busiest DB — capture
    # loop writes, review_upload_job writes/deletes every 30s, AND the UI
    # status polls the pending_count() reader continuously.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _tighten_perms():
    if platform.system() == "Windows":
        return
    try:
        os.chmod(str(_DB_PATH), 0o600)
        _IMAGES_DIR.chmod(0o700)
    except OSError:
        pass


def _make_preview(image_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(image_bytes))
    if img.width > _PREVIEW_WIDTH:
        ratio = _PREVIEW_WIDTH / img.width
        img = img.resize((_PREVIEW_WIDTH, int(img.height * ratio)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=75, optimize=True)
    buf.seek(0)
    return buf.read()


# ── Public API ──────────────────────────────────────────────────────────────

def init():
    """Create DB and images directory. Call once at startup."""
    _IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    with _connect() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS review_queue (
                id          TEXT PRIMARY KEY,
                monitor_idx INTEGER NOT NULL,
                captured_at TEXT    NOT NULL,
                image_path  TEXT    NOT NULL,
                preview_path TEXT   NOT NULL,
                deadline    TEXT    NOT NULL,
                status      TEXT    NOT NULL DEFAULT 'pending'
            )
        """)
        # Tracks deletions that haven't been reported to the server yet
        c.execute("""
            CREATE TABLE IF NOT EXISTS deletion_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at TEXT    NOT NULL,
                monitor_idx INTEGER NOT NULL,
                created_at  TEXT    DEFAULT (datetime('now'))
            )
        """)
        c.commit()
    _tighten_perms()


def enqueue(image_bytes: bytes, monitor_idx: int, captured_at: datetime) -> str:
    """
    Save a captured screenshot for review.
    Returns the item ID.
    """
    id_ = str(uuid.uuid4())
    img_path = _IMAGES_DIR / f"{id_}.jpg"
    preview_path = _IMAGES_DIR / f"{id_}_preview.jpg"

    img_path.write_bytes(image_bytes)
    preview_path.write_bytes(_make_preview(image_bytes))

    deadline = (captured_at + timedelta(minutes=REVIEW_WINDOW_MINUTES)).isoformat()

    with _connect() as c:
        c.execute(
            "INSERT INTO review_queue VALUES (?,?,?,?,?,?,'pending')",
            (id_, monitor_idx, captured_at.isoformat(),
             str(img_path), str(preview_path), deadline),
        )
        c.commit()
    return id_


def list_pending() -> list[dict]:
    """All screenshots waiting for employee review."""
    with _connect() as c:
        rows = c.execute(
            "SELECT id, monitor_idx, captured_at, preview_path, deadline "
            "FROM review_queue WHERE status='pending' ORDER BY captured_at"
        ).fetchall()
    return [dict(r) for r in rows]


def get_preview_path(id_: str) -> str | None:
    """Return the preview image path for the given pending item (for HTTP serving)."""
    with _connect() as c:
        row = c.execute(
            "SELECT preview_path FROM review_queue WHERE id=? AND status='pending'",
            (id_,),
        ).fetchone()
    return row["preview_path"] if row else None


def delete_item(id_: str) -> dict | None:
    """
    Employee removed this screenshot — purge local files and record the
    deletion event so it can be reported to the server for audit logs.
    Returns metadata dict on success, None if item not found / not pending.
    """
    with _connect() as c:
        row = c.execute(
            "SELECT * FROM review_queue WHERE id=? AND status='pending'", (id_,)
        ).fetchone()
        if not row:
            return None

        Path(row["image_path"]).unlink(missing_ok=True)
        Path(row["preview_path"]).unlink(missing_ok=True)

        c.execute(
            "UPDATE review_queue SET status='deleted', image_path='', preview_path='' WHERE id=?",
            (id_,),
        )
        c.execute(
            "INSERT INTO deletion_events (captured_at, monitor_idx) VALUES (?,?)",
            (row["captured_at"], row["monitor_idx"]),
        )
        c.commit()

    return {"captured_at": row["captured_at"], "monitor_idx": row["monitor_idx"]}


def approve(id_: str):
    """Mark a single item as approved for upload."""
    with _connect() as c:
        c.execute(
            "UPDATE review_queue SET status='approved' WHERE id=? AND status='pending'",
            (id_,),
        )
        c.commit()


def approve_all_pending():
    """Employee clicked 'Upload all now' — approve everything still pending."""
    with _connect() as c:
        c.execute("UPDATE review_queue SET status='approved' WHERE status='pending'")
        c.commit()


def auto_approve_expired() -> int:
    """
    Auto-approve items whose review window has passed.
    Called periodically by the upload loop. Returns number approved.
    """
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as c:
        cur = c.execute(
            "UPDATE review_queue SET status='approved' "
            "WHERE status='pending' AND deadline <= ?",
            (now,),
        )
        c.commit()
        return cur.rowcount


def get_approved() -> list[dict]:
    """Items ready to upload (approved by employee or by timeout)."""
    with _connect() as c:
        rows = c.execute(
            "SELECT id, monitor_idx, captured_at, image_path "
            "FROM review_queue WHERE status='approved' ORDER BY captured_at"
        ).fetchall()
    return [dict(r) for r in rows]


def mark_uploaded(id_: str):
    """Upload succeeded — purge local files and remove the row."""
    with _connect() as c:
        row = c.execute(
            "SELECT image_path, preview_path FROM review_queue WHERE id=?", (id_,)
        ).fetchone()
        if row:
            Path(row["image_path"]).unlink(missing_ok=True)
            Path(row["preview_path"]).unlink(missing_ok=True)
        c.execute("DELETE FROM review_queue WHERE id=?", (id_,))
        c.commit()


def drain_deletion_events() -> list[dict]:
    """
    Return unreported deletion events and clear them from the DB.
    Called by the upload loop so reports are sent even if the employee
    was offline when they deleted a screenshot.
    """
    with _connect() as c:
        rows = c.execute(
            "SELECT id, captured_at, monitor_idx FROM deletion_events ORDER BY id"
        ).fetchall()
        if rows:
            ids = [r["id"] for r in rows]
            c.execute(
                f"DELETE FROM deletion_events WHERE id IN ({','.join('?'*len(ids))})",
                ids,
            )
            c.commit()
    return [dict(r) for r in rows]


def pending_count() -> int:
    with _connect() as c:
        return c.execute(
            "SELECT COUNT(*) FROM review_queue WHERE status='pending'"
        ).fetchone()[0]
