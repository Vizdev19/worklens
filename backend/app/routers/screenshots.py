from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.database import get_db
from app.models import Screenshot, User, DeletionLog
from app.schemas import ScreenshotOut, ScreenshotListResponse, DeletionLogCreate, DeletionLogOut
from app.auth import get_current_user, require_admin
from app.agent_gate import require_min_agent_version
from app.storage import (
    upload_screenshot,
    get_signed_urls_batch,
    SIGNED_URL_TTL_SECONDS,
)

router = APIRouter(prefix="/screenshots", tags=["Screenshots"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}

# Refresh stored signed URL when it has less than this remaining
URL_REFRESH_THRESHOLD_SECONDS = 60 * 60  # 1 hour
# Reject screenshots claiming a captured_at outside this window
CAPTURED_AT_PAST_TOLERANCE = timedelta(hours=24)
CAPTURED_AT_FUTURE_TOLERANCE = timedelta(minutes=5)


def _assert_org(admin: User) -> str:
    """Return org_id or raise 403 for org-less bootstrap admins."""
    if not admin.org_id:
        raise HTTPException(
            status_code=403,
            detail="Your account is not associated with an organization.",
        )
    return admin.org_id


@router.post("/upload", response_model=ScreenshotOut)
async def upload(
    file: UploadFile = File(...),
    captured_at: str = Form(...),         # ISO format: 2024-01-01T10:00:00Z
    monitor_index: int = Form(0),
    os_platform: str = Form(...),         # Windows / Darwin / Linux
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    # Force-update gate — 426 before we touch storage if agent is below
    # the published min_supported version. Return value is the agent's
    # reported version, available for telemetry once heartbeats land.
    _agent_version: str = Depends(require_min_agent_version),
):
    # Validate file type
    content_type = file.content_type or "image/jpeg"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG allowed")

    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    # Parse timestamp
    try:
        captured_dt = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid captured_at format")

    # Reject suspicious timestamps (clock skew or backdating attempts)
    now = datetime.now(timezone.utc)
    if captured_dt > now + CAPTURED_AT_FUTURE_TOLERANCE:
        raise HTTPException(status_code=400, detail="captured_at is in the future")
    if captured_dt < now - CAPTURED_AT_PAST_TOLERANCE:
        raise HTTPException(status_code=400, detail="captured_at is too far in the past")

    # Upload to Supabase Storage
    storage_result = await upload_screenshot(
        file_bytes=file_bytes,
        employee_id=current_user.id,
        captured_at=captured_dt,
        monitor_index=monitor_index,
        content_type=content_type,
    )

    # Save metadata — tag with org_id so admin queries can filter without a join
    screenshot = Screenshot(
        user_id=current_user.id,
        org_id=current_user.org_id,          # SEC-2/CB-3: populate for tenant scoping
        file_path=storage_result["file_path"],
        file_url=storage_result["file_url"],
        thumbnail_path=storage_result.get("thumbnail_path"),
        thumbnail_url=storage_result.get("thumbnail_url"),
        file_size=len(file_bytes),
        monitor_index=monitor_index,
        os_platform=os_platform,
        captured_at=captured_dt,
    )
    db.add(screenshot)
    await db.flush()
    return screenshot


@router.get("/", response_model=ScreenshotListResponse)
async def list_screenshots(
    employee_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_admin: User = Depends(require_admin),   # SEC-2: need the admin's org_id
    db: AsyncSession = Depends(get_db),
):
    org_id = _assert_org(current_admin)

    # Always scope to the admin's org first — this is the tenant boundary.
    filters = [Screenshot.org_id == org_id]

    if employee_id:
        # Validate the requested employee actually belongs to this org
        # to prevent admins guessing UUIDs from other orgs.
        emp = (await db.execute(
            select(User).where(User.id == employee_id, User.org_id == org_id)
        )).scalar_one_or_none()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        filters.append(Screenshot.user_id == employee_id)

    if date_from:
        filters.append(Screenshot.captured_at >= date_from)
    if date_to:
        filters.append(Screenshot.captured_at <= date_to)

    total = (await db.execute(
        select(func.count()).select_from(Screenshot).where(and_(*filters))
    )).scalar()

    items = (await db.execute(
        select(Screenshot)
        .where(and_(*filters))
        .order_by(Screenshot.captured_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    # Refresh stale signed URLs in a single batch call
    now = datetime.now(timezone.utc)
    refresh_cutoff = now - timedelta(
        seconds=SIGNED_URL_TTL_SECONDS - URL_REFRESH_THRESHOLD_SECONDS
    )
    stale = [i for i in items if i.uploaded_at < refresh_cutoff]
    all_stale_paths = (
        [i.file_path for i in stale]
        + [i.thumbnail_path for i in stale if i.thumbnail_path]
    )

    if all_stale_paths:
        new_urls = await get_signed_urls_batch(all_stale_paths)
        for item in stale:
            if item.file_path in new_urls:
                item.file_url = new_urls[item.file_path]
            if item.thumbnail_path and item.thumbnail_path in new_urls:
                item.thumbnail_url = new_urls[item.thumbnail_path]

    return ScreenshotListResponse(total=total, items=items)


@router.post("/deletion-log", response_model=DeletionLogOut)
async def log_deletion(
    body: DeletionLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _agent_version: str = Depends(require_min_agent_version),
):
    """
    Called by the agent when an employee removes a screenshot during review.
    Records the event for admin audit without storing any image content.
    """
    entry = DeletionLog(
        user_id=current_user.id,
        org_id=current_user.org_id,          # SEC-5/CB-3: tag with org for scoped queries
        captured_at=body.captured_at,
        monitor_index=body.monitor_index,
    )
    db.add(entry)
    await db.flush()
    return entry


@router.get("/deletion-log", response_model=list[DeletionLogOut])
async def list_deletions(
    employee_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_admin: User = Depends(require_admin),   # SEC-5: need the admin's org_id
    db: AsyncSession = Depends(get_db),
):
    """Admin view: which screenshots were removed by employees before upload."""
    org_id = _assert_org(current_admin)

    # Always scope to the admin's org first
    filters = [DeletionLog.org_id == org_id]

    if employee_id:
        # Validate the employee belongs to this org before filtering by them
        emp = (await db.execute(
            select(User).where(User.id == employee_id, User.org_id == org_id)
        )).scalar_one_or_none()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        filters.append(DeletionLog.user_id == employee_id)

    if date_from:
        filters.append(DeletionLog.captured_at >= date_from)
    if date_to:
        filters.append(DeletionLog.captured_at <= date_to)

    items = (await db.execute(
        select(DeletionLog)
        .where(and_(*filters))
        .order_by(DeletionLog.deleted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()
    return items


@router.get("/my", response_model=ScreenshotListResponse)
async def my_screenshots(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Employee endpoint — only ever returns that employee's own screenshots."""
    total = (await db.execute(
        select(func.count()).select_from(Screenshot)
        .where(Screenshot.user_id == current_user.id)
    )).scalar()

    items = (await db.execute(
        select(Screenshot)
        .where(Screenshot.user_id == current_user.id)
        .order_by(Screenshot.captured_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return ScreenshotListResponse(total=total, items=items)
