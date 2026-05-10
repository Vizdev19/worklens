"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Eye,
  LayoutDashboard,
  Users,
  Image as ImageIcon,
  LogOut,
  Loader2,
} from "lucide-react";
import {
  authApi,
  supabase,
  getStoredUser,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/employees", label: "Employees", icon: Users },
  { href: "/dashboard/screenshots", label: "Screenshots", icon: ImageIcon },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const qc = useQueryClient();
  const [user, setUser] = useState<any>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
        return;
      }
      setUser(getStoredUser());
    });
  }, [router]);

  async function performLogout() {
    setLoggingOut(true);
    try {
      await authApi.logout();           // calls /auth/logout + clears local tokens
    } catch {
      /* ignore — still clear local state */
    }
    qc.clear();                         // wipe cached employee/screenshot data
    router.replace("/login");
  }

  if (!user) return null;

  return (
    <div className="min-h-screen flex">
      <aside className="w-64 bg-white border-r flex flex-col">
        <div className="p-5 border-b flex items-center gap-2">
          <Eye className="text-brand-600" size={22} />
          <span className="font-bold">Employee Monitor</span>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active =
              href === "/dashboard"
                ? pathname === href
                : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition",
                  active
                    ? "bg-brand-50 text-brand-700 font-medium"
                    : "text-slate-600 hover:bg-slate-50",
                )}
              >
                <Icon size={18} />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="p-3 border-t">
          <div className="px-3 py-2 text-sm">
            <div className="font-medium">{user.full_name}</div>
            <div className="text-xs text-slate-500 capitalize">{user.role}</div>
          </div>
          <button
            onClick={() => setShowConfirm(true)}
            disabled={loggingOut}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            <LogOut size={16} />
            Logout
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">{children}</main>

      {showConfirm && (
        <div
          className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
          onClick={() => !loggingOut && setShowConfirm(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 rounded-lg bg-red-50 text-red-600">
                <LogOut size={18} />
              </div>
              <h2 className="font-semibold text-lg">Sign out?</h2>
            </div>
            <p className="text-sm text-slate-600 mb-5">
              You'll need to sign in again to view the dashboard.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowConfirm(false)}
                disabled={loggingOut}
                className="px-4 py-2 border rounded-lg hover:bg-slate-50 text-sm font-medium disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={performLogout}
                disabled={loggingOut}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium flex items-center gap-2 disabled:opacity-50"
              >
                {loggingOut && <Loader2 size={14} className="animate-spin" />}
                {loggingOut ? "Signing out..." : "Sign out"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
