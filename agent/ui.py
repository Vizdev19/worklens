"""
Local-browser status UI.

Runs a small HTTP server on 127.0.0.1:<random-free-port>, serves the
status HTML, and opens the user's default browser to it. Replaces the
pywebview-based status_window approach.

Why this design:
- No pywebview / WebView2 / pythonnet — just stdlib HTTP server + the
  user's already-installed browser. Works on every Windows install.
- Same HTML/CSS/JS as before (just fetch() calls instead of pywebview
  bridge methods).
- A second EmployeeMonitor.exe launch reads the URL from a side file
  and re-opens the existing UI tab — natural "click icon to show".

Security:
- Bind only to 127.0.0.1 (loopback)
- Random secret token in the URL path: /<token>/...
- Server rejects any request whose path doesn't start with the token,
  so a malicious site can't drive our API even if it knows the port
"""

import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Callable, Optional

import state
from paths import state_dir

# Module-level state — set by start_server()
_token: Optional[str] = None
_server: Optional[HTTPServer] = None
_on_signout: Optional[Callable[[], None]] = None


# ── Public API ──────────────────────────────────────────────────────────────

def start_server(on_signout: Callable[[], None]) -> str:
    """Start HTTP server in a daemon thread. Return the local URL."""
    global _token, _server, _on_signout

    _on_signout = on_signout
    _token = secrets.token_urlsafe(16)

    # Bind to a random free port on loopback
    _server = _ThreadedHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=_server.serve_forever, daemon=True).start()

    url = get_url()
    _write_url_file(url)
    print(f"[ui] HTTP server listening on {url}")
    return url


def open_in_browser():
    """Open the status UI in the user's default browser."""
    url = get_url()
    if not url:
        print("[ui] Cannot open browser — server not started yet")
        return
    print(f"[ui] Opening {url} in browser")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[ui] webbrowser.open failed: {e}")


def get_url() -> Optional[str]:
    if not _server or not _token:
        return None
    port = _server.server_address[1]
    return f"http://127.0.0.1:{port}/{_token}/"


def read_url_from_file() -> Optional[str]:
    """For second-instance launches — look up the running agent's URL."""
    f = _url_file_path()
    if f.exists():
        try:
            url = f.read_text().strip()
            return url or None
        except Exception:
            return None
    return None


# ── Storage path for the URL handoff file ──────────────────────────────────

def _url_file_path() -> Path:
    return state_dir() / "agent.url"


def _write_url_file(url: str):
    try:
        _url_file_path().write_text(url)
    except Exception as e:
        print(f"[ui] Could not write URL file: {e}")


# ── HTTP server ────────────────────────────────────────────────────────────

class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _Handler(BaseHTTPRequestHandler):
    # Suppress access-log noise
    def log_message(self, fmt, *args):
        pass

    # ── Routing helpers ─────────────────────────────────────────────────────

    def _path_after_token(self) -> Optional[str]:
        """
        Validate the token segment of the URL and return the remainder.
        Returns None if the token doesn't match (caller should 403).
        """
        # path looks like /<token>/<rest>
        # strip leading slash, split max 1
        parts = self.path.lstrip("/").split("/", 1)
        if not parts or parts[0] != _token:
            return None
        rest = "/" + (parts[1] if len(parts) > 1 else "")
        # strip query string for simple routing
        rest = rest.split("?", 1)[0]
        return rest

    def _send(self, status: int, body: bytes, ctype: str = "text/plain; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # Prevent caching of dynamic API responses
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self._send(status, body, "application/json")

    # ── Verbs ───────────────────────────────────────────────────────────────

    def do_GET(self):
        rest = self._path_after_token()
        if rest is None:
            self._send(403, b"Forbidden")
            return

        if rest in ("/", ""):
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            return

        if rest == "/api/snapshot":
            self._send_json(200, state.snapshot())
            return

        self._send(404, b"Not Found")

    def do_POST(self):
        rest = self._path_after_token()
        if rest is None:
            self._send(403, b"Forbidden")
            return

        if rest == "/api/toggle-tracking":
            new_value = not state.is_tracking()
            state.set_tracking(new_value)
            print(f"[ui] Tracking {'started' if new_value else 'stopped'} by user")
            self._send_json(200, {"tracking": new_value})
            return

        if rest == "/api/sign-out":
            self._send_json(200, {"ok": True})
            if _on_signout:
                threading.Thread(target=_on_signout, daemon=True).start()
            return

        self._send(404, b"Not Found")


# ── HTML ────────────────────────────────────────────────────────────────────
# Same panel as the pywebview version, with fetch() calls instead of
# the pywebview bridge. Single self-contained file — no external assets.

HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Employee Monitor</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f8fafc;
    color: #0f172a;
    -webkit-font-smoothing: antialiased;
  }
  body {
    padding: 22px;
    max-width: 420px;
    margin: 32px auto;
    display: flex;
    flex-direction: column;
    gap: 14px;
    min-height: calc(100vh - 64px);
  }
  .header {
    display: flex; align-items: center; gap: 8px;
    color: #4f46e5; font-weight: 700;
  }
  .header svg { width: 18px; height: 18px; }
  h1 { font-size: 16px; }
  .card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px;
  }
  .user .name { font-weight: 600; font-size: 14px; }
  .user .id { color: #64748b; font-size: 12px; margin-top: 2px; }
  .status-row {
    display: flex; align-items: center; gap: 8px;
    font-weight: 600; margin-bottom: 12px;
  }
  .dot {
    width: 9px; height: 9px; border-radius: 50%;
    background: #94a3b8;
    box-shadow: 0 0 0 3px rgba(148, 163, 184, 0.2);
  }
  .dot.active { background: #10b981; box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2); }
  .dot.idle    { background: #f59e0b; box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2); }
  .dot.paused  { background: #f59e0b; box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2); }
  .dot.offline { background: #ef4444; box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.2); }
  .stats {
    display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
  }
  .stat {
    background: #f1f5f9; border-radius: 8px; padding: 8px 10px;
  }
  .stat .label { font-size: 11px; color: #64748b; }
  .stat .value { font-weight: 600; font-size: 13px; margin-top: 2px; }
  .meta { color: #64748b; font-size: 11px; text-align: center; margin-top: 4px; }

  button { font-family: inherit; }
  .toggle {
    border: none; padding: 11px; border-radius: 8px;
    font-weight: 600; font-size: 14px; cursor: pointer;
    transition: all 0.15s; color: white;
  }
  .toggle.start { background: #4f46e5; }
  .toggle.start:hover { background: #4338ca; }
  .toggle.stop  { background: #dc2626; }
  .toggle.stop:hover  { background: #b91c1c; }
  .toggle:disabled { opacity: 0.5; cursor: not-allowed; }
  .signout {
    background: white; color: #64748b;
    border: 1px solid #e2e8f0; padding: 8px;
    border-radius: 8px; font-weight: 500;
    font-size: 12px; cursor: pointer; transition: all 0.15s;
  }
  .signout:hover { background: #f8fafc; color: #dc2626; border-color: #fecaca; }
  .signout:disabled { opacity: 0.5; cursor: not-allowed; }
  .footer { color: #94a3b8; font-size: 10px; text-align: center; margin-top: auto; }
</style>
</head>
<body>
  <div class="header">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
      <path d="M12 2 4 6v6c0 5 3.5 9 8 10 4.5-1 8-5 8-10V6l-8-4Z" />
    </svg>
    <h1>Employee Monitor</h1>
  </div>

  <div class="card user">
    <div class="name" id="name">Loading…</div>
    <div class="id"   id="email"></div>
  </div>

  <div class="card">
    <div class="status-row">
      <span class="dot" id="dot"></span>
      <span id="statusText">Starting…</span>
    </div>
    <div class="stats">
      <div class="stat"><div class="label">Last capture</div><div class="value" id="lastCapture">—</div></div>
      <div class="stat"><div class="label">Captures today</div><div class="value" id="capturesToday">0</div></div>
      <div class="stat"><div class="label">Pending uploads</div><div class="value" id="queueSize">0</div></div>
      <div class="stat"><div class="label">Capture every</div><div class="value" id="interval">— min</div></div>
    </div>
  </div>

  <div class="meta">Closing this tab won't stop monitoring.</div>

  <button class="toggle stop" id="trackBtn">Stop tracking</button>
  <button class="signout" id="signoutBtn">Sign out & quit</button>

  <div class="footer" id="footer">v—</div>

<script>
  const $ = id => document.getElementById(id);

  function relative(iso) {
    if (!iso) return "—";
    const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (seconds < 60) return seconds + "s ago";
    const mins = Math.floor(seconds / 60);
    if (mins < 60) return mins + " min ago";
    const hours = Math.floor(mins / 60);
    return hours + "h ago";
  }

  // All API calls go through this. URLs are relative so the secret
  // token in the path is preserved automatically.
  async function api(path, init = {}) {
    const res = await fetch("." + path, init);
    if (!res.ok) throw new Error(res.status + " " + (await res.text()));
    return res.json();
  }

  async function refresh() {
    try {
      const s = await api("/api/snapshot");

      $("name").textContent  = s.full_name || "—";
      $("email").textContent = s.email_or_id ? "ID: " + s.email_or_id.slice(0, 8) + "…" : "";

      const dot = $("dot");
      dot.className = "dot " + s.status;
      const labels = {
        active:   "Monitoring active",
        idle:     "Idle — capture paused",
        offline:  "Offline — uploads queued",
        starting: "Starting…",
        paused:   "Tracking stopped",
        stopped:  "Stopped",
      };
      $("statusText").textContent = labels[s.status] || s.status;

      $("lastCapture").textContent = relative(s.last_capture_at);
      $("capturesToday").textContent = s.captures_today;
      $("queueSize").textContent = s.queue_size;
      $("interval").textContent = s.capture_interval_minutes + " min";
      if (s.version) $("footer").textContent = "v" + s.version;

      const btn = $("trackBtn");
      if (s.tracking) {
        btn.className = "toggle stop";
        btn.textContent = "Stop tracking";
      } else {
        btn.className = "toggle start";
        btn.textContent = "Start tracking";
      }
    } catch (e) {
      console.error("refresh failed:", e);
      $("statusText").textContent = "Reconnecting…";
    }
  }

  $("trackBtn").addEventListener("click", async () => {
    const btn = $("trackBtn");
    btn.disabled = true;
    try {
      await api("/api/toggle-tracking", { method: "POST" });
      await refresh();
    } catch (e) {
      alert("Toggle failed: " + e.message);
    } finally {
      btn.disabled = false;
    }
  });

  $("signoutBtn").addEventListener("click", async () => {
    if (!confirm("Sign out and stop monitoring?")) return;
    const btn = $("signoutBtn");
    btn.disabled = true;
    btn.textContent = "Signing out…";
    try {
      await api("/api/sign-out", { method: "POST" });
      // Server will exit shortly; replace tab with a friendly message
      document.body.innerHTML = `
        <div style="padding:60px;text-align:center;color:#64748b;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:420px;margin:0 auto;">
          <div style="font-size:48px;margin-bottom:8px;">👋</div>
          <h2 style="color:#0f172a;margin-bottom:8px;">Signed out</h2>
          <p>Monitoring has stopped. You can close this tab.</p>
          <p style="margin-top:32px;font-size:13px;line-height:1.6;">
            To start again, launch <strong>EmployeeMonitor</strong>:
            <br>• <strong>macOS:</strong> Spotlight (⌘Space) → "Employee Monitor"
            <br>• <strong>Windows:</strong> open the EmployeeMonitor folder and double-click EmployeeMonitor.exe
          </p>
        </div>`;
    } catch (e) {
      alert("Sign out failed: " + e.message);
      btn.disabled = false;
      btn.textContent = "Sign out & quit";
    }
  });

  document.addEventListener("DOMContentLoaded", () => {
    refresh();
    setInterval(refresh, 5000);
  });
</script>
</body>
</html>
"""
