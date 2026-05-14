from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, BigInteger,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    admin = "admin"
    employee = "employee"


class Plan(str, enum.Enum):
    free       = "free"
    starter    = "starter"
    pro        = "pro"
    enterprise = "enterprise"


class Organization(Base):
    __tablename__ = "organizations"

    id   = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    plan = Column(SAEnum(Plan), default=Plan.free, nullable=False)
    # Active by default; Supabase Auth blocks login until email is verified,
    # so we don't need our own is_active=False gate at org creation time.
    is_active = Column(Boolean, default=True)

    # Per-org agent config (server-driven; pushed to agents)
    capture_interval_minutes = Column(Integer, default=10)
    review_window_minutes    = Column(Integer, default=5)
    idle_skip_minutes        = Column(Integer, default=5)
    retention_days           = Column(Integer, default=7)    # free-tier default

    # Billing
    max_seats = Column(Integer, default=3)   # free-tier default

    # Stripe (nullable until Week 3)
    stripe_customer_id     = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    trial_ends_at          = Column(DateTime(timezone=True), nullable=True)

    # Set to True once the admin completes the onboarding wizard.
    # Stored server-side so the flag survives device switches / cache clears.
    onboarding_done = Column(Boolean, default=False, nullable=False)

    # The admin who created the org.
    # use_alter=True breaks the circular FK: org → user → org.
    owner_id   = Column(
        String,
        ForeignKey("users.id", use_alter=True, name="fk_org_owner"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    members = relationship(
        "User",
        primaryjoin="User.org_id == Organization.id",
        back_populates="org",
        foreign_keys="[User.org_id]",
    )


class User(Base):
    """
    Local profile record. id MUST equal the UUID from Supabase auth.users
    so that JWT sub → profile lookup works.

    Passwords and refresh tokens are managed entirely by Supabase Auth;
    hashed_password is kept nullable for backward-compatibility with any
    legacy rows but is never written post-migration.
    """
    __tablename__ = "users"

    id              = Column(String, primary_key=True)       # = Supabase auth UUID
    email           = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)          # legacy; not used post-migration
    full_name       = Column(String, nullable=False)
    role            = Column(SAEnum(UserRole), default=UserRole.employee, nullable=False)
    is_active       = Column(Boolean, default=True)
    org_id          = Column(String, ForeignKey("organizations.id"), nullable=True, index=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())

    org         = relationship("Organization", foreign_keys=[org_id], back_populates="members")
    screenshots = relationship("Screenshot", back_populates="user", cascade="all, delete")


class Screenshot(Base):
    __tablename__ = "screenshots"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    # org_id mirrors the uploading user's org — enables O(1) tenant-scoped queries
    # without a join through users every time.
    org_id = Column(String, ForeignKey("organizations.id"), nullable=True, index=True)
    file_path = Column(String, nullable=False)       # Supabase storage path
    file_url = Column(String, nullable=False)        # Public/signed URL
    thumbnail_path = Column(String, nullable=True)  # Supabase path for 400px thumb
    thumbnail_url = Column(String, nullable=True)   # Signed URL for thumb
    file_size = Column(Integer)                      # bytes
    monitor_index = Column(Integer, default=0)       # which monitor
    os_platform = Column(String)                     # Windows / Darwin / Linux
    captured_at = Column(DateTime(timezone=True), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="screenshots")


class AgentRelease(Base):
    """
    Single-row table holding the currently-published agent release manifest.

    Schema is intentionally minimal: the launcher and updater only need to know
    the latest version, the minimum version that's still allowed to upload, and
    where to fetch each platform's binary. Per-channel rollouts (beta/canary)
    are out of scope for v1 — we use `id` as the channel key so adding a "beta"
    row later is purely additive.

    Updated by the CI release pipeline via POST /agent/version (auth: header
    key X-Release-Key matching settings.agent_release_key).

    `signature` is reserved for Ed25519 manifest signing — left null for now;
    agents that fetch this and find it null skip the signature check.
    """
    __tablename__ = "agent_releases"

    id = Column(String, primary_key=True)              # "stable" | "beta" | …
    version = Column(String, nullable=False)           # "1.2.0"
    min_supported = Column(String, nullable=False)     # "1.0.0"
    released_at = Column(DateTime(timezone=True), server_default=func.now())
    platforms = Column(JSONB, nullable=False)          # { "darwin-arm64": {url, sha256, size}, … }
    signature = Column(String, nullable=True)          # reserved for Ed25519 — see brainstorm
    notes = Column(String, nullable=True)              # human-readable changelog
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AgentHeartbeat(Base):
    """
    Pulse from a running agent, sent every ~10 min. Powers admin
    observability ("who's running what version, are they alive?") and
    closes the auto-update feedback loop ("did 1.2.0 → 1.2.1 actually
    roll out?"). Insert-only — we never UPDATE rows here; queries that
    want "latest per agent" sort by recorded_at DESC and take the first.

    A retention job (Phase H5 / open audit item) will eventually GC rows
    older than ~30 days. Until then volume is bounded by
        users × 6/hr × 24h × 30d ≈ 4.3k rows / user / month
    which is fine even at 1000 users.

    Heartbeats are insert-cheap by design: no per-statement validation
    beyond what the column types enforce, and we never index anything
    besides (user_id, recorded_at) for the "latest" lookup. If we ever
    need historical version-distribution dashboards we'll add a
    materialised view rather than indexing more columns on the hot path.
    """
    __tablename__ = "agent_heartbeats"

    # BigInteger because at 1000 users × 4k rows/month this hits 50M rows
    # in a year — Integer (32-bit signed) would overflow within ~50 months
    # at higher fan-out. Cheap insurance.
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    # Mirrored from User.org_id at write time for tenant-scoped queries
    # without a join (same pattern as Screenshot/DeletionLog).
    org_id = Column(String, ForeignKey("organizations.id"), nullable=True, index=True)

    # ── Reported by the agent ────────────────────────────────────────────
    agent_version   = Column(String, nullable=False)   # "1.2.0"
    os_platform     = Column(String, nullable=False)   # "darwin-arm64", etc.
    status          = Column(String, nullable=False)   # active | idle | paused | …
    queue_size      = Column(Integer, default=0)       # offline-upload queue depth
    pending_review  = Column(Integer, default=0)       # review-queue depth
    captures_today  = Column(Integer, default=0)
    last_capture_at = Column(DateTime(timezone=True), nullable=True)
    last_upload_ok  = Column(Boolean, default=True)
    last_error      = Column(String, nullable=True)    # truncated to ~500 chars at agent

    # ── Computed by the server ───────────────────────────────────────────
    recorded_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


class DeletionLog(Base):
    """Audit record written when an employee removes a screenshot during review."""
    __tablename__ = "deletion_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    # org_id mirrors the deleting user's org — same rationale as Screenshot.org_id.
    org_id = Column(String, ForeignKey("organizations.id"), nullable=True, index=True)
    captured_at = Column(DateTime(timezone=True), nullable=False)
    monitor_index = Column(Integer, default=0)
    deleted_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
