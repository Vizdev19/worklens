"""
Shared in-memory state for the agent.

Capture loop writes to it; the status window reads from it.
Thread-safe via a single lock — small enough that contention is a non-issue.
"""

import threading
from datetime import datetime, date, timezone

import auth
import queue_manager
import review_queue


_lock = threading.Lock()
_state = {
    "status": "starting",          # starting | active | idle | paused | offline | update_required
    "last_capture_at": None,       # ISO string or None
    "captures_today": 0,
    "captures_today_date": None,   # date the counter was last reset
    "last_upload_ok": True,        # last upload succeeded?
    "running": True,               # set False to stop the agent (signout/quit)
    "tracking": True,              # employee toggle — when False, capture_job is a no-op
    # Force-update flag — set when the backend returns 426 on an upload.
    # While True, capture_job, review_upload_job, and the offline queue
    # flusher all no-op. Phase 4's updater will react to this by downloading
    # the new binary and exiting; until then it's just a kill switch.
    "must_update": False,
    "must_update_min_version": None,   # version the server told us we need
}


def set_status(new_status: str):
    with _lock:
        _state["status"] = new_status


def record_capture(success: bool):
    today = date.today()
    with _lock:
        # Reset daily counter at midnight
        if _state["captures_today_date"] != today:
            _state["captures_today"] = 0
            _state["captures_today_date"] = today
        _state["captures_today"] += 1
        _state["last_capture_at"] = datetime.now(timezone.utc).isoformat()
        _state["last_upload_ok"] = success


def is_running() -> bool:
    with _lock:
        return _state["running"]


def is_tracking() -> bool:
    with _lock:
        return _state["tracking"]


def set_tracking(value: bool):
    with _lock:
        _state["tracking"] = bool(value)
        if not _state["tracking"]:
            _state["status"] = "paused"


def stop():
    with _lock:
        _state["running"] = False
        _state["status"] = "stopped"


def require_update(min_version: str):
    """
    Backend returned 426 — agent is below the published minimum version.
    Halts all capture/upload activity until the process is replaced by an
    updated build. Idempotent.
    """
    with _lock:
        _state["must_update"] = True
        _state["must_update_min_version"] = min_version
        _state["status"] = "update_required"


def must_update_required() -> bool:
    with _lock:
        return _state["must_update"]


def snapshot() -> dict:
    """Return everything the UI needs to render."""
    from config import CAPTURE_INTERVAL_MINUTES, IDLE_SKIP_MINUTES, REVIEW_WINDOW_MINUTES, AGENT_VERSION

    with _lock:
        s = dict(_state)

    return {
        "version": AGENT_VERSION,
        "full_name": auth.get_full_name() or "",
        "email_or_id": auth.get_employee_id() or "",
        "status": s["status"],
        "last_capture_at": s["last_capture_at"],
        "captures_today": s["captures_today"],
        "queue_size": queue_manager.queue_size(),
        "pending_review": review_queue.pending_count(),
        "last_upload_ok": s["last_upload_ok"],
        "capture_interval_minutes": CAPTURE_INTERVAL_MINUTES,
        "idle_skip_minutes": IDLE_SKIP_MINUTES,
        "review_window_minutes": REVIEW_WINDOW_MINUTES,
        "running": s["running"],
        "tracking": s["tracking"],
        "must_update": s["must_update"],
        "must_update_min_version": s["must_update_min_version"],
    }
