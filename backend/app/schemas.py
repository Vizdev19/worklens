from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.models import UserRole


# ── Users ────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.employee

class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    org_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Screenshots ───────────────────────────────────────────────────────────────

class ScreenshotOut(BaseModel):
    id: str
    user_id: str
    file_url: str
    thumbnail_url: Optional[str] = None
    file_size: Optional[int]
    monitor_index: int
    os_platform: Optional[str]
    captured_at: datetime
    uploaded_at: datetime

    class Config:
        from_attributes = True

class ScreenshotListResponse(BaseModel):
    total: int
    items: list[ScreenshotOut]


# ── Organizations ────────────────────────────────────────────────────────────

class OrgSignup(BaseModel):
    company_name: str
    admin_name: str
    email: EmailStr
    password: str
    plan: str = "free"   # free | starter | pro | enterprise

class OrgOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    is_active: bool
    max_seats: int
    capture_interval_minutes: int
    review_window_minutes: int
    idle_skip_minutes: int
    retention_days: int
    onboarding_done: bool = False
    trial_ends_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class OrgUpdate(BaseModel):
    name: Optional[str] = None
    capture_interval_minutes: Optional[int] = None
    review_window_minutes: Optional[int] = None
    idle_skip_minutes: Optional[int] = None
    onboarding_done: Optional[bool] = None


# ── Deletion log ──────────────────────────────────────────────────────────────

class DeletionLogCreate(BaseModel):
    captured_at: datetime
    monitor_index: int = 0

class DeletionLogOut(BaseModel):
    id: str
    user_id: str
    captured_at: datetime
    monitor_index: int
    deleted_at: datetime

    class Config:
        from_attributes = True
