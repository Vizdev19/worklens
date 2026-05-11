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


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Idempotent column additions — safe to run on existing databases.
        # New tables are created by create_all above; only column additions
        # on pre-existing tables need ALTER TABLE.
        for stmt in [
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
        ]:
            await conn.execute(text(stmt))
