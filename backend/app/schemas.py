from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.models import UserRole


# ── Auth ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    employee_id: str
    full_name: str
    role: UserRole

class RefreshRequest(BaseModel):
    refresh_token: str


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
