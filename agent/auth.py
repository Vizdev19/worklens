import keyring
import requests
import json
import platform
from datetime import datetime, timezone
from config import SERVER_URL, KEYRING_SERVICE

OS = platform.system()


def _store(key: str, value: str):
    keyring.set_password(KEYRING_SERVICE, key, value)

def _load(key: str) -> str | None:
    return keyring.get_password(KEYRING_SERVICE, key)

def _clear():
    for key in ("access_token", "refresh_token", "employee_id", "full_name"):
        try:
            keyring.delete_password(KEYRING_SERVICE, key)
        except Exception:
            pass


def login(email: str, password: str) -> bool:
    """Authenticate and persist tokens to OS keychain."""
    try:
        res = requests.post(
            f"{SERVER_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        if res.status_code != 200:
            return False

        data = res.json()
        _store("access_token", data["access_token"])
        _store("refresh_token", data["refresh_token"])
        _store("employee_id", data["employee_id"])
        _store("full_name", data["full_name"])
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
            _clear()
            return False

        data = res.json()
        _store("access_token", data["access_token"])
        _store("refresh_token", data["refresh_token"])
        return True
    except requests.RequestException:
        return False


def get_access_token() -> str | None:
    return _load("access_token")

def get_employee_id() -> str | None:
    return _load("employee_id")

def get_full_name() -> str | None:
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
    _clear()
