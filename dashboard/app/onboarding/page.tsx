"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase, orgsApi, employeesApi, authApi, setStoredUser } from "@/lib/api";
import {
  Eye,
  CheckCircle2,
  ChevronRight,
  Loader2,
  UserPlus,
  Download,
  Settings2,
  Monitor,
  ArrowRight,
  SkipForward,
  Copy,
  Check,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────────
type WizardStep = 1 | 2 | 3;

// ── Step progress bar ─────────────────────────────────────────────────────────
function StepBar({ current }: { current: WizardStep }) {
  const steps = [
    { n: 1, label: "Monitoring" },
    { n: 2, label: "First employee" },
    { n: 3, label: "Get the agent" },
  ];
  return (
    <div className="flex items-center gap-0 mb-8">
      {steps.map(({ n, label }, i) => {
        const done = current > n;
        const active = current === n;
        return (
          <div key={n} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center gap-1">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition ${
                  done
                    ? "bg-brand-600 text-white"
                    : active
                    ? "border-2 border-brand-600 text-brand-600"
                    : "border-2 border-slate-200 text-slate-400"
                }`}
              >
                {done ? <CheckCircle2 size={16} /> : n}
              </div>
              <span
                className={`text-xs whitespace-nowrap ${
                  active ? "text-brand-600 font-medium" : "text-slate-400"
                }`}
              >
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div
                className={`flex-1 h-0.5 mx-2 mb-4 transition ${
                  done ? "bg-brand-600" : "bg-slate-200"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Step 1 — Monitoring config ─────────────────────────────────────────────────
function Step1({ onNext }: { onNext: () => void }) {
  const [captureInterval, setCaptureInterval] = useState(10);
  const [reviewWindow, setReviewWindow] = useState(5);
  const [idleSkip, setIdleSkip] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function save() {
    setLoading(true);
    setError("");
    try {
      await orgsApi.update({
        capture_interval_minutes: captureInterval,
        review_window_minutes: reviewWindow,
        idle_skip_minutes: idleSkip,
      });
      onNext();
    } catch {
      setError("Failed to save settings. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <Settings2 className="text-brand-600" size={22} />
          Configure monitoring
        </h2>
        <p className="text-slate-500 text-sm mt-1">
          These settings are pushed to all agents in your organization. You can
          change them anytime from the dashboard.
        </p>
      </div>

      {/* Capture interval */}
      <div>
        <label className="text-sm font-medium text-slate-700 block mb-2">
          Screenshot interval
        </label>
        <div className="grid grid-cols-4 gap-2">
          {[5, 10, 15, 30].map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setCaptureInterval(m)}
              className={`py-2.5 rounded-xl text-sm font-medium border transition ${
                captureInterval === m
                  ? "border-brand-600 bg-brand-50 text-brand-700"
                  : "border-slate-200 text-slate-600 hover:border-slate-300"
              }`}
            >
              {m} min
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-400 mt-2">
          How often the agent captures a screenshot per monitor.
        </p>
      </div>

      {/* Review window */}
      <div>
        <label className="text-sm font-medium text-slate-700 block mb-2">
          Employee review window
        </label>
        <div className="grid grid-cols-4 gap-2">
          {[0, 5, 10, 15].map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setReviewWindow(m)}
              className={`py-2.5 rounded-xl text-sm font-medium border transition ${
                reviewWindow === m
                  ? "border-brand-600 bg-brand-50 text-brand-700"
                  : "border-slate-200 text-slate-600 hover:border-slate-300"
              }`}
            >
              {m === 0 ? "Off" : `${m} min`}
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-400 mt-2">
          Time employees have to review and remove a screenshot before it uploads.
        </p>
      </div>

      {/* Idle skip */}
      <div>
        <label className="text-sm font-medium text-slate-700 block mb-2">
          Skip idle screenshots after
        </label>
        <div className="grid grid-cols-4 gap-2">
          {[0, 5, 10, 15].map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setIdleSkip(m)}
              className={`py-2.5 rounded-xl text-sm font-medium border transition ${
                idleSkip === m
                  ? "border-brand-600 bg-brand-50 text-brand-700"
                  : "border-slate-200 text-slate-600 hover:border-slate-300"
              }`}
            >
              {m === 0 ? "Off" : `${m} min`}
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-400 mt-2">
          Screenshots taken after this much idle time are discarded automatically.
        </p>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      <button
        onClick={save}
        disabled={loading}
        className="w-full py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white rounded-xl font-medium flex items-center justify-center gap-2 transition"
      >
        {loading ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <ChevronRight size={16} />
        )}
        {loading ? "Saving…" : "Save & continue"}
      </button>
    </div>
  );
}

// ── Step 2 — Add first employee ────────────────────────────────────────────────
function Step2({ onNext, onSkip }: { onNext: () => void; onSkip: () => void }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [added, setAdded] = useState<{ name: string; email: string } | null>(null);

  async function addEmployee(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await employeesApi.create({ email: email.trim(), full_name: name.trim(), password });
      setAdded({ name: name.trim(), email: email.trim() });
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create employee.");
    } finally {
      setLoading(false);
    }
  }

  if (added) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <UserPlus className="text-brand-600" size={22} />
            Employee added
          </h2>
        </div>

        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-start gap-3">
          <CheckCircle2 className="text-emerald-600 flex-shrink-0 mt-0.5" size={18} />
          <div>
            <p className="font-medium text-emerald-800">{added.name}</p>
            <p className="text-sm text-emerald-700">{added.email}</p>
            <p className="text-xs text-emerald-600 mt-1">
              Share their email + password so they can log into the agent.
            </p>
          </div>
        </div>

        <div className="flex gap-3">
          <button
            onClick={() => {
              setAdded(null);
              setName("");
              setEmail("");
              setPassword("");
            }}
            className="flex-1 py-2.5 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl font-medium text-sm transition"
          >
            Add another
          </button>
          <button
            onClick={onNext}
            className="flex-1 py-2.5 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 transition"
          >
            Continue <ChevronRight size={15} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={addEmployee} className="space-y-5">
      <div>
        <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <UserPlus className="text-brand-600" size={22} />
          Add your first employee
        </h2>
        <p className="text-slate-500 text-sm mt-1">
          Create a login for the first team member you want to monitor.
          You can add more from the dashboard anytime.
        </p>
      </div>

      <div>
        <label className="text-sm font-medium text-slate-700 block mb-1.5">
          Full name
        </label>
        <input
          type="text"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Alex Johnson"
          className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none"
        />
      </div>

      <div>
        <label className="text-sm font-medium text-slate-700 block mb-1.5">
          Work email
        </label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="alex@acme.com"
          className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none"
        />
      </div>

      <div>
        <label className="text-sm font-medium text-slate-700 block mb-1.5">
          Temporary password
        </label>
        <input
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Min. 8 characters"
          className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none"
        />
        <p className="text-xs text-slate-400 mt-1">
          Share this with the employee so they can log into the agent.
        </p>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="flex gap-3">
        <button
          type="button"
          onClick={onSkip}
          className="flex-1 py-2.5 border border-slate-200 hover:bg-slate-50 text-slate-600 rounded-xl font-medium text-sm flex items-center justify-center gap-2 transition"
        >
          <SkipForward size={15} /> Skip for now
        </button>
        <button
          type="submit"
          disabled={loading}
          className="flex-1 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 transition"
        >
          {loading ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <UserPlus size={15} />
          )}
          {loading ? "Adding…" : "Add employee"}
        </button>
      </div>
    </form>
  );
}

// ── Step 3 — Download agent ────────────────────────────────────────────────────

// Map agent manifest's GOOS-GOARCH platform key → user-facing label
// + the file extension we know the agent archive uses. The launcher
// binary's filename follows a different pattern (no version, no ext on
// POSIX) so we derive it separately below.
const PLATFORM_META: Record<
  string,
  { os: string; icon: string; agentExt: string; launcherSuffix: string }
> = {
  "darwin-arm64":  { os: "macOS (Apple Silicon)", icon: "🍎", agentExt: "tar.gz", launcherSuffix: ""    },
  "darwin-amd64":  { os: "macOS (Intel)",          icon: "🍎", agentExt: "tar.gz", launcherSuffix: ""    },
  "windows-amd64": { os: "Windows",                icon: "🪟", agentExt: "zip",    launcherSuffix: ".exe" },
  "linux-amd64":   { os: "Linux",                  icon: "🐧", agentExt: "tar.gz", launcherSuffix: ""    },
};

interface AgentManifest {
  version: string;
  min_supported: string;
  released_at: string;
  platforms: Record<string, { url: string; sha256: string; size: number }>;
}

interface Download {
  platformKey: string;
  os: string;
  icon: string;
  agentLabel: string;
  agentHref: string;
  launcherLabel: string;
  launcherHref: string;
}

// Derive the launcher binary URL from one of the agent archive URLs in
// the same release. The launcher is at the same GitHub Release tag, with
// filename `EmployeeMonitor-<platform>[.exe]`. We don't ship the launcher
// in the manifest itself because it's not part of the auto-update flow
// (the launcher is intentionally near-frozen — see launcher/README.md).
function launcherUrlFromAgentUrl(agentUrl: string, platformKey: string): string {
  // Agent URL example:
  //   https://github.com/OWNER/REPO/releases/download/agent-v1.2.0/EmployeeMonitorAgent-1.2.0-darwin-arm64.tar.gz
  // Launcher URL we want:
  //   https://github.com/OWNER/REPO/releases/download/agent-v1.2.0/EmployeeMonitor-darwin-arm64
  const suffix = PLATFORM_META[platformKey]?.launcherSuffix ?? "";
  return agentUrl.replace(
    /\/EmployeeMonitorAgent-[^/]+$/,
    `/EmployeeMonitor-${platformKey}${suffix}`,
  );
}

function Step3({ onDone }: { onDone: () => void }) {
  const [copied, setCopied] = useState(false);
  const [manifest, setManifest] = useState<AgentManifest | null>(null);
  const [error, setError] = useState<string | null>(null);

  const SERVER_URL =
    process.env.NEXT_PUBLIC_API_URL || "https://your-api.vercel.app";

  // Fetch the manifest once on mount. /agent/version is public — no auth
  // required — so we can hit it with plain fetch instead of the api client.
  useEffect(() => {
    let cancelled = false;
    fetch(`${SERVER_URL}/agent/version`, { cache: "no-store" })
      .then(async (r) => {
        if (r.status === 404) throw new Error("No agent release published yet.");
        if (!r.ok) throw new Error(`Manifest fetch failed: HTTP ${r.status}`);
        return (await r.json()) as AgentManifest;
      })
      .then((m) => { if (!cancelled) setManifest(m); })
      .catch((e) => { if (!cancelled) setError(String(e.message || e)); });
    return () => { cancelled = true; };
  }, [SERVER_URL]);

  function copyServerUrl() {
    navigator.clipboard.writeText(SERVER_URL).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  // Build the per-platform Download cards from the manifest. Keys we
  // don't recognise are silently dropped — protects against a future
  // server-side platform addition (e.g. linux-arm64) the dashboard
  // doesn't yet know how to label.
  const downloads: Download[] = manifest
    ? Object.entries(manifest.platforms)
        .map(([platformKey, asset]): Download | null => {
          const meta = PLATFORM_META[platformKey];
          if (!meta) return null;
          const agentFilename = asset.url.split("/").pop() ?? "";
          return {
            platformKey,
            os: meta.os,
            icon: meta.icon,
            agentLabel: agentFilename,
            agentHref: asset.url,
            launcherLabel: `EmployeeMonitor-${platformKey}${meta.launcherSuffix}`,
            launcherHref: launcherUrlFromAgentUrl(asset.url, platformKey),
          };
        })
        .filter((d): d is Download => d !== null)
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <Download className="text-brand-600" size={22} />
          Get the agent
        </h2>
        <p className="text-slate-500 text-sm mt-1">
          Install the agent on each computer you want to monitor. It runs
          silently in the background with a system tray icon.
          {manifest && (
            <span className="ml-1 text-slate-400">
              (latest version: v{manifest.version})
            </span>
          )}
        </p>
      </div>

      {/* Loading / error states */}
      {!manifest && !error && (
        <div className="rounded-xl border border-slate-200 p-4 flex items-center justify-center gap-2 text-sm text-slate-500">
          <Loader2 className="animate-spin" size={14} />
          Fetching latest release…
        </div>
      )}
      {error && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          Could not load the agent release: {error}
          <div className="text-xs text-amber-700 mt-1">
            You can still download manually from{" "}
            <a
              className="underline"
              href="https://github.com/Vizdev19/worklens/releases/latest"
              target="_blank"
              rel="noreferrer"
            >
              the GitHub Releases page
            </a>
            .
          </div>
        </div>
      )}

      {/* Per-platform downloads. Each entry shows BOTH the launcher and
          the agent archive — install.sh combines them. */}
      {manifest && downloads.length > 0 && (
        <div className="space-y-3">
          {downloads.map((d) => (
            <div
              key={d.platformKey}
              className="rounded-xl border border-slate-200 overflow-hidden"
            >
              <div className="flex items-center gap-2 px-3.5 py-2 bg-slate-50 border-b border-slate-200">
                <span className="text-xl">{d.icon}</span>
                <span className="font-medium text-sm text-slate-800">{d.os}</span>
                <span className="text-xs text-slate-400 ml-auto">
                  {d.platformKey}
                </span>
              </div>
              <a
                href={d.launcherHref}
                className="flex items-center gap-3 px-3.5 py-2 hover:bg-slate-50 transition group border-b border-slate-100"
              >
                <Download size={14} className="text-brand-600 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-slate-500">Launcher</div>
                  <div className="text-xs text-slate-700 font-mono truncate">
                    {d.launcherLabel}
                  </div>
                </div>
              </a>
              <a
                href={d.agentHref}
                className="flex items-center gap-3 px-3.5 py-2 hover:bg-slate-50 transition group"
              >
                <Download size={14} className="text-brand-600 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-slate-500">Agent payload</div>
                  <div className="text-xs text-slate-700 font-mono truncate">
                    {d.agentLabel}
                  </div>
                </div>
              </a>
            </div>
          ))}
        </div>
      )}

      {/* Setup instructions */}
      <div className="rounded-xl bg-slate-50 border border-slate-200 p-4 space-y-3">
        <div className="text-sm font-semibold text-slate-700 flex items-center gap-2">
          <Monitor size={15} className="text-brand-600" />
          Quick setup
        </div>
        {[
          "Download the launcher and agent archive for the employee's OS.",
          "Run installer/install.sh (macOS/Linux) or install.ps1 (Windows) with --launcher, --agent, --version.",
          "Enter the employee's email + password when the agent prompts on first launch.",
        ].map((step, i) => (
          <div key={i} className="flex items-start gap-3">
            <span className="flex-shrink-0 w-5 h-5 rounded-full bg-brand-100 text-brand-700 text-xs font-bold flex items-center justify-center mt-0.5">
              {i + 1}
            </span>
            <p className="text-sm text-slate-600">{step}</p>
          </div>
        ))}
      </div>

      {/* Server URL copy */}
      <div>
        <p className="text-xs text-slate-500 mb-1.5">
          Server URL (pre-configured in the installer — for reference):
        </p>
        <div className="flex items-center gap-2 p-2.5 bg-slate-900 rounded-lg">
          <code className="flex-1 text-xs text-emerald-400 font-mono truncate">
            {SERVER_URL}
          </code>
          <button
            onClick={copyServerUrl}
            className="flex-shrink-0 p-1.5 rounded text-slate-400 hover:text-white transition"
          >
            {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
          </button>
        </div>
      </div>

      <button
        onClick={onDone}
        className="w-full py-3 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold flex items-center justify-center gap-2 transition"
      >
        Go to dashboard <ArrowRight size={16} />
      </button>

      <p className="text-center text-xs text-slate-400">
        You can always download the agent again from the Employees page.
      </p>
    </div>
  );
}

// ── Onboarding page (auth-gated) ───────────────────────────────────────────────
export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<WizardStep>(1);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
        return;
      }
      // Populate stored user profile if not already set
      try {
        const profile = await authApi.me(session.access_token);
        setStoredUser({
          id: profile.id,
          full_name: profile.full_name,
          role: profile.role,
          org_id: profile.org_id,
        });
      } catch {
        /* profile already cached */
      }
      setAuthChecked(true);
    });
  }, [router]);

  async function finishOnboarding() {
    // ARCH-8: persist the flag server-side (org.onboarding_done) so it
    // survives device switches, incognito sessions, and cache clears.
    try {
      await orgsApi.update({ onboarding_done: true });
    } catch {
      // Non-fatal — the dashboard is still usable; the wizard may re-appear
      // on the next login from a fresh device, but that's acceptable.
    }
    router.replace("/dashboard");
  }

  if (!authChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin text-brand-600" size={28} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex flex-col">
      {/* Header */}
      <header className="px-6 py-4 flex items-center gap-2 font-bold text-slate-800">
        <Eye className="text-brand-600" size={20} />
        Employee Monitor
      </header>

      <div className="flex-1 flex items-start justify-center pt-8 px-6 pb-12">
        <div className="w-full max-w-lg">
          <div className="mb-2">
            <p className="text-xs font-semibold text-brand-600 uppercase tracking-wide mb-1">
              Getting started
            </p>
            <h1 className="text-2xl font-bold text-slate-900">
              Welcome to Employee Monitor 👋
            </h1>
            <p className="text-slate-500 text-sm mt-1">
              Let's get your organization set up in 3 quick steps.
            </p>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mt-6">
            <StepBar current={step} />

            {step === 1 && <Step1 onNext={() => setStep(2)} />}
            {step === 2 && (
              <Step2
                onNext={() => setStep(3)}
                onSkip={() => setStep(3)}
              />
            )}
            {step === 3 && <Step3 onDone={finishOnboarding} />}
          </div>
        </div>
      </div>
    </div>
  );
}
