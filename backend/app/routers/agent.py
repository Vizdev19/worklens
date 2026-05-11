"""
Agent lifecycle endpoints.

Currently:
  GET  /agent/version  — public manifest fetched by every running agent
  POST /agent/version  — CI-only; publishes a new manifest

Why a dedicated router (vs. tacking onto /orgs or /employees):
  - Public read; no JWT required. Mixing with the auth-gated routers would
    risk a future middleware-style dependency accidentally locking it down.
  - Future siblings (/agent/heartbeat, /agent/config) will all share the
    same auth model — Bearer JWT from the agent user, not the org admin.
    Keeping them together makes that consistent.

The release row uses a "single-row-per-channel" pattern: id = "stable".
Adding beta/canary later is purely additive (new row), no schema change.
"""

import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import AgentRelease
from app.schemas import AgentReleaseOut, AgentReleaseUpdate

router = APIRouter(prefix="/agent", tags=["Agent"])
settings = get_settings()

# Channel name for the single supported release stream.
# Beta/canary would live under different IDs in the same table.
STABLE_CHANNEL = "stable"

# Tell intermediaries (and the agent's HTTP client, if it respects this)
# to cache the manifest. Reduces traffic when 1000s of agents poll on
# the same Monday-morning login spike. 600s = 10 min.
_MANIFEST_CACHE_SECONDS = 600


@router.get("/version", response_model=AgentReleaseOut)
async def get_agent_version(
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Public — every agent polls this hourly (with jitter) to discover updates.

    Returns 404 when no release has been published yet (fresh install, dev env).
    Agents treat 404 as "no update available" and keep running.
    """
    release = (await db.execute(
        select(AgentRelease).where(AgentRelease.id == STABLE_CHANNEL)
    )).scalar_one_or_none()

    if release is None:
        raise HTTPException(
            status_code=404,
            detail="No agent release published for this channel.",
        )

    response.headers["Cache-Control"] = f"public, max-age={_MANIFEST_CACHE_SECONDS}"
    return release


@router.post("/version", response_model=AgentReleaseOut, status_code=200)
async def publish_agent_version(
    body: AgentReleaseUpdate,
    x_release_key: Optional[str] = Header(default=None, alias="X-Release-Key"),
    db: AsyncSession = Depends(get_db),
):
    """
    Publish a new release manifest. Called only by the CI release workflow
    after building and uploading platform binaries to GitHub Releases.

    Auth: a constant-time-compared bearer token in X-Release-Key. We
    deliberately do NOT reuse Supabase JWTs here — the CI job has no user
    identity, and we don't want a stolen admin token to be able to push
    a malicious agent build to every install.

    Idempotent: re-POSTing the same manifest just overwrites the row.
    """
    if not settings.agent_release_key:
        # Endpoint is disabled until the env var is configured. This avoids
        # accidentally exposing a write surface in any dev environment that
        # forgets to set the secret.
        raise HTTPException(
            status_code=503,
            detail="Release publishing is disabled (AGENT_RELEASE_KEY unset).",
        )
    if not x_release_key or not secrets.compare_digest(x_release_key, settings.agent_release_key):
        raise HTTPException(status_code=401, detail="Invalid release key.")

    if not body.platforms:
        raise HTTPException(status_code=400, detail="At least one platform asset required.")

    # Upsert the row. Single-row-per-channel pattern; no race risk because
    # this endpoint is only ever hit by one CI job at a time.
    existing = (await db.execute(
        select(AgentRelease).where(AgentRelease.id == STABLE_CHANNEL)
    )).scalar_one_or_none()

    # Pydantic models → plain dicts for JSONB storage
    platforms_payload = {
        key: asset.model_dump() for key, asset in body.platforms.items()
    }

    if existing is None:
        release = AgentRelease(
            id=STABLE_CHANNEL,
            version=body.version,
            min_supported=body.min_supported,
            platforms=platforms_payload,
            notes=body.notes,
            released_at=datetime.now(timezone.utc),
        )
        db.add(release)
    else:
        existing.version = body.version
        existing.min_supported = body.min_supported
        existing.platforms = platforms_payload
        existing.notes = body.notes
        existing.released_at = datetime.now(timezone.utc)
        release = existing

    await db.flush()
    return release
