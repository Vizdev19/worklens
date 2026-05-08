from supabase import create_client, Client
from app.config import get_settings
from datetime import datetime
from PIL import Image
from io import BytesIO
import mimetypes

settings = get_settings()

_client: Client = None

def get_supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client


_MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
}

# Long signed-URL TTL — 24h. Stored on the row so list endpoints don't
# have to round-trip to Supabase per item. Refreshed lazily on miss.
SIGNED_URL_TTL_SECONDS = 24 * 3600

THUMB_WIDTH = 400
THUMB_QUALITY = 60


def _make_thumbnail(image_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(image_bytes))
    if img.width > THUMB_WIDTH:
        ratio = THUMB_WIDTH / img.width
        img = img.resize((THUMB_WIDTH, int(img.height * ratio)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=THUMB_QUALITY, optimize=True)
    buf.seek(0)
    return buf.read()


async def upload_screenshot(
    file_bytes: bytes,
    employee_id: str,
    captured_at: datetime,
    monitor_index: int = 0,
    content_type: str = "image/jpeg",
) -> dict:
    """
    Upload screenshot to Supabase Storage.
    Returns dict with file_path and signed URL.

    Storage path structure:
    {employee_id}/{YYYY-MM-DD}/{HH-MM-SS-microseconds}_monitor{n}.{ext}
    """
    if content_type not in _MIME_TO_EXT:
        raise ValueError(f"Unsupported content type: {content_type}")

    ext = _MIME_TO_EXT[content_type]
    date_str = captured_at.strftime("%Y-%m-%d")
    # Include microseconds to avoid same-second collisions
    time_str = captured_at.strftime("%H-%M-%S-%f")
    file_path = f"{employee_id}/{date_str}/{time_str}_monitor{monitor_index}.{ext}"

    supabase = get_supabase()

    # Upload — Supabase Python SDK raises on HTTP error when upsert is set.
    # Wrap to surface storage failures clearly instead of writing a bad row.
    try:
        supabase.storage.from_(settings.supabase_bucket).upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    except Exception as e:
        raise RuntimeError(f"Storage upload failed: {e}") from e

    # 24h signed URL stored on the row
    signed = supabase.storage.from_(settings.supabase_bucket).create_signed_url(
        path=file_path,
        expires_in=SIGNED_URL_TTL_SECONDS,
    )
    if not signed or "signedURL" not in signed:
        raise RuntimeError(f"Failed to create signed URL: {signed}")

    # Generate and upload thumbnail (non-fatal if it fails)
    thumb_path: str | None = None
    thumb_url: str | None = None
    try:
        thumb_bytes = _make_thumbnail(file_bytes)
        thumb_path = file_path.rsplit(".", 1)[0] + "_thumb.jpg"
        supabase.storage.from_(settings.supabase_bucket).upload(
            path=thumb_path,
            file=thumb_bytes,
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )
        thumb_signed = supabase.storage.from_(settings.supabase_bucket).create_signed_url(
            path=thumb_path,
            expires_in=SIGNED_URL_TTL_SECONDS,
        )
        if thumb_signed and "signedURL" in thumb_signed:
            thumb_url = thumb_signed["signedURL"]
    except Exception as e:
        print(f"[storage] Thumbnail generation failed (non-fatal): {e}")

    return {
        "file_path": file_path,
        "file_url": signed["signedURL"],
        "thumbnail_path": thumb_path,
        "thumbnail_url": thumb_url,
    }


def get_signed_url(file_path: str, expires_in: int = SIGNED_URL_TTL_SECONDS) -> str:
    supabase = get_supabase()
    result = supabase.storage.from_(settings.supabase_bucket).create_signed_url(
        path=file_path,
        expires_in=expires_in,
    )
    return result["signedURL"]


def get_signed_urls_batch(file_paths: list, expires_in: int = SIGNED_URL_TTL_SECONDS) -> dict:
    """
    Generate signed URLs for many paths in a single request.
    Returns {file_path: signed_url}.
    """
    if not file_paths:
        return {}
    supabase = get_supabase()
    results = supabase.storage.from_(settings.supabase_bucket).create_signed_urls(
        paths=file_paths,
        expires_in=expires_in,
    )
    out = {}
    for r in results:
        path = r.get("path") or r.get("Key")
        url = r.get("signedURL") or r.get("signedUrl")
        if path and url:
            out[path] = url
    return out
