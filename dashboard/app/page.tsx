"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/api";
import {
  Eye,
  Camera,
  ShieldCheck,
  BarChart3,
  Monitor,
  CheckCircle2,
  ArrowRight,
  Loader2,
} from "lucide-react";

// ── Plan data ──────────────────────────────────────────────────────────────────
const PLANS = [
  {
    name: "Free",
    price: "$0",
    per: "forever",
    seats: "3 seats",
    retention: "7-day history",
    highlight: false,
    cta: "Start free",
    features: ["Unlimited screenshots", "3 monitors per seat", "7-day retention", "Email support"],
  },
  {
    name: "Starter",
    price: "$29",
    per: "per month",
    seats: "25 seats",
    retention: "30-day history",
    highlight: true,
    cta: "Start Starter",
    features: ["Everything in Free", "25 seats", "30-day retention", "Priority support", "Agent auto-update"],
  },
  {
    name: "Pro",
    price: "$99",
    per: "per month",
    seats: "200 seats",
    retention: "90-day history",
    highlight: false,
    cta: "Start Pro",
    features: ["Everything in Starter", "200 seats", "90-day retention", "Audit logs", "SSO / SAML (soon)"],
  },
];

const FEATURES = [
  {
    icon: Camera,
    title: "Automatic screenshots",
    desc: "Captures every monitor silently in the background. Configurable intervals from 5 to 30 minutes.",
  },
  {
    icon: ShieldCheck,
    title: "Employee review window",
    desc: "Give employees a grace period to remove any screenshot before it leaves their machine.",
  },
  {
    icon: Monitor,
    title: "Multi-monitor support",
    desc: "Captures all connected displays. Every monitor, every seat, one dashboard.",
  },
  {
    icon: BarChart3,
    title: "Searchable history",
    desc: "Filter by employee, date range, and monitor. Jump to any moment in seconds.",
  },
];

export default function LandingPage() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  // Redirect authenticated admins straight to the dashboard
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) router.replace("/dashboard");
      else setChecking(false);
    });
  }, [router]);

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin text-brand-600" size={28} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white text-slate-900">
      {/* ── Nav ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 bg-white/80 backdrop-blur border-b border-slate-100">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2 font-bold text-lg">
            <Eye className="text-brand-600" size={22} />
            Employee Monitor
          </div>
          <nav className="flex items-center gap-2">
            <Link
              href="/login"
              className="px-4 py-1.5 text-sm text-slate-600 hover:text-slate-900 rounded-lg hover:bg-slate-50 transition"
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="px-4 py-1.5 text-sm font-medium bg-brand-600 hover:bg-brand-700 text-white rounded-lg transition"
            >
              Start free →
            </Link>
          </nav>
        </div>
      </header>

      {/* ── Hero ────────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-gradient-to-b from-slate-50 to-white pt-20 pb-24 px-6 text-center">
        {/* Background grid */}
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              "repeating-linear-gradient(0deg,#000 0,#000 1px,transparent 1px,transparent 60px),repeating-linear-gradient(90deg,#000 0,#000 1px,transparent 1px,transparent 60px)",
          }}
        />

        <div className="relative max-w-3xl mx-auto">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-brand-50 text-brand-600 text-xs font-semibold mb-6">
            <CheckCircle2 size={12} /> Free plan · no credit card required
          </span>

          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-slate-900 mb-5 leading-tight">
            Know what your team<br className="hidden sm:block" /> is working on
          </h1>

          <p className="text-lg text-slate-500 max-w-xl mx-auto mb-8 leading-relaxed">
            Automatic screenshots, multi-monitor support, and a built-in employee
            review window — deployed in under 10 minutes.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 px-6 py-3 bg-brand-600 hover:bg-brand-700 text-white font-semibold rounded-xl transition shadow-sm"
            >
              Start for free <ArrowRight size={16} />
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center gap-2 px-6 py-3 border border-slate-200 hover:bg-slate-50 text-slate-700 font-medium rounded-xl transition"
            >
              Sign in to dashboard
            </Link>
          </div>

          <p className="mt-4 text-xs text-slate-400">
            Free plan · up to 3 seats · no expiry
          </p>
        </div>

        {/* Dashboard preview */}
        <div className="relative max-w-5xl mx-auto mt-14">
          <div className="rounded-2xl border border-slate-200 bg-white shadow-2xl shadow-slate-200/60 overflow-hidden">
            {/* Fake browser chrome */}
            <div className="bg-slate-100 border-b border-slate-200 px-4 py-2.5 flex items-center gap-2">
              <div className="flex gap-1.5">
                <span className="w-3 h-3 rounded-full bg-slate-300" />
                <span className="w-3 h-3 rounded-full bg-slate-300" />
                <span className="w-3 h-3 rounded-full bg-slate-300" />
              </div>
              <div className="flex-1 mx-4 bg-white rounded-md px-3 py-1 text-xs text-slate-400 text-center border border-slate-200">
                app.employeemonitor.com/dashboard
              </div>
            </div>

            {/* Mock dashboard content */}
            <div className="flex h-64 bg-slate-50">
              {/* Sidebar */}
              <div className="w-48 bg-white border-r border-slate-100 p-3 flex flex-col gap-1">
                {["Overview", "Employees", "Screenshots"].map((item, i) => (
                  <div
                    key={item}
                    className={`px-3 py-2 rounded-lg text-xs ${
                      i === 2
                        ? "bg-brand-50 text-brand-700 font-medium"
                        : "text-slate-500"
                    }`}
                  >
                    {item}
                  </div>
                ))}
              </div>

              {/* Main content — screenshot grid */}
              <div className="flex-1 p-4">
                <div className="text-xs font-semibold text-slate-500 mb-3">
                  Recent screenshots
                </div>
                <div className="grid grid-cols-4 gap-2">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <div
                      key={i}
                      className="aspect-video rounded-lg bg-gradient-to-br from-slate-200 to-slate-300 animate-pulse"
                      style={{ animationDelay: `${i * 80}ms` }}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Features ────────────────────────────────────────────────────── */}
      <section className="py-20 px-6 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-3">Everything you need</h2>
            <p className="text-slate-500 max-w-md mx-auto">
              Built for lean teams that need clarity without complexity.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {FEATURES.map(({ icon: Icon, title, desc }) => (
              <div
                key={title}
                className="p-6 rounded-2xl border border-slate-100 hover:border-brand-200 hover:shadow-sm transition"
              >
                <div className="inline-flex p-2.5 rounded-xl bg-brand-50 text-brand-600 mb-4">
                  <Icon size={20} />
                </div>
                <h3 className="font-semibold mb-2">{title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pricing ─────────────────────────────────────────────────────── */}
      <section className="py-20 px-6 bg-slate-50">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-3">Simple, honest pricing</h2>
            <p className="text-slate-500">Scale as your team grows. Cancel any time.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {PLANS.map((plan) => (
              <div
                key={plan.name}
                className={`relative rounded-2xl p-7 flex flex-col ${
                  plan.highlight
                    ? "bg-brand-600 text-white shadow-xl shadow-brand-600/20"
                    : "bg-white border border-slate-200"
                }`}
              >
                {plan.highlight && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-amber-400 text-amber-900 text-xs font-bold px-3 py-1 rounded-full">
                    Most popular
                  </div>
                )}

                <div className="mb-5">
                  <div
                    className={`text-sm font-semibold mb-1 ${
                      plan.highlight ? "text-brand-200" : "text-slate-500"
                    }`}
                  >
                    {plan.name}
                  </div>
                  <div className="flex items-end gap-1">
                    <span className="text-4xl font-extrabold">{plan.price}</span>
                    <span
                      className={`text-sm mb-1 ${
                        plan.highlight ? "text-brand-200" : "text-slate-400"
                      }`}
                    >
                      {plan.per}
                    </span>
                  </div>
                  <div
                    className={`text-xs mt-1 ${
                      plan.highlight ? "text-brand-200" : "text-slate-400"
                    }`}
                  >
                    {plan.seats} · {plan.retention}
                  </div>
                </div>

                <ul className="flex-1 space-y-2.5 mb-6">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm">
                      <CheckCircle2
                        size={15}
                        className={`mt-0.5 flex-shrink-0 ${
                          plan.highlight ? "text-brand-200" : "text-brand-600"
                        }`}
                      />
                      <span className={plan.highlight ? "text-brand-100" : "text-slate-600"}>
                        {f}
                      </span>
                    </li>
                  ))}
                </ul>

                <Link
                  href={`/signup?plan=${plan.name.toLowerCase()}`}
                  className={`text-center py-2.5 rounded-xl font-medium text-sm transition ${
                    plan.highlight
                      ? "bg-white text-brand-600 hover:bg-brand-50"
                      : "bg-brand-600 text-white hover:bg-brand-700"
                  }`}
                >
                  {plan.cta} →
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────────────── */}
      <footer className="border-t border-slate-100 bg-white py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <Eye className="text-brand-600" size={16} />
            Employee Monitor
          </div>
          <p className="text-xs text-slate-400">
            © {new Date().getFullYear()} Employee Monitor. All rights reserved.
          </p>
          <div className="flex gap-4 text-xs text-slate-400">
            <Link href="/login" className="hover:text-slate-600">
              Sign in
            </Link>
            <Link href="/signup" className="hover:text-slate-600">
              Sign up
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
