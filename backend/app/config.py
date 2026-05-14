from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


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

    # Dashboard URL — the host that serves the /auth/callback page. Used as
    # email_redirect_to when Supabase sends verification links during org
    # signup. MUST be the **dashboard** app's URL (not the marketing site),
    # because only the dashboard owns /auth/callback.
    #
    # Must also be listed in Supabase Dashboard → Auth → URL Configuration
    # → Allowed Redirect URLs, or Supabase silently rewrites the redirect
    # to its own SITE_URL fallback.
    #
    # Accepts either DASHBOARD_URL (preferred — unambiguous) or the older
    # FRONTEND_URL env var name (kept for backward compat with deployments
    # that haven't renamed yet). DASHBOARD_URL wins when both are set.
    dashboard_url: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("DASHBOARD_URL", "FRONTEND_URL"),
    )

    # Bearer-style secret used by the CI release pipeline to publish new agent
    # manifests via POST /agent/version. Keep this out of any client/agent build —
    # it lives only in the backend env and the GitHub Actions secret store.
    # If unset, the publish endpoint is disabled (manifest is read-only).
    agent_release_key: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # ignore unknown env vars
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
