"""
Auth router — post-Supabase-migration.

Login, refresh, and logout are handled directly by the Supabase Auth client
on the frontend and agent. Employee creation (admin action) lives in the
/employees router. This file is kept as a placeholder for future auth-adjacent
endpoints (e.g. password-reset initiation, session listing).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Auth"])
