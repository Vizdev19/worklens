"""
Status panel window (pywebview).

Opens a small native window showing:
  - Logged-in user
  - Live status (active / idle / offline)
  - Last capture time, captures today, pending uploads
  - Sign out button

Closing the window does NOT stop the agent — it keeps capturing in
the background. Sign out explicitly stops everything.
"""

import sys
import threading

import webview

import auth
import autostart
import state


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
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
    width: 100%;
    height: 100vh;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .header {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #4f46e5;
    font-weight: 700;
  }
  .header svg { width: 18px; height: 18px; }
  h1 { font-size: 16px; }
  .user {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px;
  }
  .user .name { font-weight: 600; font-size: 14px; }
  .user .id { color: #64748b; font-size: 12px; margin-top: 2px; }
  .status-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 14px;
  }
  .status-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    margin-bottom: 12px;
  }
  .dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: #94a3b8;
    box-shadow: 0 0 0 3px rgba(148, 163, 184, 0.2);
  }
  .dot.active { background: #10b981; box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2); }
  .dot.idle   { background: #f59e0b; box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2); }
  .dot.offline{ background: #ef4444; box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.2); }

  .stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .stat {
    background: #f1f5f9;
    border-radius: 8px;
    padding: 8px 10px;
  }
  .stat .label { font-size: 11px; color: #64748b; }
  .stat .value { font-weight: 600; font-size: 13px; margin-top: 2px; }

  .meta {
    color: #64748b;
    font-size: 11px;
    text-align: center;
    margin-top: 4px;
  }

  .toggle {
    border: none;
    padding: 11px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.15s;
    color: white;
  }
  .toggle.start { background: #4f46e5; }
  .toggle.start:hover { background: #4338ca; }
  .toggle.stop  { background: #dc2626; }
  .toggle.stop:hover  { background: #b91c1c; }
  .toggle:disabled { opacity: 0.5; cursor: not-allowed; }

  .signout {
    background: white;
    color: #64748b;
    border: 1px solid #e2e8f0;
    padding: 8px;
    border-radius: 8px;
    font-weight: 500;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .signout:hover { background: #f8fafc; color: #dc2626; border-color: #fecaca; }
  .signout:disabled { opacity: 0.5; cursor: not-allowed; }

  .footer {
    color: #94a3b8;
    font-size: 10px;
    text-align: center;
    margin-top: auto;
  }
</style>
</head>
<body>
  <div class="header">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
      <path d="M12 2 4 6v6c0 5 3.5 9 8 10 4.5-1 8-5 8-10V6l-8-4Z" />
    </svg>
    <h1>Employee Monitor</h1>
  </div>

  <div class="user">
    <div class="name" id="name">Loading...</div>
    <div class="id"   id="email"></div>
  </div>

  <div class="status-card">
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

  <div class="meta" id="meta">Closing this window won't stop monitoring.</div>

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

  async function refresh() {
    try {
      const s = await pywebview.api.snapshot();

      $("name").textContent  = s.full_name || "—";
      $("email").textContent = s.email_or_id ? "ID: " + s.email_or_id.slice(0, 8) + "…" : "";

      const dot = $("dot");
      const text = $("statusText");
      dot.className = "dot " + s.status;
      const labels = {
        active:   "Monitoring active",
        idle:     "Idle — capture paused",
        offline:  "Offline — uploads queued",
        starting: "Starting…",
        paused:   "Tracking stopped",
        stopped:  "Stopped",
      };
      text.textContent = labels[s.status] || s.status;

      $("lastCapture").textContent = relative(s.last_capture_at);
      $("capturesToday").textContent = s.captures_today;
      $("queueSize").textContent = s.queue_size;
      $("interval").textContent = s.capture_interval_minutes + " min";
      if (s.version) $("footer").textContent = "v" + s.version;

      // Toggle button reflects the tracking flag
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
    }
  }

  $("trackBtn").addEventListener("click", async () => {
    const btn = $("trackBtn");
    btn.disabled = true;
    try {
      await pywebview.api.toggle_tracking();
      await refresh();
    } catch (e) {
      alert("Toggle failed: " + e);
    } finally {
      btn.disabled = false;
    }
  });

  $("signoutBtn").addEventListener("click", async () => {
    if (!confirm("Sign out and stop monitoring?")) return;
    $("signoutBtn").disabled = true;
    $("signoutBtn").textContent = "Signing out...";
    try {
      await pywebview.api.sign_out();
    } catch (e) {
      alert("Sign out failed: " + e);
      $("signoutBtn").disabled = false;
      $("signoutBtn").textContent = "Sign out & quit";
    }
  });

  // Wait for pywebview bridge to be ready
  window.addEventListener("pywebviewready", () => {
    refresh();
    setInterval(refresh, 5000);
  });
</script>
</body>
</html>
"""


class _Api:
    """Bridge methods exposed to the JS side via pywebview."""

    def __init__(self, on_signout):
        self._on_signout = on_signout

    def snapshot(self):
        return state.snapshot()

    def toggle_tracking(self):
        new_value = not state.is_tracking()
        state.set_tracking(new_value)
        print(f"[ui] Tracking {'started' if new_value else 'stopped'} by user")
        return new_value

    def sign_out(self):
        # Run async so the JS button click can return
        threading.Thread(target=self._on_signout, daemon=True).start()
        return True


def open_window(on_signout):
    """Blocking — runs the pywebview event loop on the main thread."""
    api = _Api(on_signout)
    webview.create_window(
        title="Employee Monitor",
        html=HTML,
        js_api=api,
        width=380,
        height=520,
        resizable=False,
        on_top=False,
    )
    try:
        webview.start(debug=False)
    except Exception as e:
        print(f"[ui] pywebview failed: {e}; running headless")
