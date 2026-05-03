from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.models import Screenshot, User
from app.schemas import ScreenshotOut, ScreenshotListResponse
from app.auth import get_current_user, require_admin
from app.storage import upload_screenshot, get_signed_url

router = APIRouter(prefix="/screenshots", tags=["Screenshots"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload", response_model=ScreenshotOut)
async def upload(
    file: UploadFile = File(...),
    captured_at: str = Form(...),         # ISO format: 2024-01-01T10:00:00Z
    monitor_index: int = Form(0),
    os_platform: str = Form(...),         # Windows / Darwin / Linux
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate file type
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Only JPEG/PNG allowed")

    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    # Parse timestamp
    try:
        captured_dt = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid captured_at format")

    # Upload to Supabase Storage
    storage_result = await upload_screenshot(
        file_bytes=file_bytes,
        employee_id=current_user.id,
        captured_at=captured_dt,
        monitor_index=monitor_index,
    )

    # Save metadata to PostgreSQL
    screenshot = Screenshot(
        user_id=current_user.id,
        file_path=storage_result["file_path"],
        file_url=storage_result["file_url"],
        file_size=len(file_bytes),
        monitor_index=monitor_index,
        os_platform=os_platform,
        captured_at=captured_dt,
    )
    db.add(screenshot)
    await db.flush()
    return screenshot


@router.get("/", response_model=ScreenshotListResponse, dependencies=[Depends(require_admin)])
async def list_screenshots(
    employee_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if employee_id:
        filters.append(Screenshot.user_id == employee_id)
    if date_from:
        filters.append(Screenshot.captured_at >= date_from)
    if date_to:
        filters.append(Screenshot.captured_at <= date_to)

    count_q = select(func.count()).select_from(Screenshot)
    if filters:
        count_q = count_q.where(and_(*filters))
    total = (await db.execute(count_q)).scalar()

    q = select(Screenshot).order_by(Screenshot.captured_at.desc())
    if filters:
        q = q.where(and_(*filters))
    q = q.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(q)).scalars().all()

    # Refresh signed URLs before returning
    for item in items:
        item.file_url = get_signed_url(item.file_path)

    return ScreenshotListResponse(total=total, items=items)


@router.get("/my", response_model=ScreenshotListResponse)
async def my_screenshots(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total = (await db.execute(
        select(func.count()).select_from(Screenshot)
        .where(Screenshot.user_id == current_user.id)
    )).scalar()

    items = (await db.execute(
        select(Screenshot)
        .where(Screenshot.user_id == current_user.id)
        .order_by(Screenshot.captured_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return ScreenshotListResponse(total=total, items=items)
