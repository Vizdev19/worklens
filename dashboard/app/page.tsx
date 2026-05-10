"use client";

/**
 * Root of the dashboard app (app.employeemonitor.com/).
 * Redirect to /dashboard if logged in, otherwise to /login.
 * The public marketing site (employeemonitor.com) handles the landing page.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/api";
import { Loader2 } from "lucide-react";

export default function Root() {
  const router = useRouter();
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      router.replace(session ? "/dashboard" : "/login");
    });
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <Loader2 className="animate-spin text-brand-600" size={28} />
    </div>
  );
}
