"""
One source of truth for per-user state directories.

These are the directories the agent owns and writes to at runtime:
  - macOS:   ~/Library/Application Support/EmployeeMonitor
  - Windows: %LOCALAPPDATA%\\EmployeeMonitor
  - Linux:   ~/.local/state/EmployeeMonitor

Every file we create at runtime (lock, URL handoff, queue DB, logs)
should live under state_dir(). Never write into the install folder —
that may be read-only or clobbered by app updates.
"""

import os
import platform
from pathlib import Path


def state_dir() -> Path:
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        d = Path(base) / "EmployeeMonitor"
    elif platform.system() == "Darwin":
        d = Path.home() / "Library" / "Application Support" / "EmployeeMonitor"
    else:
        d = Path.home() / ".local" / "state" / "EmployeeMonitor"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_dir() -> Path:
    """Logs live alongside state in our app dir."""
    if platform.system() == "Darwin":
        d = Path.home() / "Library" / "Logs" / "EmployeeMonitor"
        d.mkdir(parents=True, exist_ok=True)
        return d
    return state_dir()
