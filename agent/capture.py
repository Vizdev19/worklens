import mss
import platform
from PIL import Image
from io import BytesIO
from datetime import datetime, timezone
from config import JPEG_QUALITY, MAX_WIDTH

OS = platform.system()


def capture_all_monitors() -> list[dict]:
    """
    Capture all monitors and return a list of dicts:
    { index, image_bytes, width, height, captured_at }
    """
    results = []
    captured_at = datetime.now(timezone.utc)

    with mss.mss() as sct:
        # monitors[0] = combined, monitors[1:] = individual screens
        monitors = sct.monitors[1:]

        for idx, monitor in enumerate(monitors):
            try:
                raw = sct.grab(monitor)
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

                # Resize if wider than MAX_WIDTH (saves bandwidth)
                if img.width > MAX_WIDTH:
                    ratio = MAX_WIDTH / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((MAX_WIDTH, new_height), Image.LANCZOS)

                # Compress to JPEG
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
                buffer.seek(0)

                results.append({
                    "index": idx,
                    "image_bytes": buffer.read(),
                    "width": img.width,
                    "height": img.height,
                    "captured_at": captured_at,
                })
            except Exception as e:
                print(f"[capture] Monitor {idx} failed: {e}")

    return results


def check_macos_permission() -> bool:
    """
    On macOS, test if screen recording permission is granted.
    Returns False if the screenshot is all-black (permission denied).
    """
    if OS != "Darwin":
        return True

    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        # If all pixels are black, permission is denied
        extrema = img.convert("L").getextrema()
        return extrema != (0, 0)
