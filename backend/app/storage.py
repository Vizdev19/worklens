import asyncio
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


# ── Sync helpers (run via asyncio.to_thread) ──────────────────────────────────
# supabase-py v1 uses blocking httpx under the hood. Calling these directly
# from an async function stalls the event loop for the duration of the HTTP
# round-trip. Wrap every call with asyncio.to_thread so the loop stays free.

def _sync_upload(bucket: str, path: str, file: bytes, content_type: str) -> None:
    """Blocking upload — must be called via asyncio.to_thread."""
    get_supabase().storage.from_(bucket).upload(
        path=path,
        file=file,
        file_options={"content-type": content_type, "upsert": "true"},
    )


def _sync_signed_url(bucket: str, path: str, expires_in: int) -> str:
    """Blocking single signed-URL — must be called via asyncio.to_thread."""
    result = get_supabase().storage.from_(bucket).create_signed_url(
        path=path,
        expires_in=expires_in,
    )
    if not result or "signedURL" not in result:
        raise RuntimeError(f"Failed to create signed URL for {path}: {result}")
    return result["signedURL"]


def _sync_signed_urls_batch(
    bucket: str, paths: list[str], expires_in: int
) -> dict[str, str]:
    """Blocking batch signed-URLs — must be called via asyncio.to_thread."""
    results = get_supabase().storage.from_(bucket).create_signed_urls(
        paths=paths,
        expires_in=expires_in,
    )
    out: dict[str, str] = {}
    for r in results:
        path = r.get("path") or r.get("Key")
        url = r.get("signedURL") or r.get("signedUrl")
        if path and url:
            out[path] = url
    return out


# ── Async public API ──────────────────────────────────────────────────────────

async def upload_screenshot(
    file_bytes: bytes,
    employee_id: str,
    captured_at: datetime,
    monitor_index: int = 0,
    content_type: str = "image/jpeg",
) -> dict:
    """
    Upload screenshot (and thumbnail) to Supabase Storage.
    Returns dict with file_path, file_url, thumbnail_path, thumbnail_url.

    Storage path structure:
    {employee_id}/{YYYY-MM-DD}/{HH-MM-SS-microseconds}_monitor{n}.{ext}

    All Supabase SDK calls are offloaded to a thread pool via asyncio.to_thread
    so the async event loop is never blocked (CB-1/CB-2).
    """
    if content_type not in _MIME_TO_EXT:
        raise ValueError(f"Unsupported content type: {content_type}")

    ext = _MIME_TO_EXT[content_type]
    date_str = captured_at.strftime("%Y-%m-%d")
    # Include microseconds to avoid same-second collisions
    time_str = captured_at.strftime("%H-%M-%S-%f")
    file_path = f"{employee_id}/{date_str}/{time_str}_monitor{monitor_index}.{ext}"

    bucket = settings.supabase_bucket

    # Upload main image (off event loop)
    try:
        await asyncio.to_thread(_sync_upload, bucket, file_path, file_bytes, content_type)
    except Exception as e:
        raise RuntimeError(f"Storage upload failed: {e}") from e

    # 24h signed URL stored on the row
    file_url = await asyncio.to_thread(
        _sync_signed_url, bucket, file_path, SIGNED_URL_TTL_SECONDS
    )

    # Generate and upload thumbnail (non-fatal if it fails)
    thumb_path: str | None = None
    thumb_url: str | None = None
    try:
        # CPU-bound resize — also off the event loop
        thumb_bytes = await asyncio.to_thread(_make_thumbnail, file_bytes)
        thumb_path = file_path.rsplit(".", 1)[0] + "_thumb.jpg"
        await asyncio.to_thread(
            _sync_upload, bucket, thumb_path, thumb_bytes, "image/jpeg"
        )
        thumb_url = await asyncio.to_thread(
            _sync_signed_url, bucket, thumb_path, SIGNED_URL_TTL_SECONDS
        )
    except Exception as e:
        print(f"[storage] Thumbnail generation failed (non-fatal): {e}")
        thumb_path = None
        thumb_url = None

    return {
        "file_path": file_path,
        "file_url": file_url,
        "thumbnail_path": thumb_path,
        "thumbnail_url": thumb_url,
    }


async def get_signed_url(
    file_path: str, expires_in: int = SIGNED_URL_TTL_SECONDS
) -> str:
    """Async wrapper — offloads blocking SDK call to thread pool."""
    return await asyncio.to_thread(
        _sync_signed_url, settings.supabase_bucket, file_path, expires_in
    )


async def get_signed_urls_batch(
    file_paths: list[str], expires_in: int = SIGNED_URL_TTL_SECONDS
) -> dict[str, str]:
    """
    Async wrapper — offloads blocking SDK call to thread pool.
    Returns {file_path: signed_url}.
    """
    if not file_paths:
        return {}
    return await asyncio.to_thread(
        _sync_signed_urls_batch, settings.supabase_bucket, file_paths, expires_in
    )
