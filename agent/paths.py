"""
One source of truth for per-user directories.

Two trees, deliberately separated on Linux per XDG:

  state_dir()    — mutable state the agent writes at runtime:
                   queue.db, review.db, logs, single-instance lock.
                   macOS:   ~/Library/Application Support/EmployeeMonitor
                   Windows: %LOCALAPPDATA%\\EmployeeMonitor
                   Linux:   ~/.local/state/EmployeeMonitor

  install_dir()  — where the launcher and versioned agent builds live:
                   macOS:   same as state_dir (Mac has no XDG split)
                   Windows: same as state_dir
                   Linux:   ~/.local/share/EmployeeMonitor

Why split on Linux: binaries belong in $XDG_DATA_HOME; DBs / logs belong in
$XDG_STATE_HOME. Following this means `du -sh ~/.local/state` actually
reflects user-data size and packagers don't get angry.

Never write into the install folder at runtime — the launcher promotes
update directories into bin/, and the agent must not race that. Mutable
files always go through state_dir().

EMPLOYEE_MONITOR_HOME overrides BOTH directories to the same path, for
tests and CI. The Go launcher honours the same env var.
"""

import os
import platform
import sys
from pathlib import Path

_ENV_HOME_OVERRIDE = "EMPLOYEE_MONITOR_HOME"


def _override() -> Path | None:
    o = os.environ.get(_ENV_HOME_OVERRIDE)
    if not o:
        return None
    p = Path(o)
    p.mkdir(parents=True, exist_ok=True)
    return p


def state_dir() -> Path:
    """Mutable runtime state. Matches the Go launcher's stateDir()."""
    o = _override()
    if o:
        return o
    sysname = platform.system()
    if sysname == "Windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        d = Path(base) / "EmployeeMonitor"
    elif sysname == "Darwin":
        d = Path.home() / "Library" / "Application Support" / "EmployeeMonitor"
    else:
        base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
        d = Path(base) / "EmployeeMonitor"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_dir() -> Path:
    """Logs live alongside state in our app dir."""
    if platform.system() == "Darwin":
        d = Path.home() / "Library" / "Logs" / "EmployeeMonitor"
        d.mkdir(parents=True, exist_ok=True)
        return d
    return state_dir()


def install_dir() -> Path:
    """
    Where the launcher binary and bin/<version>/ trees live.

    Note: on Linux this is *different* from state_dir() because XDG_DATA_HOME
    is the right home for shipped binaries, not XDG_STATE_HOME. On Mac and
    Windows the convention is to keep both under one tree, so install_dir
    returns the same path as state_dir there.
    """
    o = _override()
    if o:
        return o
    sysname = platform.system()
    if sysname == "Windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        d = Path(base) / "EmployeeMonitor"
    elif sysname == "Darwin":
        d = Path.home() / "Library" / "Application Support" / "EmployeeMonitor"
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        d = Path(base) / "EmployeeMonitor"
    d.mkdir(parents=True, exist_ok=True)
    return d


def updates_dir() -> Path:
    """Staging area for downloads. The Go launcher reads this on startup."""
    d = install_dir() / "updates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def versions_dir() -> Path:
    """Where promoted updates live. <versions_dir>/<semver>/<binary>."""
    d = install_dir() / "bin"
    d.mkdir(parents=True, exist_ok=True)
    return d


def launcher_path() -> Path:
    """
    Resolve the launcher binary's path so the updater can re-exec it
    after staging an update.

    Returns the file the OS autostart entry points at. The path is only
    guaranteed to exist for 1.2.0+ installs that ship with the launcher;
    callers must check .exists() before invoking.
    """
    sysname = platform.system()
    if sysname == "Windows":
        return install_dir() / "EmployeeMonitor.exe"
    if sysname == "Darwin":
        # During Phase 4 the launcher is a plain Mach-O binary at the
        # install root. Phase 5 may wrap it in a .app bundle; if so we
        # point at Contents/MacOS/EmployeeMonitor here.
        bundled = install_dir() / "EmployeeMonitor.app" / "Contents" / "MacOS" / "EmployeeMonitor"
        if bundled.exists():
            return bundled
        return install_dir() / "EmployeeMonitor"
    return install_dir() / "EmployeeMonitor"


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle. Dev runs return False."""
    return getattr(sys, "frozen", False)
