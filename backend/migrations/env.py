"""
Alembic environment for the Employee Monitor backend.

Differences from the stock `alembic init` template:

  - Pulls DATABASE_URL from app.config.get_settings() rather than from
    alembic.ini, so migrations always target the same DB the FastAPI
    app is configured against.

  - Uses an async engine (asyncpg) wrapped via run_sync to match the
    rest of the codebase. Stock template is sync-only.

  - Imports app.models explicitly so every Base subclass is registered
    on Base.metadata BEFORE autogenerate compares ORM to DB.

  - NullPool: each `alembic` invocation is one process / one transaction;
    no pool needed and it avoids stale-connection issues against
    Supabase's transaction pooler.
"""

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Make the application package importable. Alembic runs from inside
# backend/ so the parent is backend itself — we just need its app/
# subpackage on the path.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# Importing app.models registers every ORM class on Base.metadata. Without
# this, autogenerate would think every table is "new" because the metadata
# would be empty when env.py runs.
from app.config import get_settings  # noqa: E402
from app.database import Base         # noqa: E402
import app.models                     # noqa: E402, F401 — register tables

# Alembic config object — gives us access to alembic.ini values.
config = context.config

# Initialise logging from alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the DATABASE_URL from app settings, overriding whatever is in
# alembic.ini (which holds a placeholder). This is what lets us point
# alembic at prod by exporting DATABASE_URL in the shell.
#
# Escape % → %% before passing to alembic's configparser. URL-encoded
# password characters like %40 (@) or %23 (#) trigger "invalid
# interpolation syntax" otherwise — configparser reads % as the start
# of a %(name)s reference. set_main_option goes through configparser
# under the hood, so it needs the escape; the actual asyncpg/SQLAlchemy
# layer sees the original URL after configparser un-escapes the doubled
# percent signs.
_db_url = get_settings().database_url
config.set_main_option("sqlalchemy.url", _db_url.replace("%", "%%"))

# Target metadata used by autogenerate to diff against the live DB.
target_metadata = Base.metadata


# ── Offline mode ──────────────────────────────────────────────────────────────
# Generates SQL to stdout instead of running it. Useful for code review
# but not used in our workflow today — kept stock so future use is one
# command away (`alembic upgrade head --sql`).

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Compare types + server_defaults so renames / type changes
        # produce autogenerate diffs instead of silently being skipped.
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (the path we actually use) ────────────────────────────────────

def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Spin up an async engine, run the migration via run_sync, tear down."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
