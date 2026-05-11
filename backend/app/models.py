from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    ForeignKey, Enum as SAEnum
)
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
