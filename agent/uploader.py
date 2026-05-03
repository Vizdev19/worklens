import requests
import platform
from datetime import datetime, timezone

import auth
import queue_manager
from config import SERVER_URL

OS = platform.system()


def _do_upload(image_bytes: bytes, monitor_idx: int, captured_at: str) -> bool:
    """
    Send one screenshot to the backend.
    Returns True on success, False on failure.
    """
    token = auth.get_access_token()
    if not token:
        return False

    try:
        res = requests.post(
            f"{SERVER_URL}/screenshots/upload",
            files={"file": ("screenshot.jpg", image_bytes, "image/jpeg")},
            data={
                "captured_at": captured_at,
                "monitor_index": str(monitor_idx),
                "os_platform": OS,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )

        # Access token expired → refresh and retry once
        if res.status_code == 401:
            if auth.refresh_tokens():
                token = auth.get_access_token()
                res = requests.post(
                    f"{SERVER_URL}/screenshots/upload",
                    files={"file": ("screenshot.jpg", image_bytes, "image/jpeg")},
                    data={
                        "captured_at": captured_at,
                        "monitor_index": str(monitor_idx),
                        "os_platform": OS,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30,
                )

        return res.status_code == 200

    except requests.RequestException as e:
        print(f"[uploader] Network error: {e}")
        return False


def upload_screenshot(image_bytes: bytes, monitor_idx: int, captured_at: datetime):
    """Upload or enqueue if offline."""
    ts = captured_at.isoformat()
    success = _do_upload(image_bytes, monitor_idx, ts)
    if not success:
        print(f"[uploader] Upload failed — queuing for retry")
        queue_manager.enqueue(image_bytes, monitor_idx, OS, ts)


def flush_queue():
    """Retry pending uploads from the offline queue."""
    pending = queue_manager.get_pending(limit=5)
    if not pending:
        return

    print(f"[uploader] Retrying {len(pending)} queued screenshot(s)")
    for item in pending:
        success = _do_upload(item["image_bytes"], item["monitor_idx"], item["captured_at"])
        if success:
            queue_manager.mark_done(item["id"])
            print(f"[uploader] Queued item {item['id']} uploaded successfully")
        else:
            queue_manager.increment_attempts(item["id"])
