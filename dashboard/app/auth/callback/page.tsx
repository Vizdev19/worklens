"use client";

/**
 * Supabase Auth callback handler.
 *
 * After a user clicks the email-verification link, Supabase redirects here.
 * The Supabase JS client exchanges the code for a session automatically.
 *
 * Routing:
 *   - New org admins (onboarding not done)  → /onboarding
 *   - Returning admins                      → /dashboard
 *   - No session (expired/used link)        → /login?error=link_expired
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase, authApi, setStoredUser } from "@/lib/api";
import { Loader2 } from "lucide-react";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const handle = async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session) {
        router.replace("/login?error=link_expired");
        return;
      }

      try {
        const profile = await authApi.me(session.access_token);
        setStoredUser({
          id: profile.id,
          full_name: profile.full_name,
          role: profile.role,
          org_id: profile.org_id,
        });

        // First-time org admin: send to onboarding wizard.
        // Returning user: send to dashboard.
        const onboardingDone = localStorage.getItem("em_onboarding_done");
        if (!onboardingDone && profile.role === "admin") {
          router.replace("/onboarding");
        } else {
          router.replace("/dashboard");
        }
      } catch {
        router.replace("/login");
      }
    };

    handle();
  }, [router]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-slate-50">
      <Loader2 className="animate-spin text-brand-600" size={36} />
      <p className="text-slate-500 text-sm">Verifying your email…</p>
    </div>
  );
}
