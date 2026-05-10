"""
Create an employee account via Supabase Auth + local profile.

Usage: python -m scripts.create_employee

Prefer the dashboard UI (Employees → Add employee) for day-to-day use.
This script is useful for bulk seeding or CI/staging setup.
"""

import asyncio
import sys
import getpass
import httpx
from sqlalchemy import select

sys.path.insert(0, ".")

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import User, UserRole

settings = get_settings()


async def main():
    print("👥 Create employee account")
    email = input("Email: ").strip()
    full_name = input("Full name: ").strip()
    password = getpass.getpass("Password: ")

    if len(password) < 8:
        print("❌ Password must be at least 8 characters.")
        return

    # ── Create auth user in Supabase ──────────────────────────────────────────
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
                "email_confirm": True,   # admin-created accounts skip email verification
            },
        )

    if resp.status_code == 422:
        print(f"❌ Email {email} is already registered in Supabase.")
        return
    if resp.status_code >= 400:
        print(f"❌ Supabase error {resp.status_code}: {resp.text}")
        return

    supabase_id = resp.json()["id"]

    # ── Create local profile ──────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"❌ Email {email} already exists locally.")
            return

        user = User(
            id=supabase_id,
            email=email,
            full_name=full_name,
            role=UserRole.employee,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    print(f"\n✅ Employee created: {user.full_name} ({user.email})")
    print(f"   ID: {user.id}")
    print("\n📥 Share the email + password with the employee so they can log in.")


if __name__ == "__main__":
    asyncio.run(main())
