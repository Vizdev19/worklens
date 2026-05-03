from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.config import get_settings

settings = get_settings()

# Detect if we're using Supabase's transaction pooler (PgBouncer)
# Pooler URLs contain "pooler.supabase.com" and use port 6543
is_pgbouncer = "pooler.supabase.com" in settings.database_url

# asyncpg-specific connect args
connect_args: dict = {}
if is_pgbouncer:
    # PgBouncer transaction mode doesn't support prepared statements
    # → disable asyncpg's prepared-statement cache
    connect_args = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
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
