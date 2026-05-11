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

import platform
from pathlib import Path

from paths import state_dir

OS = platform.system()

_lock_handle = None  # keep a module-level reference so GC doesn't release it


def _lock_path() -> Path:
    return state_dir() / "agent.lock"


def release() -> None:
    """
    Explicitly release the single-instance lock.

    Used during the auto-update relaunch: the updater spawns the launcher
    as a detached subprocess, which will exec the new agent. If we left
    the lock held until the Python interpreter exits, the new agent could
    hit acquire() before we're gone — single_instance.acquire() would
    fail, the new agent would just open the UI URL and exit, leaving the
    user with no agent running.

    By closing the file handle here we make sure the kernel releases the
    fcntl/msvcrt lock immediately, even if our process lingers for a
    moment doing cleanup. Safe to call multiple times.
    """
    global _lock_handle
    if _lock_handle is not None:
        try:
            _lock_handle.close()
        except Exception:
            pass
        _lock_handle = None


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
