"""
Employee Monitor Agent — Entry Point

Flow:
1. Check OS keychain for stored credentials
2. If not found → show login UI
3. Start idle tracker
4. Start system tray icon
5. Run capture + upload loop every N minutes
6. On each tick: skip if idle, capture all monitors, upload / queue
7. Every tick: also flush offline queue
"""

import platform
import sys
import time
import schedule
import threading

import auth
import capture
import uploader
import queue_manager
import idle
import tray
from config import CAPTURE_INTERVAL_MINUTES, IDLE_SKIP_MINUTES

OS = platform.system()
_running = True


def on_quit():
    global _running
    print("[main] Tray quit — stopping agent")
    _running = False


def check_platform_permissions():
    if OS == "Darwin":
        if not capture.check_macos_permission():
            print("[main] macOS screen recording permission denied.")
            print("       Go to: System Preferences → Privacy & Security → Screen Recording")
            print("       Enable this app, then restart.")
            sys.exit(1)


def capture_job():
    """Main periodic task: capture + upload."""
    if idle.is_idle(IDLE_SKIP_MINUTES):
        print(f"[main] Skipping — user idle for {idle.idle_seconds():.0f}s")
        tray.update_status("Idle — skipping capture", color="orange")
        return

    tray.update_status("Capturing...", color="blue")
    screenshots = capture.capture_all_monitors()

    for shot in screenshots:
        uploader.upload_screenshot(
            image_bytes=shot["image_bytes"],
            monitor_idx=shot["index"],
            captured_at=shot["captured_at"],
        )

    # Retry any queued (offline) uploads
    uploader.flush_queue()

    q = queue_manager.queue_size()
    status = f"Monitoring active{f' | {q} queued' if q else ''}"
    tray.update_status(status, color="green")
    print(f"[main] Captured {len(screenshots)} monitor(s). Queue size: {q}")


def main():
    print(f"[main] Starting Employee Monitor Agent (OS: {OS})")

    # ── Auth ──────────────────────────────────────────────────────────────────
    if not auth.is_logged_in():
        print("[main] No credentials found — showing login UI")
        from login_ui import show_login
        if not show_login():
            print("[main] Login cancelled. Exiting.")
            sys.exit(0)
        print(f"[main] Logged in as: {auth.get_full_name()}")
    else:
        print(f"[main] Credentials found for: {auth.get_full_name()}")

    # ── Platform checks ───────────────────────────────────────────────────────
    check_platform_permissions()

    # ── Init offline queue ────────────────────────────────────────────────────
    queue_manager.init_queue()

    # ── Idle tracker ──────────────────────────────────────────────────────────
    idle.start_idle_tracker()
    print("[main] Idle tracker started")

    # ── System tray ───────────────────────────────────────────────────────────
    tray.start_tray(on_quit_callback=on_quit)
    print("[main] System tray started")

    # ── Scheduler ─────────────────────────────────────────────────────────────
    schedule.every(CAPTURE_INTERVAL_MINUTES).minutes.do(capture_job)
    print(f"[main] Scheduler set — capturing every {CAPTURE_INTERVAL_MINUTES} minute(s)")

    # Run once immediately on startup
    capture_job()

    # ── Main loop ─────────────────────────────────────────────────────────────
    while _running:
        schedule.run_pending()
        time.sleep(10)

    print("[main] Agent stopped.")


if __name__ == "__main__":
    main()
