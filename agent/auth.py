"""
Auth and credential management.

Tokens live in the OS keychain. Reads are cached in memory after the
first hit so we don't trigger one keychain ACL prompt per UI refresh
(macOS pops a "Python wants to use your keychain" dialog for every
read on unsigned builds — that flooded the user with prompts).

Cache rules:
  - Populated on login() and refresh_tokens() with the values we just
    received from the backend.
  - On startup, populated lazily by the first read (one prompt per
    key, then memoized).
  - Cleared on logout().
"""

import keyring
import platform
import threading
from typing import Optional

import requests

from config import SERVER_URL, KEYRING_SERVICE

OS = platform.system()

_KEYS = ("access_token", "refresh_token", "employee_id", "full_name")
_cache: dict = {}
_lock = threading.Lock()


# ── Keychain wrappers ──────────────────────────────────────────────────────

def _store(key: str, value: str):
    # Update the cache only AFTER the keyring write succeeds. Otherwise
    # a failing keychain write would leave _cache out of sync with disk
    # (cache says "yes", keychain says no).
    keyring.set_password(KEYRING_SERVICE, key, value)
    with _lock:
        _cache[key] = value


def _load(key: str) -> Optional[str]:
    """Return cached value if we have one; otherwise hit keychain once."""
    with _lock:
        if key in _cache:
            return _cache[key]
    value = keyring.get_password(KEYRING_SERVICE, key)
    with _lock:
        _cache[key] = value  # cache None too — prevents re-prompts on misses
    return value


def _clear_keychain():
    for key in _KEYS:
        try:
            keyring.delete_password(KEYRING_SERVICE, key)
        except Exception:
            pass


def _clear_cache():
    with _lock:
        _cache.clear()


# ── Public API ─────────────────────────────────────────────────────────────

def login(email: str, password: str) -> bool:
    """Authenticate and persist tokens to OS keychain + cache."""
    try:
        res = requests.post(
            f"{SERVER_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        if res.status_code != 200:
            return False

        data = res.json()
        # Keyring writes can raise (denied, no backend, locked) — catch
        # and treat as a login failure rather than crashing the agent.
        try:
            _store("access_token", data["access_token"])
            _store("refresh_token", data["refresh_token"])
            _store("employee_id", data["employee_id"])
            _store("full_name", data["full_name"])
        except Exception as e:
            print(f"[auth] Could not save credentials to keychain: {e}")
            _clear_cache()
            return False
        return True
    except requests.RequestException:
        return False


def refresh_tokens() -> bool:
    """Silently refresh access token using refresh token."""
    refresh_token = _load("refresh_token")
    if not refresh_token:
        return False

    try:
        res = requests.post(
            f"{SERVER_URL}/auth/refresh",
            json={"refresh_token": refresh_token},
            timeout=10,
        )
        if res.status_code != 200:
            _clear_keychain()
            _clear_cache()
            return False

        data = res.json()
        _store("access_token", data["access_token"])
        _store("refresh_token", data["refresh_token"])
        return True
    except requests.RequestException:
        return False


def get_access_token() -> Optional[str]:
    return _load("access_token")


def get_employee_id() -> Optional[str]:
    return _load("employee_id")


def get_full_name() -> Optional[str]:
    return _load("full_name")


def is_logged_in() -> bool:
    return bool(_load("access_token") and _load("refresh_token"))


def logout():
    refresh_token = _load("refresh_token")
    if refresh_token:
        try:
            requests.post(
                f"{SERVER_URL}/auth/logout",
                json={"refresh_token": refresh_token},
                timeout=5,
            )
        except Exception:
            pass
    _clear_keychain()
    _clear_cache()
