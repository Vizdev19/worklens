"""
Organization management.

Public (no auth required):
  POST /orgs/     — self-service signup: create org + admin account via Supabase Auth.
                    Supabase sends the verification email automatically; no custom
                    email logic needed. The org record is created immediately — Supabase
                    blocks JWT issuance until the user confirms their email, so the API
                    is inaccessible until verification completes.

Authenticated:
  GET  /orgs/me   — get current org details (any role)
  PATCH /orgs/me  — update org config (admin only)
"""

import re
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx

from app.config import get_settings
from app.database import get_db
from app.models import Organization, Plan, User, UserRole
from app.schemas import OrgOut, OrgSignup, OrgUpdate
from app.auth import get_current_user, require_admin

settings = get_settings()
router = APIRouter(prefix="/orgs", tags=["Organizations"])

# Per-plan defaults applied at org creation time
_PLAN_DEFAULTS: dict[str, dict] = {
    "free":       {"max_seats": 3,    "retention_days": 7},
    "starter":    {"max_seats": 25,   "retention_days": 30},
    "pro":        {"max_seats": 200,  "retention_days": 90},
    "enterprise": {"max_seats": 9999, "retention_days": 365},
}

_VALID_PLANS = set(_PLAN_DEFAULTS)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    """Convert a company name to a URL-safe slug."""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-")[:50] or "org"


# ── Public endpoints ─────────────────────────────────────────────────────────

@router.post("/", status_code=201)
async def signup(
    body: OrgSignup,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new organization and its first admin account.

    Flow:
    1. Call Supabase Admin API → creates auth user, Supabase sends confirmation email.
    2. Create Organization + User profile in our DB (IDs linked by Supabase UUID).
    3. Return a 201 — the user must verify their email before they can log in.
       (Supabase won't issue a JWT until email_confirmed_at is set.)
    """
    plan = body.plan if body.plan in _VALID_PLANS else "free"
    defaults = _PLAN_DEFAULTS[plan]

    # ── Email uniqueness (local check first to avoid unnecessary Supabase calls) ──
    existing = (
        await db.execute(select(User).where(User.email == body.email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    # ── Unique slug ─────────────────────────────────────────────────────────────
    base_slug = _slugify(body.company_name)
    slug = base_slug
    if (await db.execute(
        select(Organization).where(Organization.slug == slug)
    )).scalar_one_or_none():
        slug = f"{base_slug}-{secrets.token_hex(3)}"

    # ── Create auth user in Supabase ─────────────────────────────────────────
    # email_confirm=False → Supabase queues a confirmation email automatically.
    # The user cannot log in (get a valid JWT) until they click the link.
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{settings.supabase_url}/auth/v1/admin/users",
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
            },
            json={
                "email": body.email,
                "password": body.password,
                "email_confirm": False,   # Supabase sends verification email
                "options": {
                    # After the user clicks the link, Supabase redirects to the
                    # DASHBOARD's /auth/callback (the marketing site has no such
                    # route). settings.dashboard_url accepts either
                    # DASHBOARD_URL or the legacy FRONTEND_URL env var; see
                    # app/config.py for the alias rules.
                    # Must be listed in Supabase → Auth → Allowed Redirect URLs.
                    "email_redirect_to": f"{settings.dashboard_url}/auth/callback",
                },
            },
        )

    if resp.status_code == 422:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail="Auth service temporarily unavailable. Please try again.",
        )

    supabase_id: str = resp.json()["id"]

    # ── Create org and admin profile ─────────────────────────────────────────
    # CB-6/ARCH-2: If any DB step fails we must delete the Supabase auth user
    # to avoid a permanent orphan (a Supabase user with no local profile means
    # the email address is permanently blocked from re-registering).
    async def _delete_supabase_user(uid: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                await c.delete(
                    f"{settings.supabase_url}/auth/v1/admin/users/{uid}",
                    headers={
                        "apikey": settings.supabase_service_key,
                        "Authorization": f"Bearer {settings.supabase_service_key}",
                    },
                )
        except Exception:
            pass  # best-effort; log in production

    try:
        org = Organization(
            name=body.company_name,
            slug=slug,
            plan=plan,
            is_active=True,   # Supabase guards login; no need for our own gate
            max_seats=defaults["max_seats"],
            retention_days=defaults["retention_days"],
        )
        db.add(org)
        await db.flush()          # resolves org.id

        user = User(
            id=supabase_id,       # must match Supabase UUID for JWT → profile lookup
            email=body.email,
            full_name=body.admin_name,
            role=UserRole.admin,
            org_id=org.id,
        )
        db.add(user)
        await db.flush()          # resolves user.id

        org.owner_id = user.id
    except Exception:
        # Roll back the DB transaction and clean up the Supabase auth user
        # so the email address is not permanently locked.
        await db.rollback()
        await _delete_supabase_user(supabase_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to create organization. Please try again.",
        )

    return {
        "message": (
            "Account created. Please check your email to verify your address "
            "before logging in."
        ),
        "email": body.email,
        "org_id": org.id,
    }


# ── Authenticated endpoints ───────────────────────────────────────────────────

@router.get("/me", response_model=OrgOut)
async def get_my_org(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's organization details."""
    if not current_user.org_id:
        raise HTTPException(status_code=404, detail="No organization associated with this account.")

    org = (
        await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    ).scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    return org


@router.patch("/me", response_model=OrgOut)
async def update_my_org(
    body: OrgUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin only: update the org's name and per-org agent config."""
    org = (
        await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    ).scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(org, field, value)

    await db.flush()
    return org
