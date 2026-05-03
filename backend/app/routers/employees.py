from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models import User, UserRole
from app.schemas import UserOut
from app.auth import require_admin, get_current_user

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
