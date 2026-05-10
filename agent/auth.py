"""
Auth using Supabase Auth REST API (GoTrue).

Login flow:
  1. POST to Supabase /auth/v1/token?grant_type=password  → access + refresh tokens
  2. GET {SERVER_URL}/employees/me with the access token   → employee profile (id, full_name)

Tokens are stored in the OS keychain. An in-process cache prevents repeated
keychain prompts (macOS pops a dialog for every unsigned-binary read).

Cache rules:
  - Populated on login() / refresh_tokens() with freshly-received values.
  - Lazily populated on first read (one dialog per key, then memoized).
  - Cleared on logout().
"""

import keyring
import threading
from typing import Optional

import requests

from config import SERVER_URL, SUPABASE_URL, SUPABASE_ANON_KEY, KEYRING_SERVICE

_KEYS = ("access_token", "refresh_token", "employee_id", "full_name")
_cache: dict = {}
_lock = threading.Lock()

_SUPABASE_HEADERS = {
    "apikey": SUPABASE_ANON_KEY,
    "Content-Type": "application/json",
}


# ── Keychain wrappers ──────────────────────────────────────────────────────

def _store(key: str, value: str):
    keyring.set_password(KEYRING_SERVICE, key, value)
    with _lock:
        _cache[key] = value


def _load(key: str) -> Optional[str]:
    """Return cached value; otherwise read keychain once and memoize."""
    with _lock:
        if key in _cache:
            return _cache[key]
    value = keyring.get_password(KEYRING_SERVICE, key)
    with _lock:
        _cache[key] = value   # cache None too — prevents repeated prompts on misses
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
    """Authenticate via Supabase and persist tokens to keychain."""
    try:
        # ── Step 1: Authenticate with Supabase Auth ────────────────────────
        res = requests.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers=_SUPABASE_HEADERS,
            json={"email": email, "password": password},
            timeout=10,
        )
        if res.status_code != 200:
            return False

        tokens = res.json()
        access_token  = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        # ── Step 2: Fetch employee profile from our backend ────────────────
        profile_res = requests.get(
            f"{SERVER_URL}/employees/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if profile_res.status_code != 200:
            return False

        profile = profile_res.json()

        try:
            _store("access_token",  access_token)
            _store("refresh_token", refresh_token)
            _store("employee_id",   profile["id"])
            _store("full_name",     profile["full_name"])
        except Exception as e:
            print(f"[auth] Could not save credentials to keychain: {e}")
            _clear_cache()
            return False

        return True

    except requests.RequestException:
        return False


def refresh_tokens() -> bool:
    """Silently refresh the access token using the Supabase refresh token."""
    refresh_token = _load("refresh_token")
    if not refresh_token:
        return False

    try:
        res = requests.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
            headers=_SUPABASE_HEADERS,
            json={"refresh_token": refresh_token},
            timeout=10,
        )
        if res.status_code != 200:
            _clear_keychain()
            _clear_cache()
            return False

        data = res.json()
        _store("access_token",  data["access_token"])
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
    """Sign out from Supabase and wipe local credentials."""
    access_token = _load("access_token")
    if access_token:
        try:
            requests.post(
                f"{SUPABASE_URL}/auth/v1/logout",
                headers={
                    **_SUPABASE_HEADERS,
                    "Authorization": f"Bearer {access_token}",
                },
                timeout=5,
            )
        except Exception:
            pass
    _clear_keychain()
    _clear_cache()
