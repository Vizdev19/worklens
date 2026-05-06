"""
Cross-platform single-instance lock.

Ensures only one agent process runs per user. Prevents the "multiple
captures every few seconds" bug caused by accidentally launching the
agent twice (Run-key + manual double-click, or repeated DMG launches).

Strategy: open a per-user lock file with an exclusive lock. Holding
the file handle keeps the lock alive for the lifetime of the process;
when the process dies the OS releases it automatically.

  - POSIX (macOS/Linux): fcntl.flock with LOCK_EX | LOCK_NB
  - Windows: msvcrt.locking with LK_NBLCK
"""

import os
import platform
import sys
from pathlib import Path

OS = platform.system()

_lock_handle = None  # keep a module-level reference so GC doesn't release it


def _lock_path() -> Path:
    if OS == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")))
        d = base / "EmployeeMonitor"
    elif OS == "Darwin":
        d = Path("~/Library/Application Support/EmployeeMonitor").expanduser()
    else:
        d = Path("~/.local/state/EmployeeMonitor").expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d / "agent.lock"


def acquire() -> bool:
    """
    Try to claim the single-instance lock.
    Returns True if we got it (continue running),
    False if another instance already holds it (we should exit).
    """
    global _lock_handle
    path = _lock_path()

    if OS == "Windows":
        import msvcrt
        try:
            f = open(path, "a+b")
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            _lock_handle = f
            return True
        except OSError:
            try:
                f.close()
            except Exception:
                pass
            return False
    else:
        import fcntl
        try:
            f = open(path, "a+b")
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            _lock_handle = f
            return True
        except (BlockingIOError, OSError):
            try:
                f.close()
            except Exception:
                pass
            return False
