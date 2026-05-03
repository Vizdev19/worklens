"""
Create an employee account.
Usage: python -m scripts.create_employee
"""

import asyncio
import sys
import getpass
from sqlalchemy import select

sys.path.insert(0, ".")

from app.database import AsyncSessionLocal
from app.models import User, UserRole
from app.auth import hash_password


async def main():
    print("👥 Create employee account")
    email = input("Email: ").strip()
    full_name = input("Full name: ").strip()
    password = getpass.getpass("Password: ")

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"❌ Email {email} already exists.")
            return

        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            role=UserRole.employee,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        print(f"\n✅ Employee created: {user.full_name} ({user.email})")
        print(f"   ID: {user.id}")
        print(f"\n📥 Give the employee these credentials so they can log into the agent.")


if __name__ == "__main__":
    asyncio.run(main())
