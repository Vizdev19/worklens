from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import httpx

from app.config import get_settings
from app.database import get_db
from app.models import User, UserRole
from app.schemas import UserOut, UserCreate
from app.auth import require_admin, get_current_user

settings = get_settings()
router = APIRouter(prefix="/employees", tags=["Employees"])


@router.get("/", response_model=list[UserOut], dependencies=[Depends(require_admin)])
async def list_employees(
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(User).where(User.role == UserRole.employee)
    if is_active is not None:
        q = q.where(User.is_active == is_active)
    result = await db.execute(q.order_by(User.full_name))
    return result.scalars().all()


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
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

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
        raise HTTPException(409, "Email already registered locally")

    user = User(
        id=supabase_id,          # UUID from Supabase — must match for JWT → profile lookup
        email=body.email,
        full_name=body.full_name,
        role=UserRole.employee,  # force employee role; admins come via org signup
        org_id=current_admin.org_id,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/{employee_id}", response_model=UserOut, dependencies=[Depends(require_admin)])
async def get_employee(employee_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == employee_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    return user


@router.patch("/{employee_id}/deactivate", dependencies=[Depends(require_admin)])
async def deactivate_employee(employee_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == employee_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    user.is_active = False
    return {"detail": f"{user.full_name} deactivated"}


@router.patch("/{employee_id}/activate", dependencies=[Depends(require_admin)])
async def activate_employee(employee_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == employee_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    user.is_active = True
    return {"detail": f"{user.full_name} activated"}
