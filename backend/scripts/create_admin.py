"""
One-time script to create the first admin user.
Usage:
    cd backend
    python -m scripts.create_admin
"""

import asyncio
import sys
import getpass
from sqlalchemy import select

# Allow running as a module
sys.path.insert(0, ".")

from app.database import AsyncSessionLocal, init_db
from app.models import User, UserRole
from app.auth import hash_password


async def main():
    print("🚀 Initializing database...")
    await init_db()

    print("\n👤 Create admin user")
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

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"❌ User with email {email} already exists.")
            return

        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            role=UserRole.admin,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        print(f"\n✅ Admin created: {user.full_name} ({user.email})")
        print(f"   ID: {user.id}")


if __name__ == "__main__":
    asyncio.run(main())
