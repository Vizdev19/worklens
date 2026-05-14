"""
Apply pending Alembic migrations (i.e. bring the schema up to head).

Kept as `scripts.init_db` so existing tooling (RELEASING.md, our own
muscle memory) keeps working — but the implementation is just a thin
wrapper around `alembic upgrade head` using Alembic's Python API.

Usage:
    cd backend
    DATABASE_URL='postgresql+asyncpg://...' \\
    SUPABASE_JWT_SECRET='...' \\
    python -m scripts.init_db

For prod bootstrapping (one-time, after introducing Alembic):
    # 1. Reconcile any schema drift (e.g. paste agent_heartbeats SQL if missing)
    # 2. Mark prod as already at the baseline revision WITHOUT running it:
    cd backend
    python -m scripts.init_db --stamp-only

This makes prod's alembic_version table match what's on disk, and
subsequent migrations layer cleanly on top.
"""

import argparse
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config


def _load_alembic_config() -> Config:
    """
    Build the Alembic Config object pointing at our local alembic.ini.
    Resolves the path relative to this script so cwd doesn't matter.
    """
    backend_root = Path(__file__).resolve().parent.parent
    cfg_path = backend_root / "alembic.ini"
    if not cfg_path.exists():
        raise FileNotFoundError(f"alembic.ini not found at {cfg_path}")
    cfg = Config(str(cfg_path))
    # env.py reads DATABASE_URL from app.config; we make sure cwd
    # doesn't interfere by setting script_location absolutely.
    cfg.set_main_option("script_location", str(backend_root / "migrations"))
    return cfg


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply pending Alembic migrations.")
    parser.add_argument(
        "--stamp-only",
        action="store_true",
        help=(
            "Mark the DB as already at HEAD without running any migration. "
            "Used once when introducing Alembic to an existing DB whose "
            "schema already matches the baseline revision."
        ),
    )
    args = parser.parse_args()

    cfg = _load_alembic_config()

    if args.stamp_only:
        print("Stamping DB at head (no DDL will run)…")
        command.stamp(cfg, "head")
        print("Done — alembic_version now reports head. Future migrations will apply incrementally.")
        return 0

    print("Running alembic upgrade head…")
    command.upgrade(cfg, "head")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
