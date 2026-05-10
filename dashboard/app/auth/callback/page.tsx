"use client";

/**
 * Supabase Auth callback handler.
 *
 * After a user clicks the email-verification link, Supabase redirects here
 * with a code in the query string. The Supabase JS client exchanges it for
 * a session automatically when `detectSessionInUrl` is true (default).
 *
 * We just wait for the session to settle, then route accordingly:
 *   - Verified admin  → /dashboard (or /onboarding if first login)
 *   - No session yet  → /login  (e.g. expired link)
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/api";
import { authApi, setStoredUser } from "@/lib/api";
import { Loader2 } from "lucide-react";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const handle = async () => {
      // Give Supabase a moment to exchange the code from the URL hash / query.
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session) {
        // Link may have been expired or already used
        router.replace("/login?error=link_expired");
        return;
      }

      try {
        // Fetch local profile so we can check role and cache it
        const profile = await authApi.me(session.access_token);
        setStoredUser({
          id: profile.id,
          full_name: profile.full_name,
          role: profile.role,
          org_id: profile.org_id,
        });

        // First-time org admins go to onboarding; returning users go to dashboard
        router.replace("/dashboard");
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
