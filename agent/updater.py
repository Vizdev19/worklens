"""
Background updater.

Polls GET /agent/version on a jittered hourly cadence, compares the
returned manifest against AGENT_VERSION, and — when a newer build
exists for our platform — downloads it, verifies the SHA-256 against
the manifest, extracts it into <install_dir>/updates/<v>.pending/,
and atomically renames that directory to <v>.ready/ so the Go
launcher will promote it on next start.

Two paths through the same code:

  Normal upgrade
    - We learn about v1.2.1 via the periodic poll
    - Download in background, stage as .ready
    - Surface a "Restart for update" banner in the local UI
    - User clicks → relaunch via the launcher

  Forced upgrade (must_update flag is set from uploader's 426 handler)
    - request_immediate_check() pokes the wake event
    - We download immediately and trigger a relaunch without waiting
      for the user — captures are already halted, no value in lingering

Either way the OS autostart entry now points at the launcher binary,
not the agent's PyInstaller bundle, so the agent's job ends at
"hand off cleanly." perform_restart_relaunch() in main.py does the
detached subprocess.Popen of the launcher after the single-instance
lock has been released; the launcher promotes the staged update and
execs the new agent.

We deliberately use stdlib only (urllib, hashlib, tarfile, zipfile).
The agent already bundles `requests` via the uploader, but the updater
is on the path where every dependency import counts toward PyInstaller
bundle weight, and stdlib is enough.
"""

import hashlib
import json
import os
import platform
import random
import shutil
import subprocess
import tarfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

import paths
import state
from config import AGENT_VERSION, SERVER_URL

# ── Tunables ──────────────────────────────────────────────────────────────────

# Cadence of the normal-path poll. ±JITTER spreads the 9am Monday spike
# so 1000 agents don't all hit /agent/version at the same second.
_CHECK_INTERVAL_SECONDS = 60 * 60        # 1h
_JITTER_SECONDS = 60 * 15                # ±15 min
# Brief randomized startup delay — agents launched together (laptop reboot,
# OS update fleet) shouldn't all check immediately on the same second.
_INITIAL_DELAY_RANGE = (30, 300)         # 30s..5min

_MANIFEST_FETCH_TIMEOUT = 30             # seconds
_DOWNLOAD_TIMEOUT = 120                  # seconds; per-chunk timeout
_DOWNLOAD_CHUNK_BYTES = 64 * 1024

# ── Module state ──────────────────────────────────────────────────────────────

_thread: Optional[threading.Thread] = None
_wake = threading.Event()
_restart_lock = threading.Lock()
_restart_requested = False


# ── Public API ────────────────────────────────────────────────────────────────

def start() -> None:
    """
    Spin up the updater's background thread. Idempotent — safe to call
    twice from main() on startup.
    """
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _thread = threading.Thread(target=_loop, daemon=True, name="updater")
    _thread.start()
    print(f"[updater] background thread started (platform={platform_key()})")


def request_immediate_check() -> None:
    """
    Wake the updater thread now (skip the remaining jittered sleep).

    Called from uploader._handle_426() so a force-update from the server
    starts downloading within seconds rather than at the next hourly tick.
    """
    _wake.set()


def restart_was_requested() -> bool:
    """
    Read-only check used by main.py after the main loop exits, to decide
    whether to spawn the launcher for relaunch or just exit normally.
    """
    with _restart_lock:
        return _restart_requested


def trigger_restart_for_update() -> None:
    """
    Mark a restart as pending and tell the rest of the agent to stop.

    The actual subprocess.Popen of the launcher happens later, in
    perform_restart_relaunch(), AFTER the single-instance lock has been
    released — otherwise the freshly-spawned agent loses the lock race
    against this still-exiting one.
    """
    with _restart_lock:
        global _restart_requested
        _restart_requested = True
    state.stop()


def perform_restart_relaunch() -> None:
    """
    Spawn the Go launcher as a detached subprocess and return. The caller
    (main.py) is responsible for ensuring the single-instance lock has
    been released and that the Python interpreter is about to exit.

    No-ops on dev/source runs where the launcher binary doesn't exist.
    """
    launcher = paths.launcher_path()
    if not launcher.exists():
        print(f"[updater] cannot relaunch: launcher missing at {launcher}")
        print("[updater] (this is expected in source/dev mode)")
        return

    print(f"[updater] spawning launcher for relaunch: {launcher}")
    try:
        if platform.system() == "Windows":
            # DETACHED_PROCESS = no console, no parent — child survives
            # our exit independently.
            flags = (
                getattr(subprocess, "DETACHED_PROCESS", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )
            subprocess.Popen([str(launcher)], creationflags=flags, close_fds=True)
        else:
            subprocess.Popen(
                [str(launcher)],
                start_new_session=True,
                close_fds=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception as e:
        print(f"[updater] launcher spawn failed: {e}")


def platform_key() -> str:
    """
    Manifest platform key for this OS/arch combo. Matches what the
    Go launcher computes from runtime.GOOS/GOARCH, and what the CI
    release workflow names artifacts as.

    Examples: darwin-arm64, darwin-amd64, windows-amd64, linux-amd64.
    """
    sysname = platform.system().lower()    # darwin / windows / linux
    machine = platform.machine().lower()
    arch_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "i386": "386",
        "i686": "386",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    arch = arch_map.get(machine, machine)
    return f"{sysname}-{arch}"


# ── Loop body ─────────────────────────────────────────────────────────────────

def _loop() -> None:
    """
    Long-running background poll. Wakes early on _wake.set(), exits when
    state.is_running() flips False (signout / restart-for-update).
    """
    # Spread the startup spike.
    initial = random.uniform(*_INITIAL_DELAY_RANGE)
    _wake.wait(timeout=initial)
    _wake.clear()

    while state.is_running():
        try:
            _check_once()
        except Exception as e:
            # Never let the updater take down the agent.
            print(f"[updater] cycle error: {type(e).__name__}: {e}")

        # Sleep with jitter so the next-cycle thundering herd is spread
        # across 30 minutes.
        delay = _CHECK_INTERVAL_SECONDS + random.uniform(
            -_JITTER_SECONDS, _JITTER_SECONDS
        )
        _wake.wait(timeout=max(60, delay))
        _wake.clear()

    print("[updater] loop exit")


def _check_once() -> None:
    """One poll cycle. Decides between no-op / surface-banner / download-and-restart."""
    manifest = _fetch_manifest()
    if manifest is None:
        return

    latest = manifest.get("version")
    min_supported = manifest.get("min_supported", "0.0.0")
    platforms_map = manifest.get("platforms") or {}
    if not latest or not platforms_map:
        return

    # Nothing newer? Done.
    if _cmp_version(latest, AGENT_VERSION) <= 0:
        return

    key = platform_key()
    asset = platforms_map.get(key)
    if not asset:
        # The manifest exists but doesn't list this platform. Two cases:
        #   - Normal: minor releases sometimes skip a platform (e.g. we
        #     dropped macos-13 from CI). The agent just sits on its
        #     current version until a platform-inclusive release ships.
        #   - Critical: force-update is already required (must_update set
        #     from a 426) AND there's no asset to install. The agent is
        #     now halted with no way to recover until the manifest is
        #     fixed. Log loudly so it shows up in support tickets.
        if state.must_update_required():
            print(
                f"[updater] CRITICAL: server requires update but no asset "
                f"for {key} in the published manifest. Agent will remain "
                f"halted until the manifest is updated."
            )
        else:
            print(f"[updater] manifest has no asset for {key}; skipping")
        return

    is_forced = state.must_update_required() or (
        _cmp_version(AGENT_VERSION, min_supported) < 0
    )

    # Already staged on disk from a previous run? Don't re-download.
    if _is_already_staged(latest):
        print(f"[updater] {latest} already staged; awaiting restart")
        state.set_update_available(latest, ready=True)
        if is_forced:
            trigger_restart_for_update()
        return

    # Tell the UI we're about to start downloading.
    state.set_update_available(latest, ready=False)
    print(f"[updater] new version: {latest} (forced={is_forced}, platform={key})")

    try:
        _download_and_stage(latest, asset)
    except Exception as e:
        print(f"[updater] download/stage failed for {latest}: {e}")
        # Leave update_ready=False; we'll try again next cycle.
        return

    state.set_update_available(latest, ready=True)
    print(f"[updater] {latest} staged at updates/{latest}.ready")

    if is_forced:
        trigger_restart_for_update()


# ── Manifest + download ───────────────────────────────────────────────────────

def _fetch_manifest() -> Optional[dict]:
    """
    GET {SERVER_URL}/agent/version. Returns the parsed JSON, or None on
    any failure (404 = no release published, treated as "no update").
    """
    url = f"{SERVER_URL}/agent/version"
    req = urllib.request.Request(
        url,
        headers={
            "X-Agent-Version": AGENT_VERSION,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_MANIFEST_FETCH_TIMEOUT) as resp:
            if resp.status != 200:
                return None
            data = resp.read()
            return json.loads(data.decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # No release configured yet — happens in dev envs.
            return None
        print(f"[updater] manifest HTTP {e.code}")
        return None
    except Exception as e:
        # Network, JSON, etc. — log and back off.
        print(f"[updater] manifest fetch: {type(e).__name__}: {e}")
        return None


def _is_already_staged(version: str) -> bool:
    return (paths.updates_dir() / f"{version}.ready").exists()


def _download_and_stage(version: str, asset: dict) -> None:
    """
    Pull the platform archive, verify size + SHA-256 against the manifest,
    extract into updates/<v>.pending/, then atomically rename to .ready/.

    A crash mid-download leaves a .archive.tmp file we'll clean up next
    cycle. A crash mid-extract leaves a .pending/ directory we'll also
    clean up. Only the final os.rename to .ready/ is the commit point.
    """
    url: str = asset["url"]
    expected_sha: str = asset["sha256"].lower()
    expected_size: int = int(asset["size"])

    updates = paths.updates_dir()
    archive_tmp = updates / f"{version}.archive.tmp"
    pending = updates / f"{version}.pending"
    ready = updates / f"{version}.ready"

    # Wipe any half-baked artifacts from a prior failed cycle.
    if archive_tmp.exists():
        archive_tmp.unlink()
    if pending.exists():
        shutil.rmtree(pending, ignore_errors=True)
    if ready.exists():
        # Should have been caught by _is_already_staged. Defensive.
        return

    print(f"[updater] downloading {url}  ({expected_size} bytes)")
    h = hashlib.sha256()
    bytes_read = 0
    req = urllib.request.Request(url, headers={"X-Agent-Version": AGENT_VERSION})
    with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT) as resp:
        with open(archive_tmp, "wb") as f:
            while True:
                chunk = resp.read(_DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                bytes_read += len(chunk)
                if bytes_read > expected_size + 1024:
                    # Manifest lied about size, or we hit a redirect to
                    # an attacker-controlled object. Either way: stop.
                    raise RuntimeError(
                        f"download exceeded manifest size {expected_size} "
                        f"(got {bytes_read})"
                    )

    if bytes_read != expected_size:
        archive_tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"size mismatch: expected {expected_size}, got {bytes_read}"
        )

    actual_sha = h.hexdigest()
    if actual_sha != expected_sha:
        archive_tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"sha256 mismatch: expected {expected_sha}, got {actual_sha}"
        )

    # Extract.
    pending.mkdir(parents=True, exist_ok=True)
    try:
        _extract_archive(archive_tmp, pending)
    except Exception:
        shutil.rmtree(pending, ignore_errors=True)
        archive_tmp.unlink(missing_ok=True)
        raise

    # Commit: atomic rename to .ready/.
    os.rename(pending, ready)
    archive_tmp.unlink(missing_ok=True)


def _extract_archive(archive_path: Path, dest: Path) -> None:
    """
    Extract the downloaded archive into dest. Format inferred from suffix:
    .zip for Windows, .tar.gz for everything else.

    We reject any archive entry whose normalised path escapes dest — a
    cheap mitigation against the classic tarball traversal bug. Without
    OS code signing this matters more than usual: a compromised release
    asset is the only thing protecting us from arbitrary path writes.
    """
    name = archive_path.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as zf:
            for info in zf.infolist():
                _assert_safe_member(info.filename, dest)
            zf.extractall(dest)
        return

    # tar.gz / .tgz / .tar  — default for mac/linux.
    with tarfile.open(archive_path, "r:*") as tf:
        for member in tf.getmembers():
            _assert_safe_member(member.name, dest)
            # Refuse symlinks and hardlinks that escape dest too.
            if member.issym() or member.islnk():
                _assert_safe_member(member.linkname, dest)
        # Python 3.12+ tarfile takes a filter= argument; pass "data" when
        # available for an extra layer of safety. Older Pythons fall back
        # to our manual _assert_safe_member loop above.
        try:
            tf.extractall(dest, filter="data")     # type: ignore[arg-type]
        except TypeError:
            tf.extractall(dest)


def _assert_safe_member(name: str, dest: Path) -> None:
    if not name:
        raise RuntimeError("archive contained an unnamed member")
    if name.startswith("/") or name.startswith("\\"):
        raise RuntimeError(f"absolute path in archive: {name}")
    if ".." in Path(name).parts:
        raise RuntimeError(f"parent-dir traversal in archive: {name}")


# ── Version compare (mirrors backend/app/agent_gate.py + launcher) ────────────

def _cmp_version(a: str, b: str) -> int:
    """
    Same numeric tuple compare the launcher and backend use.
    Returns -1 / 0 / 1.
    """
    ta = _parse(a)
    tb = _parse(b)
    n = max(len(ta), len(tb))
    ta = ta + [0] * (n - len(ta))
    tb = tb + [0] * (n - len(tb))
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0


def _parse(s: str) -> list:
    out = []
    for part in (s or "").split("."):
        try:
            out.append(int(part))
        except ValueError:
            out.append(0)
    return out
