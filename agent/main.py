"""
Employee Monitor Agent — Entry Point

Threading model:
  - Main thread sleeps in a loop while the agent runs.
  - Background thread runs the capture+upload scheduler.
  - Background thread runs an HTTP server (ui.py); the user's browser
    is opened to it on first launch.
  - Closing the browser tab does NOT stop the agent.
  - A second EmployeeMonitor.exe launch detects the running instance
    via the single-instance lock and re-opens the same URL in browser.
  - "Sign out" stops the scheduler, clears credentials, removes
    auto-start, and exits.
"""

import os
import platform
import sys
import threading
import time

# In Windows GUI builds (PyInstaller console=False), sys.stdout/stderr can be
# None, which makes any `print()` raise. Redirect them to a log file so we
# don't lose visibility AND don't crash on print.
def _redirect_std_to_log():
    if sys.stdout is not None and sys.stderr is not None:
        return  # already attached
    try:
        from paths import log_dir as _log_dir
        log_path = _log_dir() / "agent.log"
        f = open(log_path, "a", buffering=1, encoding="utf-8")
        sys.stdout = f
        sys.stderr = f
    except Exception:
        # Worst case — give print() a no-op file so it doesn't crash
        sys.stdout = open(os.devnull, "w")
        sys.stderr = sys.stdout

_redirect_std_to_log()

import webbrowser

import single_instance
import ui

# If another agent is already running, just re-open its UI in the
# user's browser and exit cleanly.
if not single_instance.acquire():
    existing_url = ui.read_url_from_file()
    if existing_url:
        try:
            webbrowser.open(existing_url)
            print(f"[main] Another instance is already running; re-opened {existing_url}")
        except Exception as e:
            print(f"[main] Could not reopen UI: {e}")
    else:
        print("[main] Another EmployeeMonitor instance is already running.")
    sys.exit(0)

import schedule

import auth
import autostart
import capture
import idle
import queue_manager
import review_queue
import state
import updater
import uploader
from config import AGENT_VERSION, CAPTURE_INTERVAL_MINUTES, IDLE_SKIP_MINUTES, SERVER_URL

OS = platform.system()


# ── Capture loop ────────────────────────────────────────────────────────────

def capture_job():
    """
    Periodic task: capture all monitors and enqueue for employee review.
    Screenshots are NOT uploaded here — review_upload_job() handles that
    once the review window has passed or the employee approves them.
    """
    if not state.is_running():
        return

    # Force-update wall: the server has told us this build is too old.
    # Skip capture entirely until Phase 4's updater swaps us out.
    if state.must_update_required():
        return

    # Screen Recording (macOS) was denied at startup — no point trying.
    # Status was already set to "permission_denied" in check_platform_permissions.
    if OS == "Darwin" and not capture.check_macos_permission():
        state.set_status("permission_denied")
        return

    if not state.is_tracking():
        state.set_status("paused")
        return

    if idle.is_idle(IDLE_SKIP_MINUTES):
        state.set_status("idle")
        print(f"[main] Idle — skipping capture")
        return

    state.set_status("active")
    screenshots = capture.capture_all_monitors()

    if not screenshots:
        print("[main] No screenshots captured (all monitors failed)")
        state.record_capture(success=False)
        return

    for shot in screenshots:
        try:
            review_queue.enqueue(
                image_bytes=shot["image_bytes"],
                monitor_idx=shot["index"],
                captured_at=shot["captured_at"],
            )
        except Exception as e:
            print(f"[main] Review enqueue error: {e}")

    state.record_capture(success=True)
    print(
        f"[main] Captured {len(screenshots)} monitor(s) — pending review "
        f"({review_queue.pending_count()} awaiting)"
    )


def review_upload_job():
    """
    Periodic task (every ~30s): auto-approve expired screenshots, upload
    approved ones, and report any deletion events to the server.
    """
    if state.must_update_required():
        return

    # 1. Auto-approve screenshots whose review window has elapsed
    approved = review_queue.auto_approve_expired()
    if approved:
        print(f"[main] Auto-approved {approved} screenshot(s) after review window")

    # 2. Upload approved screenshots
    for item in review_queue.get_approved():
        try:
            img_bytes = open(item["image_path"], "rb").read()
            from datetime import datetime, timezone
            captured_at = datetime.fromisoformat(item["captured_at"])
            uploader.upload_screenshot(
                image_bytes=img_bytes,
                monitor_idx=item["monitor_idx"],
                captured_at=captured_at,
            )
            review_queue.mark_uploaded(item["id"])
        except Exception as e:
            print(f"[main] Review upload error for {item['id']}: {e}")

    # 3. Report deletion events (best-effort — queued in DB so offline-safe)
    events = review_queue.drain_deletion_events()
    for ev in events:
        _report_deletion(ev["captured_at"], ev["monitor_idx"])

    # 4. Drain offline queue if internet returned
    uploader.flush_queue()


def _report_deletion(captured_at: str, monitor_idx: int):
    """POST a deletion event to the server audit log (best-effort)."""
    if state.must_update_required():
        return
    token = auth.get_access_token()
    if not token:
        return
    try:
        import requests as _req
        res = _req.post(
            f"{SERVER_URL}/screenshots/deletion-log",
            json={"captured_at": captured_at, "monitor_index": monitor_idx},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Agent-Version": AGENT_VERSION,
            },
            timeout=10,
        )
        if res.status_code == 426:
            # Mirror the uploader's 426 handler so the deletion path can't
            # quietly keep retrying after the gate has slammed shut.
            min_version = res.headers.get("X-Min-Agent-Version") or "unknown"
            try:
                body = res.json()
                if isinstance(body, dict):
                    detail = body.get("detail") or {}
                    if isinstance(detail, dict):
                        min_version = detail.get("min_supported") or min_version
            except Exception:
                pass
            print(f"[main] Deletion-log gate: server requires >= {min_version}. Halting.")
            state.require_update(min_version)
            updater.request_immediate_check()
    except Exception as e:
        print(f"[main] Deletion log report failed (will retry next cycle): {e}")


def scheduler_loop():
    """Run the capture + review-upload schedule until state.is_running() flips False."""
    schedule.every(CAPTURE_INTERVAL_MINUTES).minutes.do(capture_job)
    # Review uploads run more frequently so employees don't wait long after approving
    schedule.every(30).seconds.do(review_upload_job)
    print(f"[main] Scheduler started — capture every {CAPTURE_INTERVAL_MINUTES} min, review check every 30s")

    # Capture immediately on startup
    capture_job()
    # Also flush any approved items from a previous run (e.g. agent crashed mid-upload)
    review_upload_job()

    while state.is_running():
        schedule.run_pending()
        time.sleep(5)

    print("[main] Scheduler stopped")


# ── Sign out ────────────────────────────────────────────────────────────────

def on_signout():
    """
    Stop scheduler, clear creds, remove auto-start, exit cleanly.

    The legacy implementation called os._exit(0) here with a "pywebview
    can hang on regular sys.exit" comment, but pywebview was removed in
    the browser-UI migration. os._exit also skips atexit handlers and
    SQLite WAL checkpoints, AND short-circuits the auto-update restart
    branch in __main__ below — so we let main() return cleanly instead.
    """
    print("[main] Sign-out requested")
    state.stop()
    auth.logout()
    autostart.uninstall()
    print("[main] Signed out — main loop will exit on next tick")


# ── Platform checks ─────────────────────────────────────────────────────────

def check_platform_permissions():
    """
    One-shot check at startup. The agent doesn't keep re-checking — TCC
    permission is only granted via the system prompt, and once granted
    persists across launches (modulo binary-signature changes, which is
    why we tell the user to re-launch after granting).

    NB: without code signing, every agent update changes the binary
    hash → TCC may re-prompt on each update. There's no clean fix
    short of shipping a signed build; this is documented in the
    auto-update brainstorm under "limitations of v1".
    """
    if OS == "Darwin" and not capture.check_macos_permission():
        print("[main] macOS Screen Recording permission denied.")
        print("       Grant it in System Settings → Privacy & Security → "
              "Screen Recording, then re-launch.")
        # Surface in the UI so the user sees something actionable instead
        # of an agent that silently uploads black frames.
        state.set_status("permission_denied")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    from config import AGENT_VERSION
    print(f"[main] Starting Employee Monitor v{AGENT_VERSION} (OS: {OS})")

    # 1. Auth — block until logged in
    if not auth.is_logged_in():
        print("[main] No credentials — showing login")
        from login_ui import show_login
        if not show_login():
            print("[main] Login cancelled. Exiting.")
            sys.exit(0)
        autostart.install()
    else:
        print(f"[main] Logged in as {auth.get_full_name()}")

    # 2. Platform checks
    check_platform_permissions()

    # 3. Initialize subsystems
    queue_manager.init_queue()
    review_queue.init()
    idle.start_idle_tracker()
    print("[main] Idle tracker running")

    # 3b. Start the auto-update poller. Runs in its own thread, polls the
    # manifest hourly with ±15min jitter, downloads + stages new builds
    # into <install_dir>/updates/<v>.ready/. The Go launcher promotes them
    # on next start; the relaunch is triggered from the __main__ block
    # below once main() returns.
    updater.start()

    # 4. Start scheduler in background thread
    sched_thread = threading.Thread(target=scheduler_loop, daemon=True)
    sched_thread.start()

    # 5. Start the embedded HTTP UI server, then open it in the user's browser
    ui.start_server(on_signout=on_signout)
    ui.open_in_browser()

    # 6. Keep main thread alive until sign-out / OS shutdown
    while state.is_running():
        time.sleep(5)


if __name__ == "__main__":
    main()

    # main() returns when state.is_running() flips False. That happens
    # on either of:
    #   - on_signout() — clean shutdown, no relaunch wanted
    #   - updater.trigger_restart_for_update() — staged update is ready
    #     and we want the Go launcher to promote it + start the new build
    #
    # For the second case we need to drop the single-instance lock *before*
    # the launcher's child agent tries to acquire it, otherwise the new
    # process loses the race against this still-exiting one.
    if updater.restart_was_requested():
        print("[main] restart requested — releasing lock and spawning launcher")
        single_instance.release()
        updater.perform_restart_relaunch()
    sys.exit(0)
