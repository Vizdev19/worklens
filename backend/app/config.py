from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_service_key: str
    supabase_bucket: str = "screenshots"

    # PostgreSQL
    database_url: str

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # CORS — comma-separated list of allowed origins
    allowed_origins: str = "http://localhost:3000"

    # App
    app_name: str = "EmployeeMonitor"
    environment: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # ignore unknown env vars instead of erroring
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
