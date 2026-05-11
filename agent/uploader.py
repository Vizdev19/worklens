import platform
from datetime import datetime, timezone

import requests

import auth
import queue_manager
import state
from config import AGENT_VERSION, SERVER_URL

OS = platform.system()


def _build_headers(token: str) -> dict:
    """Common headers for every backend call. X-Agent-Version drives the
    server-side force-update gate; without it the server defaults the
    agent to 0.0.0 and rejects with 426 once min_supported moves above that."""
    return {
        "Authorization": f"Bearer {token}",
        "X-Agent-Version": AGENT_VERSION,
    }


def _handle_426(res: requests.Response) -> None:
    """
    Backend says this agent is below the published minimum version.
    Flip the global must_update flag so the capture loop and queue
    flusher stop hammering the API. Phase 4's updater module will react
    to this flag by downloading the new binary and exiting cleanly.
    """
    min_version = res.headers.get("X-Min-Agent-Version") or "unknown"
    try:
        body = res.json()
        # FastAPI HTTPException(detail=dict) → {"detail": {...}}
        if isinstance(body, dict):
            detail = body.get("detail") or {}
            if isinstance(detail, dict):
                min_version = detail.get("min_supported") or min_version
    except Exception:
        pass
    print(f"[uploader] Server requires agent >= {min_version}. Halting captures.")
    state.require_update(min_version)


def _do_upload(image_bytes: bytes, monitor_idx: int, captured_at: str) -> bool:
    """
    Send one screenshot to the backend.
    Returns True on success, False on failure.

    Side effect: sets the agent-wide must_update flag on HTTP 426. Callers
    should still check state.must_update_required() before re-enqueuing so
    failed uploads in flight don't bounce back into the offline queue.
    """
    token = auth.get_access_token()
    if not token:
        return False

    files = {"file": ("screenshot.jpg", image_bytes, "image/jpeg")}
    data = {
        "captured_at": captured_at,
        "monitor_index": str(monitor_idx),
        "os_platform": OS,
    }

    try:
        res = requests.post(
            f"{SERVER_URL}/screenshots/upload",
            files=files,
            data=data,
            headers=_build_headers(token),
            timeout=30,
        )

        # Access token expired → refresh and retry once
        if res.status_code == 401:
            if auth.refresh_tokens():
                token = auth.get_access_token()
                res = requests.post(
                    f"{SERVER_URL}/screenshots/upload",
                    files=files,
                    data=data,
                    headers=_build_headers(token),
                    timeout=30,
                )

        if res.status_code == 426:
            _handle_426(res)
            return False

        return res.status_code == 200

    except requests.RequestException as e:
        print(f"[uploader] Network error: {e}")
        return False


def upload_screenshot(image_bytes: bytes, monitor_idx: int, captured_at: datetime):
    """Upload or enqueue if offline."""
    if state.must_update_required():
        # Agent has already been told it's too old — don't keep growing the queue.
        return

    ts = captured_at.isoformat()
    success = _do_upload(image_bytes, monitor_idx, ts)
    if not success and not state.must_update_required():
        # Only enqueue on real failures (network), not on 426 which would
        # just bounce back forever.
        print(f"[uploader] Upload failed — queuing for retry")
        queue_manager.enqueue(image_bytes, monitor_idx, OS, ts)


def flush_queue():
    """Retry pending uploads from the offline queue."""
    if state.must_update_required():
        return

    pending = queue_manager.get_pending(limit=5)
    if not pending:
        return

    print(f"[uploader] Retrying {len(pending)} queued screenshot(s)")
    for item in pending:
        if state.must_update_required():
            # 426 fired mid-batch — bail before incrementing more attempts
            return
        success = _do_upload(item["image_bytes"], item["monitor_idx"], item["captured_at"])
        if success:
            queue_manager.mark_done(item["id"])
            print(f"[uploader] Queued item {item['id']} uploaded successfully")
        else:
            queue_manager.increment_attempts(item["id"])
