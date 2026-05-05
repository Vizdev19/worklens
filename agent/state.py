"""
Shared in-memory state for the agent.

Capture loop writes to it; the status window reads from it.
Thread-safe via a single lock — small enough that contention is a non-issue.
"""

import threading
from datetime import datetime, date, timezone

import auth
import queue_manager


_lock = threading.Lock()
_state = {
    "status": "starting",          # starting | active | idle | offline
    "last_capture_at": None,       # ISO string or None
    "captures_today": 0,
    "captures_today_date": None,   # date the counter was last reset
    "last_upload_ok": True,        # last upload succeeded?
    "running": True,               # set False to stop the scheduler
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


def stop():
    with _lock:
        _state["running"] = False
        _state["status"] = "stopped"


def snapshot() -> dict:
    """Return everything the UI needs to render."""
    from config import CAPTURE_INTERVAL_MINUTES, IDLE_SKIP_MINUTES

    with _lock:
        s = dict(_state)

    return {
        "full_name": auth.get_full_name() or "",
        "email_or_id": auth.get_employee_id() or "",
        "status": s["status"],
        "last_capture_at": s["last_capture_at"],
        "captures_today": s["captures_today"],
        "queue_size": queue_manager.queue_size(),
        "last_upload_ok": s["last_upload_ok"],
        "capture_interval_minutes": CAPTURE_INTERVAL_MINUTES,
        "idle_skip_minutes": IDLE_SKIP_MINUTES,
        "running": s["running"],
    }
