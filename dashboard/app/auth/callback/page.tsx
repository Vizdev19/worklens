"use client";

/**
 * Supabase Auth callback handler.
 *
 * After a user clicks the email-verification link, Supabase redirects here
 * with a PKCE `code` param in the URL. The SDK exchanges it for a session
 * automatically and emits a SIGNED_IN auth-state event.
 *
 * MQ-11 fix: replaced getSession() (which races the code exchange) with
 * onAuthStateChange, so we wait for the SIGNED_IN event rather than polling
 * a snapshot that may still be null.
 *
 * ARCH-8 fix: onboarding status is read from org.onboarding_done (server)
 * instead of localStorage so it survives device switches and cache clears.
 *
 * Routing:
 *   - New org admins (onboarding not done)  → /onboarding
 *   - Returning admins                      → /dashboard
 *   - No session / expired link             → /login?error=link_expired
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase, authApi, orgsApi, setStoredUser } from "@/lib/api";
import type { Session } from "@supabase/supabase-js";
import { Loader2 } from "lucide-react";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    let settled = false;

    function redirect(path: string) {
      if (settled) return;
      settled = true;
      router.replace(path);
    }

    async function handleSession(session: Session) {
      try {
        const profile = await authApi.me(session.access_token);
        setStoredUser({
          id: profile.id,
          full_name: profile.full_name,
          role: profile.role,
          org_id: profile.org_id,
        });

        if (profile.role === "admin") {
          // ARCH-8: check server-side flag so the decision is device-agnostic
          try {
            const org = await orgsApi.me();
            redirect(org.onboarding_done ? "/dashboard" : "/onboarding");
          } catch {
            // Can't reach org endpoint — fall back to dashboard
            redirect("/dashboard");
          }
        } else {
          redirect("/dashboard");
        }
      } catch {
        redirect("/login");
      }
    }

    // MQ-11: listen for the code-exchange completion instead of calling
    // getSession(), which may return null if the exchange hasn't finished yet.
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        if (event === "SIGNED_IN" && session) {
          // Unsubscribe immediately so we only handle the first SIGNED_IN event.
          subscription.unsubscribe();
          await handleSession(session);
        }
      },
    );

    // Safety net: if no SIGNED_IN event fires within 12 seconds the link is
    // expired or already used — send the user back to login.
    const timeout = setTimeout(
      () => redirect("/login?error=link_expired"),
      12_000,
    );

    return () => {
      subscription.unsubscribe();
      clearTimeout(timeout);
    };
  }, [router]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-slate-50">
      <Loader2 className="animate-spin text-brand-600" size={36} />
      <p className="text-slate-500 text-sm">Verifying your email…</p>
    </div>
  );
}
