"""
Employee Monitor Agent — Entry Point

Threading model:
  - Main thread runs the pywebview status window (UI requires main thread on macOS).
  - Background thread runs the capture+upload scheduler.
  - Closing the window does NOT stop the agent — the scheduler keeps running.
  - "Sign out" stops the scheduler, clears credentials, removes auto-start, exits.
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
    log_dir = os.path.join(
        os.path.expanduser("~"),
        ("AppData/Local/EmployeeMonitor" if platform.system() == "Windows"
         else "Library/Logs/EmployeeMonitor" if platform.system() == "Darwin"
         else ".local/state/EmployeeMonitor"),
    )
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "agent.log")
    try:
        f = open(log_path, "a", buffering=1, encoding="utf-8")
        sys.stdout = f
        sys.stderr = f
    except Exception:
        # Worst case — give print() a no-op file
        sys.stdout = open(os.devnull, "w")
        sys.stderr = sys.stdout

_redirect_std_to_log()

import single_instance

# Bail out immediately if another agent is already running.
# Prevents the "duplicate captures every few seconds" bug caused by
# accidentally launching the agent twice.
if not single_instance.acquire():
    print("[main] Another EmployeeMonitor instance is already running. Exiting.")
    sys.exit(0)

import schedule

import auth
import autostart
import capture
import idle
import queue_manager
import state
import status_window
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

    # 5. Ensure WebView2 runtime is installed (Windows only — no-op elsewhere)
    if OS == "Windows":
        import webview2_check
        webview2_check.ensure_installed()

    # 6. Show status window on main thread (blocks until window closed)
    print("[main] Opening status window")
    status_window.open_window(on_signout=on_signout)

    # 6. Window closed — keep agent running headless until LaunchAgent stops us
    print("[main] Window closed — continuing in background")
    while state.is_running():
        time.sleep(5)


if __name__ == "__main__":
    main()
