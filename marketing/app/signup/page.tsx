"use client";

import { useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import axios from "axios";
import {
  Eye,
  CheckCircle2,
  Loader2,
  Building2,
  User,
  Mail,
  Lock,
  ExternalLink,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const APP_URL = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

type Plan = "free" | "starter" | "pro";

const PLAN_LABELS: Record<Plan, { label: string; price: string }> = {
  free:    { label: "Free",    price: "$0/mo"  },
  starter: { label: "Starter", price: "$29/mo" },
  pro:     { label: "Pro",     price: "$99/mo" },
};

// ── Inner component (uses useSearchParams — must be inside Suspense) ───────────
function SignupForm() {
  const searchParams = useSearchParams();
  const initialPlan = (searchParams.get("plan") as Plan) || "free";

  const [companyName, setCompanyName]       = useState("");
  const [adminName, setAdminName]           = useState("");
  const [email, setEmail]                   = useState("");
  const [password, setPassword]             = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [plan, setPlan]                     = useState<Plan>(initialPlan);
  const [loading, setLoading]               = useState(false);
  const [error, setError]                   = useState("");
  const [submittedEmail, setSubmittedEmail] = useState<string | null>(null);

  const passwordMismatch = confirmPassword.length > 0 && password !== confirmPassword;
  const passwordWeak     = password.length > 0 && password.length < 8;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirmPassword) { setError("Passwords do not match."); return; }
    if (password.length < 8)          { setError("Password must be at least 8 characters."); return; }

    setError("");
    setLoading(true);
    try {
      await axios.post(`${API_URL}/orgs/`, {
        company_name: companyName.trim(),
        admin_name:   adminName.trim(),
        email:        email.trim().toLowerCase(),
        password,
        plan,
      });
      setSubmittedEmail(email.trim().toLowerCase());
    } catch (err: any) {
      setError(err.response?.data?.detail || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  // ── Success ──────────────────────────────────────────────────────────────────
  if (submittedEmail) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 p-6">
        <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8 text-center">
          <div className="inline-flex p-4 rounded-full bg-emerald-50 text-emerald-600 mb-5">
            <CheckCircle2 size={32} />
          </div>
          <h1 className="text-2xl font-bold mb-2">Check your email</h1>
          <p className="text-slate-500 mb-1">We sent a verification link to</p>
          <p className="font-semibold text-slate-800 mb-5">{submittedEmail}</p>
          <p className="text-sm text-slate-500 mb-6">
            Click the link to activate your account and complete setup.
            The link expires in <strong>24 hours</strong>.
          </p>
          <a
            href={`${APP_URL}/login`}
            className="inline-flex items-center gap-2 text-sm text-brand-600 hover:underline font-medium"
          >
            Go to sign in <ExternalLink size={13} />
          </a>
          <p className="text-xs text-slate-400 mt-4">
            Wrong email?{" "}
            <button
              onClick={() => setSubmittedEmail(null)}
              className="text-brand-600 hover:underline"
            >
              Go back
            </button>
          </p>
        </div>
      </div>
    );
  }

  // ── Form ─────────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex flex-col">
      <header className="px-6 py-4 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-bold text-slate-800">
          <Eye className="text-brand-600" size={20} />
          Employee Monitor
        </Link>
        <p className="text-sm text-slate-500">
          Already have an account?{" "}
          <a href={`${APP_URL}/login`} className="text-brand-600 hover:underline font-medium">
            Sign in
          </a>
        </p>
      </header>

      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-lg">
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-slate-900">Create your account</h1>
            <p className="text-slate-500 text-sm mt-1">
              Set up your organization in under 2 minutes.
            </p>
          </div>

          {/* Plan selector */}
          <div className="bg-white rounded-xl border border-slate-200 p-1 flex mb-5">
            {(Object.entries(PLAN_LABELS) as [Plan, { label: string; price: string }][]).map(
              ([key, { label, price }]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setPlan(key)}
                  className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition ${
                    plan === key
                      ? "bg-brand-600 text-white shadow-sm"
                      : "text-slate-600 hover:text-slate-800"
                  }`}
                >
                  {label}{" "}
                  <span className={`text-xs ${plan === key ? "text-brand-200" : "text-slate-400"}`}>
                    {price}
                  </span>
                </button>
              )
            )}
          </div>

          <form
            onSubmit={onSubmit}
            className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4"
          >
            {/* Company name */}
            <Field label="Company name">
              <IconInput icon={<Building2 size={15} />}>
                <input
                  type="text" required value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="Acme Inc."
                  className="w-full pl-9 pr-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none"
                />
              </IconInput>
            </Field>

            {/* Admin name */}
            <Field label="Your full name">
              <IconInput icon={<User size={15} />}>
                <input
                  type="text" required value={adminName}
                  onChange={(e) => setAdminName(e.target.value)}
                  placeholder="Jane Smith"
                  className="w-full pl-9 pr-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none"
                />
              </IconInput>
            </Field>

            {/* Email */}
            <Field label="Work email">
              <IconInput icon={<Mail size={15} />}>
                <input
                  type="email" required value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="jane@acme.com"
                  className="w-full pl-9 pr-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none"
                />
              </IconInput>
            </Field>

            {/* Passwords */}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Password" error={passwordWeak ? "Too short" : ""}>
                <IconInput icon={<Lock size={15} />}>
                  <input
                    type="password" required value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Min. 8 chars"
                    className={`w-full pl-9 pr-3 py-2.5 border rounded-lg text-sm focus:ring-2 focus:outline-none ${
                      passwordWeak ? "border-red-300 focus:ring-red-400" : "border-slate-200 focus:ring-brand-500 focus:border-brand-500"
                    }`}
                  />
                </IconInput>
              </Field>

              <Field label="Confirm password" error={passwordMismatch ? "Doesn't match" : ""}>
                <IconInput icon={<Lock size={15} />}>
                  <input
                    type="password" required value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat password"
                    className={`w-full pl-9 pr-3 py-2.5 border rounded-lg text-sm focus:ring-2 focus:outline-none ${
                      passwordMismatch ? "border-red-300 focus:ring-red-400" : "border-slate-200 focus:ring-brand-500 focus:border-brand-500"
                    }`}
                  />
                </IconInput>
              </Field>
            </div>

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || passwordMismatch || passwordWeak}
              className="w-full py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white rounded-lg font-medium text-sm flex items-center justify-center gap-2 transition"
            >
              {loading && <Loader2 size={15} className="animate-spin" />}
              {loading ? "Creating account…" : "Create account →"}
            </button>

            <p className="text-center text-xs text-slate-400">
              By signing up you agree to our Terms of Service and Privacy Policy.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}

// ── Small layout helpers ───────────────────────────────────────────────────────
function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-sm font-medium text-slate-700 block mb-1.5">{label}</label>
      {children}
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  );
}

function IconInput({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="relative">
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">{icon}</span>
      {children}
    </div>
  );
}

// ── Page export — wraps in Suspense for useSearchParams ───────────────────────
export default function SignupPage() {
  return (
    <Suspense>
      <SignupForm />
    </Suspense>
  );
}
