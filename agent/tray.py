"""
Cross-platform system tray icon using pystray.
Shows monitoring status and allows the employee to see info / quit.
"""

import threading
import platform
from PIL import Image, ImageDraw
import pystray
import auth
import queue_manager

OS = platform.system()
_icon = None
_status = "Monitoring active"


def _create_icon_image(color: str = "green") -> Image.Image:
    """Generate a simple colored circle as the tray icon."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, size - 4, size - 4], fill=color)
    return img


def _build_menu():
    name = auth.get_full_name() or "Employee"
    q_size = queue_manager.queue_size()
    queue_label = f"Queued (offline): {q_size}" if q_size > 0 else "All uploads synced"

    return pystray.Menu(
        pystray.MenuItem(f"👤 {name}", lambda: None, enabled=False),
        pystray.MenuItem(_status, lambda: None, enabled=False),
        pystray.MenuItem(queue_label, lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit monitoring", _quit),
    )


def _quit(icon, item):
    icon.stop()


def update_status(new_status: str, color: str = "green"):
    global _status
    _status = new_status
    if _icon:
        _icon.icon = _create_icon_image(color)
        _icon.menu = _build_menu()
        try:
            _icon.update_menu()
        except Exception:
            pass


def start_tray(on_quit_callback=None):
    """Start the system tray icon in a background thread.

    If the tray fails to start (e.g. headless system or platform GUI
    framework mismatch), we silently continue — agent still runs.
    """
    global _icon

    def _run():
        global _icon
        try:
            _icon = pystray.Icon(
                name="EmployeeMonitor",
                icon=_create_icon_image("green"),
                title="Employee Monitor — Active",
                menu=_build_menu(),
            )
            _icon.run()
        except Exception as e:
            print(f"[tray] Tray icon unavailable ({e}); continuing without it")
            _icon = None
            return
        if on_quit_callback:
            on_quit_callback()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t
