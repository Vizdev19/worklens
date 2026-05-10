from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase project credentials
    supabase_url: str
    supabase_service_key: str          # service_role key — never expose to clients
    supabase_bucket: str = "screenshots"

    # Supabase Auth JWT secret — Project Settings → API → JWT Secret
    # Used to validate Bearer tokens issued by Supabase Auth (GoTrue).
    supabase_jwt_secret: str

    # PostgreSQL — Supabase pooler URL recommended for production
    database_url: str

    # CORS — comma-separated list of allowed origins
    allowed_origins: str = "http://localhost:3000"

    # App
    app_name: str = "EmployeeMonitor"
    environment: str = "development"

    # Frontend URL — used as the redirect target in Supabase verification emails.
    # Must be listed in Supabase Dashboard → Auth → URL Configuration → Allowed Redirect URLs.
    frontend_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # ignore unknown env vars
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
