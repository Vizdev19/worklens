"""
Agent configuration.

Resolution order (first wins):
  1. Environment variables (set by user / installer)
  2. Bundled .env (loaded from the app bundle in production)
  3. Defaults below — see PRODUCTION_DEFAULTS

The PRODUCTION_DEFAULTS values get baked into the packaged binary, so
employees don't need to configure anything. Override locally with .env
during development.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv


# Bake-in version. Bumped on each release; CI replaces this on tag builds
# via a sed-style step (see .github/workflows/build-agent.yml — TODO).
# For now, set this manually before tagging:
#     1. Edit AGENT_VERSION
#     2. git commit
#     3. git tag agent-v<same-version>
# 1.2.0 — first release under the launcher-managed install topology.
# 1.1.3 and earlier are pre-auto-update and require manual reinstall;
# the backend's min_supported can be set to 1.2.0 to force them out.
__version__ = "1.2.0"
AGENT_VERSION = __version__


# ── Production defaults (baked into the packaged binary) ───────────────────
# Update SERVER_URL when your prod backend URL changes.
PRODUCTION_DEFAULTS = {
    "SERVER_URL": "https://employee-monitor-api.vercel.app",
    # Supabase project — agents authenticate directly against Supabase Auth REST API.
    # These are the anon/public credentials (safe to bundle in the binary).
    "SUPABASE_URL": "https://your-project.supabase.co",
    "SUPABASE_ANON_KEY": "your-anon-key",
    "CAPTURE_INTERVAL_MINUTES": "10",
    "IDLE_SKIP_MINUTES": "5",
    "JPEG_QUALITY": "70",
    "MAX_WIDTH": "1920",
    "REVIEW_WINDOW_MINUTES": "5",   # How long employees have to remove a screenshot before it auto-uploads
}


def _is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def _bundle_dir() -> Path:
    """Directory containing the bundled resources at runtime."""
    if _is_frozen():
        # PyInstaller extracts to sys._MEIPASS at runtime
        return Path(getattr(sys, "_MEIPASS", "."))
    return Path(__file__).resolve().parent


# 1. Load .env if present (next to script in dev, or bundled in prod)
env_path = _bundle_dir() / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()  # current directory fallback


def _cfg(key: str) -> str:
    """Env > production default."""
    return os.getenv(key, PRODUCTION_DEFAULTS.get(key, ""))


SERVER_URL = _cfg("SERVER_URL")
SUPABASE_URL = _cfg("SUPABASE_URL")
SUPABASE_ANON_KEY = _cfg("SUPABASE_ANON_KEY")
CAPTURE_INTERVAL_MINUTES = int(_cfg("CAPTURE_INTERVAL_MINUTES"))
IDLE_SKIP_MINUTES = int(_cfg("IDLE_SKIP_MINUTES"))
JPEG_QUALITY = int(_cfg("JPEG_QUALITY"))
MAX_WIDTH = int(_cfg("MAX_WIDTH"))
REVIEW_WINDOW_MINUTES = int(_cfg("REVIEW_WINDOW_MINUTES"))
KEYRING_SERVICE = "EmployeeMonitor"
