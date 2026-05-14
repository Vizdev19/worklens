from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import httpx

from app.config import get_settings
from app.database import get_db
from app.models import AgentHeartbeat, Organization, User, UserRole
from app.schemas import HeartbeatSummary, UserOut, UserCreate
from app.auth import require_admin, get_current_user

settings = get_settings()
router = APIRouter(prefix="/employees", tags=["Employees"])


def _assert_org(admin: User) -> str:
    """
    Return the admin's org_id, or raise 403 if the account has no org.

    Bootstrap admins created via the CLI before org signup exist without
    an org_id. They must complete the org signup flow before managing employees.
    """
    if not admin.org_id:
        raise HTTPException(
            status_code=403,
            detail="Your account is not associated with an organization. "
                   "Complete the org setup at /onboarding first.",
        )
    return admin.org_id


@router.get("/", response_model=list[UserOut])
async def list_employees(
    is_active: Optional[bool] = Query(None),
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    org_id = _assert_org(current_admin)
    q = select(User).where(
        User.role == UserRole.employee,
        User.org_id == org_id,           # SEC-1: only this org's employees
    )
    if is_active is not None:
        q = q.where(User.is_active == is_active)
    result = await db.execute(q.order_by(User.full_name))
    return result.scalars().all()


@router.get("/heartbeats", response_model=list[HeartbeatSummary])
async def list_employee_heartbeats(
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Latest heartbeat per employee in the calling admin's org, joined onto
    the employee's profile so the dashboard can render one row per person
    with one API call.

    Strategy: a window-functioned subquery over agent_heartbeats picks
    `recorded_at DESC LIMIT 1 per user_id`, then we LEFT JOIN that onto
    users so employees who've never pinged still appear (with all
    heartbeat fields null). The composite index on
    (user_id, recorded_at DESC) makes the row-pick a single index lookup
    per employee.

    NB: this is an admin-only / org-scoped surface. Employees calling
    /employees/me get only their own profile via a different endpoint;
    they have no reason to see anyone else's agent state.
    """
    org_id = _assert_org(current_admin)

    # Window function over heartbeats: rank rows newest-first per user,
    # filter to rank=1. Avoids GROUP BY + the "pick a non-aggregate
    # alongside max(recorded_at)" Postgres dance.
    latest = (
        select(
            AgentHeartbeat,
            func.row_number().over(
                partition_by=AgentHeartbeat.user_id,
                order_by=AgentHeartbeat.recorded_at.desc(),
            ).label("rn"),
        )
        # Scope to the admin's org. Mirrors the same pattern as Screenshot.
        .where(AgentHeartbeat.org_id == org_id)
        .subquery()
    )
    latest_q = select(latest).where(latest.c.rn == 1).subquery()

    # LEFT JOIN so employees with no heartbeat at all still surface
    # as "never seen" rows (all hb_* fields will be NULL).
    rows = (await db.execute(
        select(
            User,
            latest_q.c.agent_version,
            latest_q.c.os_platform,
            latest_q.c.status,
            latest_q.c.queue_size,
            latest_q.c.pending_review,
            latest_q.c.captures_today,
            latest_q.c.last_capture_at,
            latest_q.c.last_upload_ok,
            latest_q.c.last_error,
            latest_q.c.recorded_at,
        )
        .outerjoin(latest_q, User.id == latest_q.c.user_id)
        .where(
            User.role == UserRole.employee,
            User.org_id == org_id,
        )
        .order_by(User.full_name)
    )).all()

    return [
        HeartbeatSummary(
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            is_active=user.is_active,
            agent_version=agent_version,
            os_platform=os_platform,
            status=status,
            queue_size=queue_size,
            pending_review=pending_review,
            captures_today=captures_today,
            last_capture_at=last_capture_at,
            last_upload_ok=last_upload_ok,
            last_error=last_error,
            last_seen=recorded_at,
        )
        for (user, agent_version, os_platform, status, queue_size,
             pending_review, captures_today, last_capture_at,
             last_upload_ok, last_error, recorded_at) in rows
    ]


@router.post("/", response_model=UserOut, status_code=201)
async def create_employee(
    body: UserCreate,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Admin creates a new employee account.

    1. Creates the Supabase Auth user (email auto-confirmed — admin-provisioned).
    2. Inserts a local profile row whose id matches the Supabase UUID.
    The employee can immediately sign in via the agent; no email verification needed.
    """
    org_id = _assert_org(current_admin)

    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    # ARCH-7: enforce plan seat limit before touching Supabase
    org = (await db.execute(
        select(Organization).where(Organization.id == org_id)
    )).scalar_one_or_none()
    if org is None:
        raise HTTPException(500, "Organization record not found")

    active_count = (await db.execute(
        select(func.count()).select_from(User).where(
            User.org_id == org_id,
            User.role == UserRole.employee,
            User.is_active == True,   # noqa: E712
        )
    )).scalar() or 0

    if active_count >= org.max_seats:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Seat limit reached ({active_count}/{org.max_seats}). "
                "Upgrade your plan to add more employees."
            ),
        )

    # ── Create auth user in Supabase ─────────────────────────────────────────
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
                "email_confirm": True,   # admin-created accounts skip email verification
            },
        )

    if resp.status_code == 422:
        raise HTTPException(409, "Email already in use")
    if resp.status_code >= 400:
        raise HTTPException(502, f"Auth service error: {resp.text}")

    supabase_id: str = resp.json()["id"]

    # ── Create local profile ─────────────────────────────────────────────────
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        # Supabase user was created but local profile already exists — clean up
        # the Supabase user to avoid an orphan.
        async with httpx.AsyncClient(timeout=10) as client:
            await client.delete(
                f"{settings.supabase_url}/auth/v1/admin/users/{supabase_id}",
                headers={
                    "apikey": settings.supabase_service_key,
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                },
            )
        raise HTTPException(409, "Email already registered locally")

    user = User(
        id=supabase_id,          # UUID from Supabase — must match for JWT → profile lookup
        email=body.email,
        full_name=body.full_name,
        role=UserRole.employee,  # force employee role; admins come via org signup
        org_id=org_id,           # scoped to the creating admin's org
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/{employee_id}", response_model=UserOut)
async def get_employee(
    employee_id: str,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    org_id = _assert_org(current_admin)
    result = await db.execute(
        select(User).where(
            User.id == employee_id,
            User.org_id == org_id,       # SEC-3: only look up employees in this org
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    return user


@router.patch("/{employee_id}/deactivate")
async def deactivate_employee(
    employee_id: str,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    org_id = _assert_org(current_admin)
    result = await db.execute(
        select(User).where(
            User.id == employee_id,
            User.org_id == org_id,       # SEC-4: only deactivate employees in this org
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    user.is_active = False
    return {"detail": f"{user.full_name} deactivated"}


@router.patch("/{employee_id}/activate")
async def activate_employee(
    employee_id: str,
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    org_id = _assert_org(current_admin)
    result = await db.execute(
        select(User).where(
            User.id == employee_id,
            User.org_id == org_id,       # SEC-4: only activate employees in this org
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    user.is_active = True
    return {"detail": f"{user.full_name} activated"}
