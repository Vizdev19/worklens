/**
 * Build-time-validated env vars for the marketing site.
 *
 * Why a wrapper instead of inline `process.env.NEXT_PUBLIC_FOO || "fallback"`:
 *
 *   Inline fallbacks to "http://localhost:3000" silently ship broken links
 *   to production when the env var isn't set on Vercel. The user clicks
 *   "Sign in" → browser tries to open localhost:3000 → nothing happens.
 *   No build error, no deploy failure, just confused users.
 *
 * The pattern here throws at module-import time when:
 *   - the env var is missing AND
 *   - we're in a production build (NODE_ENV === 'production')
 *
 * Next.js `next build` evaluates these modules during static page
 * generation, so a missing var fails the Vercel build with a clear
 * message — well before any user clicks a broken link.
 *
 * In `next dev`, NODE_ENV is 'development' and the localhost fallbacks
 * are used silently. That's the right behaviour: local dev should
 * "just work" without forcing every contributor to set env vars.
 */

function requireEnv(name: string, devFallback: string): string {
  const v = process.env[name];
  if (v) return v;

  // Vercel sets NODE_ENV=production for production builds. Failing here
  // turns a silent runtime bug into a loud build-time bug.
  if (process.env.NODE_ENV === "production") {
    throw new Error(
      `[marketing] Missing required environment variable: ${name}\n` +
      `Set it in Vercel → Project Settings → Environment Variables, then redeploy.\n` +
      `See backend/.env.example and the inventory in the project for expected values.`
    );
  }

  return devFallback;
}

// Backend API base URL. Marketing only calls /orgs/ for self-serve signup.
export const API_URL = requireEnv(
  "NEXT_PUBLIC_API_URL",
  "http://localhost:8000",
);

// Dashboard app URL — where "Sign in" / "Go to sign in" links go.
// Must NOT default to localhost in production builds; the requireEnv
// helper enforces this.
export const APP_URL = requireEnv(
  "NEXT_PUBLIC_APP_URL",
  "http://localhost:3000",
);
