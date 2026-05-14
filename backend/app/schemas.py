from pydantic import BaseModel, EmailStr, Field
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


# ── Agent release manifest ────────────────────────────────────────────────────
# Platform key convention: GOOS-GOARCH (darwin-arm64, darwin-amd64,
# windows-amd64, linux-amd64). The agent computes its own key from
# platform.system() + platform.machine() and looks it up here.

class PlatformAsset(BaseModel):
    url: str                       # full download URL (GitHub Release asset)
    sha256: str = Field(min_length=64, max_length=64)   # hex-encoded SHA-256
    size: int = Field(gt=0)        # bytes — sanity check during download


class AgentReleaseOut(BaseModel):
    """Manifest returned to agents from GET /agent/version."""
    version: str
    min_supported: str
    released_at: datetime
    platforms: dict[str, PlatformAsset]
    signature: Optional[str] = None      # reserved — null until Ed25519 lands
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class AgentReleaseUpdate(BaseModel):
    """Payload from the CI release pipeline to publish a new manifest."""
    version: str
    min_supported: str
    platforms: dict[str, PlatformAsset]
    notes: Optional[str] = None


# ── Agent heartbeat ───────────────────────────────────────────────────────────
# Sent by the agent every ~10 min. We accept whatever shape the agent
# can plausibly produce and don't enforce ranges — heartbeats are
# diagnostic, not authoritative. Truncate-on-input on last_error is a
# DoS guard against a malformed agent that puts a megabyte of stack
# trace in there.

class HeartbeatPayload(BaseModel):
    agent_version: str = Field(min_length=1, max_length=32)
    os_platform: str = Field(min_length=1, max_length=64)
    status: str = Field(min_length=1, max_length=64)
    queue_size: int = Field(default=0, ge=0)
    pending_review: int = Field(default=0, ge=0)
    captures_today: int = Field(default=0, ge=0)
    last_capture_at: Optional[datetime] = None
    last_upload_ok: bool = True
    last_error: Optional[str] = Field(default=None, max_length=500)


class HeartbeatSummary(BaseModel):
    """One row per employee in GET /employees/heartbeats — the LATEST
    pulse, plus enough employee metadata to render the dashboard list
    without a second round-trip."""
    user_id: str
    full_name: str
    email: EmailStr
    is_active: bool

    # All null when the agent has never reported.
    agent_version: Optional[str] = None
    os_platform: Optional[str] = None
    status: Optional[str] = None
    queue_size: Optional[int] = None
    pending_review: Optional[int] = None
    captures_today: Optional[int] = None
    last_capture_at: Optional[datetime] = None
    last_upload_ok: Optional[bool] = None
    last_error: Optional[str] = None
    last_seen: Optional[datetime] = None      # recorded_at of latest heartbeat


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
