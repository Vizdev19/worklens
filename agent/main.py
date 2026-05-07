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
import state
import uploader
from config import CAPTURE_INTERVAL_MINUTES, IDLE_SKIP_MINUTES

OS = platform.system()


# ── Capture loop ────────────────────────────────────────────────────────────

def capture_job():
    """Periodic task: capture all monitors and upload."""
    if not state.is_running():
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

    # If capture itself returned nothing (every monitor errored), don't
    # claim success — that would mislead the UI / dashboard heartbeat.
    if not screenshots:
        print("[main] No screenshots captured (all monitors failed)")
        state.record_capture(success=False)
        uploader.flush_queue()
        return

    upload_ok = True
    for shot in screenshots:
        try:
            uploader.upload_screenshot(
                image_bytes=shot["image_bytes"],
                monitor_idx=shot["index"],
                captured_at=shot["captured_at"],
            )
        except Exception as e:
            print(f"[main] Upload error: {e}")
            upload_ok = False

    # Drain offline queue if internet returned
    uploader.flush_queue()

    state.record_capture(success=upload_ok)
    print(
        f"[main] Captured {len(screenshots)} monitor(s) "
        f"(queued: {queue_manager.queue_size()})"
    )


def scheduler_loop():
    """Run the capture schedule until state.is_running() flips to False."""
    schedule.every(CAPTURE_INTERVAL_MINUTES).minutes.do(capture_job)
    print(f"[main] Scheduler started — every {CAPTURE_INTERVAL_MINUTES} min")

    # Capture immediately on startup
    capture_job()

    while state.is_running():
        schedule.run_pending()
        time.sleep(5)

    print("[main] Scheduler stopped")


# ── Sign out ────────────────────────────────────────────────────────────────

def on_signout():
    """Stop scheduler, clear creds, remove auto-start, exit cleanly."""
    print("[main] Sign-out requested")
    state.stop()
    auth.logout()
    autostart.uninstall()
    print("[main] Signed out — exiting in 1s")
    time.sleep(1)
    os._exit(0)  # Force exit; pywebview can hang on regular sys.exit


# ── Platform checks ─────────────────────────────────────────────────────────

def check_platform_permissions():
    if OS == "Darwin" and not capture.check_macos_permission():
        print("[main] macOS Screen Recording permission denied.")
        print("       Grant it in System Settings → Privacy & Security → "
              "Screen Recording, then re-launch.")
        # Don't exit — let user see the UI and the missing permission state


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
    idle.start_idle_tracker()
    print("[main] Idle tracker running")

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
