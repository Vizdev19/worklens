"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { orgsApi } from "@/lib/api";
import {
  Eye,
  CheckCircle2,
  Loader2,
  ArrowLeft,
  Building2,
  User,
  Mail,
  Lock,
} from "lucide-react";

type Plan = "free" | "starter" | "pro";

const PLAN_LABELS: Record<Plan, { label: string; price: string; seats: string }> = {
  free:    { label: "Free",    price: "$0/mo",  seats: "3 seats"  },
  starter: { label: "Starter", price: "$29/mo", seats: "25 seats" },
  pro:     { label: "Pro",     price: "$99/mo", seats: "200 seats" },
};

type Step = "form" | "success";

export default function SignupPage() {
  const searchParams = useSearchParams();
  const initialPlan = (searchParams.get("plan") as Plan) || "free";

  // ── Form state ─────────────────────────────────────────────────────────────
  const [step, setStep] = useState<Step>("form");
  const [companyName, setCompanyName] = useState("");
  const [adminName, setAdminName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [plan, setPlan] = useState<Plan>(initialPlan);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [submittedEmail, setSubmittedEmail] = useState("");

  // ── Validation ─────────────────────────────────────────────────────────────
  const passwordMismatch = confirmPassword.length > 0 && password !== confirmPassword;
  const passwordWeak = password.length > 0 && password.length < 8;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      await orgsApi.signup({
        company_name: companyName.trim(),
        admin_name: adminName.trim(),
        email: email.trim().toLowerCase(),
        password,
        plan,
      });
      setSubmittedEmail(email.trim().toLowerCase());
      setStep("success");
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          "Something went wrong. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  // ── Success screen ──────────────────────────────────────────────────────────
  if (step === "success") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 p-6">
        <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8 text-center">
          <div className="inline-flex p-4 rounded-full bg-emerald-50 text-emerald-600 mb-5">
            <CheckCircle2 size={32} />
          </div>
          <h1 className="text-2xl font-bold mb-2">Check your email</h1>
          <p className="text-slate-500 mb-1">
            We sent a verification link to
          </p>
          <p className="font-semibold text-slate-800 mb-5">{submittedEmail}</p>
          <p className="text-sm text-slate-500 mb-6">
            Click the link in the email to activate your account and start the
            setup wizard. The link expires in 24 hours.
          </p>
          <p className="text-xs text-slate-400">
            Wrong email?{" "}
            <button
              onClick={() => setStep("form")}
              className="text-brand-600 hover:underline"
            >
              Go back
            </button>
          </p>
        </div>
      </div>
    );
  }

  // ── Signup form ─────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex flex-col">
      {/* Minimal nav */}
      <header className="px-6 py-4 flex items-center justify-between">
        <Link
          href="/"
          className="flex items-center gap-2 font-bold text-slate-800"
        >
          <Eye className="text-brand-600" size={20} />
          Employee Monitor
        </Link>
        <p className="text-sm text-slate-500">
          Already have an account?{" "}
          <Link href="/login" className="text-brand-600 hover:underline font-medium">
            Sign in
          </Link>
        </p>
      </header>

      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-lg">
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-slate-900">
              Create your account
            </h1>
            <p className="text-slate-500 text-sm mt-1">
              Set up your organization in under 2 minutes.
            </p>
          </div>

          {/* Plan selector */}
          <div className="bg-white rounded-xl border border-slate-200 p-1 flex mb-5">
            {(Object.entries(PLAN_LABELS) as [Plan, typeof PLAN_LABELS[Plan]][]).map(
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
                  <span
                    className={`text-xs ${plan === key ? "text-brand-200" : "text-slate-400"}`}
                  >
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
            <div>
              <label className="text-sm font-medium text-slate-700 block mb-1.5">
                Company name
              </label>
              <div className="relative">
                <Building2
                  size={15}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  type="text"
                  required
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="Acme Inc."
                  className="w-full pl-9 pr-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Admin name */}
            <div>
              <label className="text-sm font-medium text-slate-700 block mb-1.5">
                Your full name
              </label>
              <div className="relative">
                <User
                  size={15}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  type="text"
                  required
                  value={adminName}
                  onChange={(e) => setAdminName(e.target.value)}
                  placeholder="Jane Smith"
                  className="w-full pl-9 pr-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Work email */}
            <div>
              <label className="text-sm font-medium text-slate-700 block mb-1.5">
                Work email
              </label>
              <div className="relative">
                <Mail
                  size={15}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="jane@acme.com"
                  className="w-full pl-9 pr-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Password row */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-slate-700 block mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <Lock
                    size={15}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                  />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Min. 8 chars"
                    className={`w-full pl-9 pr-3 py-2.5 border rounded-lg text-sm focus:ring-2 focus:outline-none ${
                      passwordWeak
                        ? "border-red-300 focus:ring-red-400"
                        : "border-slate-200 focus:ring-brand-500 focus:border-brand-500"
                    }`}
                  />
                </div>
                {passwordWeak && (
                  <p className="text-xs text-red-500 mt-1">Too short</p>
                )}
              </div>

              <div>
                <label className="text-sm font-medium text-slate-700 block mb-1.5">
                  Confirm password
                </label>
                <div className="relative">
                  <Lock
                    size={15}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                  />
                  <input
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat password"
                    className={`w-full pl-9 pr-3 py-2.5 border rounded-lg text-sm focus:ring-2 focus:outline-none ${
                      passwordMismatch
                        ? "border-red-300 focus:ring-red-400"
                        : "border-slate-200 focus:ring-brand-500 focus:border-brand-500"
                    }`}
                  />
                </div>
                {passwordMismatch && (
                  <p className="text-xs text-red-500 mt-1">Doesn't match</p>
                )}
              </div>
            </div>

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || passwordMismatch || passwordWeak}
              className="w-full py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white rounded-lg font-medium text-sm flex items-center justify-center gap-2 transition mt-1"
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
