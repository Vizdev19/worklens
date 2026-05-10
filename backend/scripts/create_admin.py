"""
One-time script to bootstrap the first super-admin user via Supabase Auth.

Usage:
    cd backend
    python -m scripts.create_admin

The script:
  1. Creates the user in Supabase Auth (email auto-confirmed).
  2. Creates the matching profile row in the local `users` table.
  3. Runs init_db() so any pending migrations are applied first.
"""

import asyncio
import sys
import getpass
import httpx
from sqlalchemy import select

sys.path.insert(0, ".")

from app.config import get_settings
from app.database import AsyncSessionLocal, init_db
from app.models import User, UserRole

settings = get_settings()


async def main():
    print("🚀 Initializing database...")
    await init_db()

    print("\n👤 Create super-admin user")
    email = input("Email: ").strip()
    full_name = input("Full name: ").strip()
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("❌ Passwords don't match.")
        return
    if len(password) < 8:
        print("❌ Password must be at least 8 characters.")
        return

    # ── Create auth user in Supabase ──────────────────────────────────────────
    print("\n🔑 Creating Supabase auth user...")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{settings.supabase_url}/auth/v1/admin/users",
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
            },
            json={
                "email": email,
                "password": password,
                "email_confirm": True,   # skip email verification for bootstrap admin
            },
        )

    if resp.status_code == 422:
        print(f"❌ Email {email} is already registered in Supabase.")
        return
    if resp.status_code >= 400:
        print(f"❌ Supabase error {resp.status_code}: {resp.text}")
        return

    supabase_id = resp.json()["id"]
    print(f"   Supabase UUID: {supabase_id}")

    # ── Create local profile ──────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"❌ Profile for {email} already exists in local DB.")
            return

        user = User(
            id=supabase_id,
            email=email,
            full_name=full_name,
            role=UserRole.admin,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    print(f"\n✅ Admin created: {user.full_name} ({user.email})")
    print(f"   ID: {user.id}")
    print("\n🔒 This account can now log in via the dashboard.")


if __name__ == "__main__":
    asyncio.run(main())
