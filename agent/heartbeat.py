"""
Periodic heartbeat to the backend.

Runs in a background thread, sends a status pulse every ~10 min with
jitter. Powers admin observability ("who's running which version, are
they alive?") and closes the feedback loop on the auto-update system
("did 1.2.0 → 1.2.1 actually roll out?").

Endpoint: POST {SERVER_URL}/agent/heartbeat
Auth:     Bearer access_token from the keychain (same as upload)

Failure handling:
  - 401 once → refresh via auth, retry once
  - 426 (server demands update) → mirror uploader's 426 handler,
    flip must_update, wake the updater, no further retry this cycle
  - Anything else / network error → log and try again next cycle

Heartbeats are fire-and-forget; we never queue them. A missed heartbeat
just means the admin sees a slightly stale "last seen" value — acceptable
because the next one usually lands within 10 min.
"""

import platform
import random
import threading
from typing import Optional

import requests

import auth
import state
from config import AGENT_VERSION, SERVER_URL

# Tunables — exposed as module constants for tests / future config override.
_INTERVAL_SECONDS = 10 * 60        # 10 min
_JITTER_SECONDS = 60               # ±1 min — spreads the 9am Monday spike
_INITIAL_DELAY_RANGE = (10, 60)    # 10s..60s before the first ping
_TIMEOUT_SECONDS = 15

# Module-level lifecycle.
_thread: Optional[threading.Thread] = None
_wake = threading.Event()


# ── Public API ────────────────────────────────────────────────────────────────

def start() -> None:
    """Start the heartbeat thread. Idempotent."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _thread = threading.Thread(target=_loop, daemon=True, name="heartbeat")
    _thread.start()
    print("[heartbeat] background thread started (interval 10 min ± 1 min)")


def request_immediate() -> None:
    """Skip the remaining sleep and pulse on the next loop iteration.
    Currently unused — exposed for future "on important status change"
    triggers (e.g. status flip into permission_denied)."""
    _wake.set()


# ── Loop ──────────────────────────────────────────────────────────────────────

def _loop() -> None:
    # Initial delay so a fleet of agents that restart together (laptop
    # reboot, OS update) doesn't all pulse on the same second.
    initial = random.uniform(*_INITIAL_DELAY_RANGE)
    _wake.wait(timeout=initial)
    _wake.clear()

    while state.is_running():
        try:
            _send_once()
        except Exception as e:
            # Heartbeat must never take down the agent — capture everything.
            print(f"[heartbeat] cycle error: {type(e).__name__}: {e}")

        delay = _INTERVAL_SECONDS + random.uniform(
            -_JITTER_SECONDS, _JITTER_SECONDS
        )
        _wake.wait(timeout=max(60, delay))
        _wake.clear()

    print("[heartbeat] loop exit")


def _send_once() -> None:
    """One heartbeat. No-op until we have an access token (pre-login)."""
    token = auth.get_access_token()
    if not token:
        # Not logged in yet — silently skip. The user is at the login UI;
        # heartbeats start once auth succeeds.
        return

    snap = state.snapshot()
    payload = {
        "agent_version": AGENT_VERSION,
        "os_platform": _platform_key(),
        "status": snap.get("status", "unknown"),
        "queue_size": snap.get("queue_size", 0),
        "pending_review": snap.get("pending_review", 0),
        "captures_today": snap.get("captures_today", 0),
        "last_capture_at": snap.get("last_capture_at"),
        "last_upload_ok": bool(snap.get("last_upload_ok", True)),
    }

    res = _post(payload, token)

    if res is None:
        return  # network error already logged

    if res.status_code == 401:
        # Try a refresh, then one more attempt. Beyond that, give up
        # this cycle; auth flow already wiped credentials if the refresh
        # failed permanently.
        if auth.refresh_tokens():
            new_token = auth.get_access_token()
            if new_token:
                _post(payload, new_token)
        return

    if res.status_code == 426:
        # Server says we're too old. Mirror uploader._handle_426 so the
        # must_update state propagates from any agent-→server contact
        # surface, not just uploads.
        min_version = res.headers.get("X-Min-Agent-Version") or "unknown"
        try:
            body = res.json()
            if isinstance(body, dict):
                detail = body.get("detail") or {}
                if isinstance(detail, dict):
                    min_version = detail.get("min_supported") or min_version
        except Exception:
            pass
        print(
            f"[heartbeat] server requires agent >= {min_version}. Halting."
        )
        state.require_update(min_version)
        # Inline import to avoid a top-level cycle (updater → state → ...).
        try:
            import updater
            updater.request_immediate_check()
        except Exception as e:
            print(f"[heartbeat] could not signal updater: {e}")
        return

    if res.status_code >= 400:
        # Don't spam — log once with the body for diagnosis.
        print(f"[heartbeat] backend returned {res.status_code}: {res.text[:200]}")


def _post(payload: dict, token: str) -> Optional[requests.Response]:
    try:
        return requests.post(
            f"{SERVER_URL}/agent/heartbeat",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Agent-Version": AGENT_VERSION,
            },
            timeout=_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        # Common during VPN flaps / coffee-shop wifi — don't escalate.
        print(f"[heartbeat] network error: {e}")
        return None


def _platform_key() -> str:
    """
    Compute the manifest platform key. Duplicated from updater.platform_key()
    rather than imported to avoid a circular dep at module load time.
    """
    sysname = platform.system().lower()    # darwin / windows / linux
    machine = platform.machine().lower()
    arch_map = {
        "x86_64": "amd64",
        "amd64":  "amd64",
        "i386":   "386",
        "i686":   "386",
        "arm64":  "arm64",
        "aarch64": "arm64",
    }
    arch = arch_map.get(machine, machine)
    return f"{sysname}-{arch}"
