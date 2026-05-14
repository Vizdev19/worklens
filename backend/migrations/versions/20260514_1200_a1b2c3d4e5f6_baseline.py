"""Baseline schema

Revision ID: a1b2c3d4e5f6
Revises: None
Create Date: 2026-05-14 12:00:00 UTC

First migration. Captures every table in app/models.py exactly as of
agent v1.2.0 / backend post-Phase-6. Hand-written rather than
--autogenerate-d because we don't have a clean DB to diff against —
prod and dev have both been hand-poked over the last few weeks.

Prod reconciliation (one-time):
    1. Manually create agent_heartbeats if it doesn't exist yet (see
       RELEASING.md — we paste the same SQL once more then never again).
    2. `alembic stamp a1b2c3d4e5f6` against prod. This writes
       alembic_version=a1b2c3d4e5f6 WITHOUT running upgrade() — we're
       telling Alembic "prod's schema already matches this revision."
    3. Done. All future migrations layer on top of this baseline.

Fresh dev environments just `alembic upgrade head` — upgrade() runs
and creates everything from scratch.

The downgrade() path drops all tables + types in reverse dependency
order. Useful for `alembic downgrade base` in tests and for the
rare "I screwed up, give me a clean slate" moment.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op


# Alembic revision identifiers.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enum types ────────────────────────────────────────────────────────────
    # Created up-front so the tables that reference them below can use the
    # type name directly. Postgres requires the type to exist before any
    # column references it.
    plan_enum = postgresql.ENUM(
        "free", "starter", "pro", "enterprise",
        name="plan",
        create_type=False,  # we manage creation explicitly via execute()
    )
    role_enum = postgresql.ENUM(
        "admin", "employee",
        name="userrole",
        create_type=False,
    )
    op.execute("CREATE TYPE plan AS ENUM ('free', 'starter', 'pro', 'enterprise')")
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'employee')")

    # ── organizations ────────────────────────────────────────────────────────
    # Created first; the FK constraint on owner_id → users.id is added later
    # via a separate ALTER once users exists (use_alter pattern in the ORM).
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("plan", plan_enum, nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("capture_interval_minutes", sa.Integer(), server_default="10"),
        sa.Column("review_window_minutes", sa.Integer(), server_default="5"),
        sa.Column("idle_skip_minutes", sa.Integer(), server_default="5"),
        sa.Column("retention_days", sa.Integer(), server_default="7"),
        sa.Column("max_seats", sa.Integer(), server_default="3"),
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "onboarding_done",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("owner_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("role", role_enum, nullable=False, server_default="employee"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column(
            "org_id",
            sa.String(),
            sa.ForeignKey("organizations.id"),
            nullable=True,
        ),
        # Legacy column — Supabase Auth owns verification now. Kept so
        # prod's existing column matches the ORM and autogenerate stays quiet.
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_org_id", "users", ["org_id"])

    # Deferred FK closing the org ↔ user cycle (use_alter pattern).
    op.create_foreign_key(
        "fk_org_owner",
        source_table="organizations",
        referent_table="users",
        local_cols=["owner_id"],
        remote_cols=["id"],
    )

    # ── screenshots ──────────────────────────────────────────────────────────
    op.create_table(
        "screenshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False,
        ),
        sa.Column(
            "org_id",
            sa.String(),
            sa.ForeignKey("organizations.id"),
            nullable=True,
        ),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("file_url", sa.String(), nullable=False),
        sa.Column("thumbnail_path", sa.String(), nullable=True),
        sa.Column("thumbnail_url", sa.String(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("monitor_index", sa.Integer(), server_default="0"),
        sa.Column("os_platform", sa.String(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_screenshots_user_id", "screenshots", ["user_id"])
    op.create_index("ix_screenshots_org_id", "screenshots", ["org_id"])

    # ── deletion_logs ────────────────────────────────────────────────────────
    op.create_table(
        "deletion_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False,
        ),
        sa.Column(
            "org_id",
            sa.String(),
            sa.ForeignKey("organizations.id"),
            nullable=True,
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("monitor_index", sa.Integer(), server_default="0"),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_deletion_logs_user_id", "deletion_logs", ["user_id"])
    op.create_index("ix_deletion_logs_org_id", "deletion_logs", ["org_id"])

    # ── agent_releases ───────────────────────────────────────────────────────
    op.create_table(
        "agent_releases",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("min_supported", sa.String(), nullable=False),
        sa.Column(
            "released_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("platforms", postgresql.JSONB(), nullable=False),
        sa.Column("signature", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── agent_heartbeats ─────────────────────────────────────────────────────
    op.create_table(
        "agent_heartbeats",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False,
        ),
        sa.Column(
            "org_id",
            sa.String(),
            sa.ForeignKey("organizations.id"),
            nullable=True,
        ),
        sa.Column("agent_version", sa.String(), nullable=False),
        sa.Column("os_platform", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("queue_size", sa.Integer(), server_default="0"),
        sa.Column("pending_review", sa.Integer(), server_default="0"),
        sa.Column("captures_today", sa.Integer(), server_default="0"),
        sa.Column("last_capture_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_upload_ok",
            sa.Boolean(),
            server_default=sa.text("true"),
        ),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_agent_heartbeats_user_id", "agent_heartbeats", ["user_id"],
    )
    op.create_index(
        "ix_agent_heartbeats_org_id", "agent_heartbeats", ["org_id"],
    )
    op.create_index(
        "ix_agent_heartbeats_recorded_at",
        "agent_heartbeats",
        ["recorded_at"],
    )
    # Composite index for "latest heartbeat per user" — the hot path
    # behind GET /employees/heartbeats. Single index lookup instead of
    # scanning two separate B-trees.
    op.create_index(
        "ix_agent_heartbeats_user_recorded",
        "agent_heartbeats",
        ["user_id", sa.text("recorded_at DESC")],
    )


def downgrade() -> None:
    # Reverse dependency order: drop tables that reference others first.
    op.drop_index("ix_agent_heartbeats_user_recorded", table_name="agent_heartbeats")
    op.drop_index("ix_agent_heartbeats_recorded_at", table_name="agent_heartbeats")
    op.drop_index("ix_agent_heartbeats_org_id", table_name="agent_heartbeats")
    op.drop_index("ix_agent_heartbeats_user_id", table_name="agent_heartbeats")
    op.drop_table("agent_heartbeats")

    op.drop_table("agent_releases")

    op.drop_index("ix_deletion_logs_org_id", table_name="deletion_logs")
    op.drop_index("ix_deletion_logs_user_id", table_name="deletion_logs")
    op.drop_table("deletion_logs")

    op.drop_index("ix_screenshots_org_id", table_name="screenshots")
    op.drop_index("ix_screenshots_user_id", table_name="screenshots")
    op.drop_table("screenshots")

    # Break the cycle FK before dropping either table.
    op.drop_constraint("fk_org_owner", "organizations", type_="foreignkey")

    op.drop_index("ix_users_org_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")

    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS plan")
