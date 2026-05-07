"""
Detect and install Microsoft Edge WebView2 runtime on Windows.

Required by pywebview to render the status window. Pre-installed on
Windows 11; missing on a lot of Windows 10 machines.

We bundle MicrosoftEdgeWebview2Setup.exe (the Evergreen Bootstrapper,
~150 KB) inside the build. On first launch we check the registry; if
the runtime isn't there, we run the bootstrapper silently — it
downloads and installs the actual ~150 MB runtime in the background.

Per-user install (HKCU) doesn't need admin privileges.
"""

import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


# WebView2 product GUID — same on all Windows versions
_WEBVIEW2_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


def is_installed() -> bool:
    """True if WebView2 runtime is present (machine-wide or per-user)."""
    if platform.system() != "Windows":
        return True   # Not relevant on macOS/Linux

    try:
        import winreg
    except ImportError:
        return True

    candidate_paths = [
        # Machine-wide (admin install)
        (winreg.HKEY_LOCAL_MACHINE,
         rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_GUID}"),
        (winreg.HKEY_LOCAL_MACHINE,
         rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_GUID}"),
        # Per-user (no admin needed)
        (winreg.HKEY_CURRENT_USER,
         rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_GUID}"),
    ]

    for hive, path in candidate_paths:
        try:
            with winreg.OpenKey(hive, path) as key:
                version, _ = winreg.QueryValueEx(key, "pv")
                if version and version != "0.0.0.0":
                    return True
        except FileNotFoundError:
            continue
        except OSError:
            continue
    return False


def _bootstrapper_path() -> Optional[Path]:
    """Locate the bundled MicrosoftEdgeWebview2Setup.exe."""
    candidates = []

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        # one-folder bundle layout (PyInstaller 6.x):
        #   EmployeeMonitor.exe      ← exe_dir
        #   _internal/
        #     MicrosoftEdgeWebview2Setup.exe
        #     ... (datas live here)
        candidates.append(exe_dir / "_internal")
        candidates.append(exe_dir)
        # one-file bundle: PyInstaller extracts everything into _MEIPASS
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS))

    # Dev: bootstrapper sits in the agent dir
    candidates.append(Path(__file__).resolve().parent)

    for d in candidates:
        p = d / "MicrosoftEdgeWebview2Setup.exe"
        if p.exists():
            return p
    return None


def ensure_installed(timeout_seconds: int = 180) -> bool:
    """
    If WebView2 is missing on Windows, run the bundled bootstrapper.

    Returns True if WebView2 is available after this call, False if
    we couldn't install it (employee will see the fallback dialog).
    """
    if platform.system() != "Windows":
        return True

    if is_installed():
        return True

    bootstrapper = _bootstrapper_path()
    if not bootstrapper:
        print("[webview2] runtime missing AND bootstrapper not bundled")
        return False

    print(f"[webview2] runtime missing — installing via {bootstrapper.name}")
    try:
        # /silent /install → unattended per-user install, no UI prompts
        proc = subprocess.Popen(
            [str(bootstrapper), "/silent", "/install"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as e:
        print(f"[webview2] could not launch bootstrapper: {e}")
        return False

    # Poll until it finishes or we hit the timeout
    deadline = time.time() + timeout_seconds
    while proc.poll() is None and time.time() < deadline:
        time.sleep(2)

    if proc.poll() is None:
        print("[webview2] bootstrapper still running after timeout — proceeding anyway")

    installed = is_installed()
    print(f"[webview2] post-install check: {'OK' if installed else 'still missing'}")
    return installed
