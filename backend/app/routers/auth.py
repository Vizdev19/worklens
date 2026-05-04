from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.database import get_db
from app.models import User, RefreshToken
from app.schemas import LoginRequest, TokenResponse, RefreshRequest, UserCreate, UserOut
from app.auth import (
    verify_password, hash_password,
    create_access_token, create_refresh_token,
    save_refresh_token, require_admin, get_current_user
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token()
    await save_refresh_token(user.id, refresh_token, db)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        employee_id=user.id,
        full_name=user.full_name,
        role=user.role,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token == body.refresh_token)
    )
    db_token = result.scalar_one_or_none()

    if not db_token or db_token.is_revoked:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if db_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user_result = await db.execute(select(User).where(User.id == db_token.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists")
    if not user.is_active:
        # Revoke and refuse — disabled accounts can't refresh
        db_token.is_revoked = True
        raise HTTPException(status_code=403, detail="Account is disabled")

    # Rotate: revoke old, issue new
    db_token.is_revoked = True

    new_access = create_access_token(user.id, user.role)
    new_refresh = create_refresh_token()
    await save_refresh_token(user.id, new_refresh, db)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        employee_id=user.id,
        full_name=user.full_name,
        role=user.role,
    )


@router.post("/logout")
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token == body.refresh_token)
    )
    db_token = result.scalar_one_or_none()
    if db_token:
        db_token.is_revoked = True
    return {"detail": "Logged out successfully"}


# ── Admin: create employee accounts ──────────────────────────────────────────

@router.post("/register", response_model=UserOut, dependencies=[Depends(require_admin)])
async def register_employee(body: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
    )
    db.add(user)
    await db.flush()
    return user
