from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models import User, UserRole
from app.schemas import UserOut, UserCreate
from app.auth import require_admin, get_current_user, hash_password

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


@router.post("/", response_model=UserOut, status_code=201,
             dependencies=[Depends(require_admin)])
async def create_employee(body: UserCreate, db: AsyncSession = Depends(get_db)):
    # Password rule
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    # Email uniqueness
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Email already in use")

    # Force role to employee from this endpoint (admins are seeded via CLI)
    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=UserRole.employee,
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
