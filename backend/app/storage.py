from supabase import create_client, Client
from app.config import get_settings
from datetime import datetime
import mimetypes

settings = get_settings()

_client: Client = None

def get_supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client


async def upload_screenshot(
    file_bytes: bytes,
    employee_id: str,
    captured_at: datetime,
    monitor_index: int = 0,
) -> dict:
    """
    Upload screenshot to Supabase Storage.
    Returns dict with file_path and public URL.

    Storage path structure:
    screenshots/{employee_id}/{YYYY-MM-DD}/{HH-MM-SS}_monitor{n}.jpg
    """
    date_str = captured_at.strftime("%Y-%m-%d")
    time_str = captured_at.strftime("%H-%M-%S")
    file_path = f"{employee_id}/{date_str}/{time_str}_monitor{monitor_index}.jpg"

    supabase = get_supabase()

    # Upload to Supabase bucket
    response = supabase.storage.from_(settings.supabase_bucket).upload(
        path=file_path,
        file=file_bytes,
        file_options={"content-type": "image/jpeg", "upsert": "true"},
    )

    # Generate a signed URL valid for 1 hour (private bucket)
    signed = supabase.storage.from_(settings.supabase_bucket).create_signed_url(
        path=file_path,
        expires_in=3600,
    )

    return {
        "file_path": file_path,
        "file_url": signed["signedURL"],
    }


def get_signed_url(file_path: str, expires_in: int = 3600) -> str:
    supabase = get_supabase()
    result = supabase.storage.from_(settings.supabase_bucket).create_signed_url(
        path=file_path,
        expires_in=expires_in,
    )
    return result["signedURL"]
