import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from app.config import get_settings

settings = get_settings()

# Detect if we're using Supabase's transaction pooler (PgBouncer)
# Pooler URLs contain "pooler.supabase.com" and use port 6543
is_pgbouncer = "pooler.supabase.com" in settings.database_url

# asyncpg-specific connect args
connect_args: dict = {}
if is_pgbouncer:
    # PgBouncer transaction mode doesn't support prepared statements properly.
    # Three things needed:
    #   1. statement_cache_size=0 → don't cache prepared statements client-side
    #   2. prepared_statement_cache_size=0 → SQLAlchemy-level
    #   3. unique statement names → each call gets its own server-side name
    #      (otherwise reused names collide across pooled connections)
    connect_args = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
    }

# Engine config
# - In serverless / behind PgBouncer: NullPool (don't reuse connections across requests)
# - Locally: small pool, normal behavior
engine_kwargs: dict = {
    "echo": settings.environment == "development",
    "connect_args": connect_args,
}

if is_pgbouncer:
    # NullPool: each request opens a fresh connection through PgBouncer
    # PgBouncer itself handles the actual pooling on the server side
    engine_kwargs["poolclass"] = NullPool
else:
    # Direct connection (local dev) — standard SQLAlchemy pool
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
    engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(settings.database_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Idempotent migrations ────────────────────────────────────────────────────
# These are individually idempotent (each uses IF NOT EXISTS / DROP NOT NULL,
# both of which are no-ops on the second run). They handle column additions
# on tables that already exist in production — the ORM models in app/models.py
# describe the *current* schema, but production rows pre-date some additions
# and need ALTERs to catch up.
#
# Run order matters: a column FK'd to organizations.id must wait until the
# organizations table exists (otherwise Postgres raises UndefinedTableError).
_IDEMPOTENT_MIGRATIONS: tuple[str, ...] = (
    # Thumbnail feature
    "ALTER TABLE screenshots ADD COLUMN IF NOT EXISTS thumbnail_path TEXT",
    "ALTER TABLE screenshots ADD COLUMN IF NOT EXISTS thumbnail_url TEXT",
    # Multi-tenancy: org membership on users
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS org_id TEXT REFERENCES organizations(id)",
    # email_verified column (legacy — Supabase now owns verification)
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT TRUE",
    # Multi-tenancy: org_id on screenshots (now part of ORM model — index added)
    "ALTER TABLE screenshots ADD COLUMN IF NOT EXISTS org_id TEXT REFERENCES organizations(id)",
    "CREATE INDEX IF NOT EXISTS ix_screenshots_org_id ON screenshots (org_id)",
    # Multi-tenancy: org_id on deletion_logs (now part of ORM model — index added)
    "ALTER TABLE deletion_logs ADD COLUMN IF NOT EXISTS org_id TEXT REFERENCES organizations(id)",
    "CREATE INDEX IF NOT EXISTS ix_deletion_logs_org_id ON deletion_logs (org_id)",
    # Supabase Auth migration: passwords are now managed by Supabase;
    # allow NULL so new users created via the Admin API have no local hash.
    "ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL",
    # ARCH-8: server-side onboarding flag (replaces localStorage hack)
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS onboarding_done BOOLEAN NOT NULL DEFAULT FALSE",
)


async def init_db():
    """
    Bring the DB schema in line with the ORM models.

    Two stages, each in its own transaction — historically this was one
    big `engine.begin()` block and a single failing ALTER would roll back
    everything (including the tables `create_all` had just created),
    leaving the operator in a stuck state where re-running hit the
    exact same failure:

      Stage 1 — create_all
        Issues CREATE TABLE for any model whose table doesn't exist in
        the DB. Runs in its own transaction; commits before stage 2 even
        starts. This is critical because some stage-2 statements ALTER
        columns that REFERENCE freshly-created tables — if stage 1 hadn't
        already committed, the FK target wouldn't be visible.

      Stage 2 — idempotent migrations, one transaction each
        Every ALTER / CREATE INDEX runs in its own short transaction. A
        single bad statement (e.g. one that references a column that
        couldn't be created on this PG version) only rolls back itself;
        the rest still apply. We log failures and continue, so the
        operator sees the full picture instead of one error masking many.

    The original failure that motivated this rewrite: on a partially-
    populated DB (users / screenshots from old schema, organizations
    missing) under Supabase's transaction pooler, `create_all`'s
    introspection wrongly believed organizations existed and skipped its
    CREATE. The first ALTER referencing organizations(id) then failed
    with UndefinedTableError, rolling back everything `create_all` HAD
    done. See git history for the auto-update Phase 1→prod-bringup
    debugging session for the full story.
    """
    # Stage 1 — tables. Atomic and committed before stage 2 starts.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Stage 2 — migrations. Each statement in its own transaction so a
    # single failure can't cascade. Failures are logged loudly but don't
    # raise — letting subsequent migrations still apply means a bad
    # statement at position N doesn't gate the N+1 fix the operator
    # might also need.
    errors: list[tuple[str, str]] = []
    for stmt in _IDEMPOTENT_MIGRATIONS:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
        except Exception as e:
            short = stmt[:80] + ("…" if len(stmt) > 80 else "")
            print(f"[init_db] WARN: migration failed: {short}")
            print(f"           reason: {type(e).__name__}: {e}")
            errors.append((short, f"{type(e).__name__}: {e}"))

    if errors:
        print(f"[init_db] completed with {len(errors)} failure(s):")
        for stmt, err in errors:
            print(f"  • {stmt}\n      {err}")
    else:
        print("[init_db] all migrations applied cleanly")
