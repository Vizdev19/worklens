"""
One-shot: run all pending schema migrations and exit.

Usage:
    cd backend
    DATABASE_URL='postgresql+asyncpg://...' python -m scripts.init_db

Idempotent — safe to run repeatedly. Use after adding new tables/columns
to the ORM (e.g. Phase 1 of auto-update added the AgentRelease table,
which the deployed FastAPI app won't auto-create on cold start).

This is a thin wrapper around app.database.init_db(); it exists so you
can pick up new tables without going through the interactive prompts in
scripts.create_admin (which calls init_db too, but then expects a TTY
to seed a super-admin).
"""

import asyncio
import sys

sys.path.insert(0, ".")

from app.database import init_db


async def main() -> None:
    print("Running init_db() — creating tables and applying idempotent migrations…")
    await init_db()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
