import platform
import threading
from datetime import datetime, timezone
from pynput import mouse, keyboard

_last_activity = datetime.now(timezone.utc)
_lock = threading.Lock()
OS = platform.system()


def _update_activity(*args, **kwargs):
    global _last_activity
    with _lock:
        _last_activity = datetime.now(timezone.utc)


def start_idle_tracker():
    """Start background listeners for mouse and keyboard activity."""
    mouse.Listener(
        on_move=_update_activity,
        on_click=_update_activity,
        on_scroll=_update_activity,
        daemon=True,
    ).start()

    keyboard.Listener(
        on_press=_update_activity,
        daemon=True,
    ).start()


def idle_seconds() -> float:
    """Return how many seconds since last user activity."""
    with _lock:
        delta = datetime.now(timezone.utc) - _last_activity
        return delta.total_seconds()


def is_idle(threshold_minutes: float) -> bool:
    return idle_seconds() >= threshold_minutes * 60
