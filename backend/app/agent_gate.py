"""
Server-side enforcement of the minimum agent version.

The agent sends `X-Agent-Version: 1.2.0` on every upload-class request.
This module exposes a FastAPI dependency that compares that header against
the currently-published manifest's `min_supported` field and returns
HTTP 426 ("Upgrade Required") when the agent is too old.

The 426 response is the only mechanism that forces an in-field agent to
update — without it, a CVE patch in pynput or a breaking change to the
upload API would simply break every old install silently.

Design notes
------------
* The manifest is read from the DB on demand and memoized for a short
  window (60 s). We don't want to round-trip per upload, but we also want
  a manifest change to take effect within a minute — fast enough that
  someone hot-fixing a CVE doesn't have to bounce the server.

* "No manifest published yet" is treated as "no minimum" rather than
  "reject everything", so dev environments without a seeded release row
  keep working.

* Agents that don't send the header at all are treated as version
  "0.0.0" — the oldest possible. This makes pre-Phase-2 agents (1.1.3)
  fail fast the moment min_supported moves above 0.0.0, which is the
  deprecation behaviour we picked for the existing 1.1.3 installs.

* The 426 body uses the {"detail": <dict>} shape that FastAPI emits for
  HTTPException(detail=dict). The agent only reads `min_supported` from
  it; the X-Min-Agent-Version header is a redundant signal that's easier
  to log from infra (CDN/WAF) without parsing the body.
"""

import time
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AgentRelease

STABLE_CHANNEL = "stable"
_CACHE_TTL_SECONDS = 60

# Module-level memo. {value, expires_at_monotonic}. The TTL is short
# enough that we don't need invalidation on POST /agent/version.
_min_supported_cache: dict = {"value": None, "expires_at": 0.0}


def _parse_version(s: str) -> tuple:
    """
    Convert "1.10.2" → (1, 10, 2). Non-numeric or malformed components
    coerce to 0 so we never crash on garbage input — we just sort it
    pessimistically (older than anything well-formed).
    """
    parts = []
    for component in s.split("."):
        try:
            parts.append(int(component))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _compare_versions(a: str, b: str) -> int:
    """Return -1/0/1 like the C strcmp convention."""
    ta = _parse_version(a)
    tb = _parse_version(b)
    # Pad the shorter tuple with zeros so "1.2" == "1.2.0".
    n = max(len(ta), len(tb))
    ta = ta + (0,) * (n - len(ta))
    tb = tb + (0,) * (n - len(tb))
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0


async def _get_cached_min_supported(db: AsyncSession) -> Optional[str]:
    """
    Read the stable channel's min_supported field, cached for 60s.
    Returns None when no manifest exists — the caller treats that as
    "no minimum" and lets everything through.
    """
    now = time.monotonic()
    if now < _min_supported_cache["expires_at"]:
        return _min_supported_cache["value"]

    release = (await db.execute(
        select(AgentRelease).where(AgentRelease.id == STABLE_CHANNEL)
    )).scalar_one_or_none()

    value = release.min_supported if release else None
    # Cache None too — prevents a stampede on dev envs with no manifest.
    _min_supported_cache["value"] = value
    _min_supported_cache["expires_at"] = now + _CACHE_TTL_SECONDS
    return value


async def require_min_agent_version(
    x_agent_version: Optional[str] = Header(default=None, alias="X-Agent-Version"),
    db: AsyncSession = Depends(get_db),
) -> str:
    """
    FastAPI dependency. Apply to any route that's called by the agent and
    that we want to gate on version (uploads, heartbeats, etc.).

    Returns the agent's reported version on success — handlers can record
    it for telemetry. Raises 426 when too old.
    """
    min_required = await _get_cached_min_supported(db)

    # No manifest published — dev env or before first release.
    if min_required is None:
        return x_agent_version or "0.0.0"

    reported = x_agent_version or "0.0.0"

    if _compare_versions(reported, min_required) < 0:
        raise HTTPException(
            status_code=426,
            detail={
                "message": (
                    f"Agent version {reported} is no longer supported. "
                    f"Minimum required: {min_required}. Please update."
                ),
                "min_supported": min_required,
                "current": reported,
            },
            headers={"X-Min-Agent-Version": min_required},
        )

    return reported
