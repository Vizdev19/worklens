import axios, { AxiosError } from "axios";
import { createClient } from "@supabase/supabase-js";
import type {
  User,
  Screenshot,
  ScreenshotListResponse,
  Org,
  HeartbeatSummary,
} from "@/types/api";

const baseURL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Supabase client ──────────────────────────────────────────────────────────
// Uses the anon key — safe to expose. Server-side operations that need
// elevated permissions use the service key from the backend only.
export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
);

export const api = axios.create({ baseURL });

// ── User profile cache (role, full_name, org_id) ─────────────────────────────
// We store only the profile metadata — Supabase client manages the JWT.
const USER_KEY = "em_user";

export function setStoredUser(u: {
  id: string;
  full_name: string;
  role: string;
  org_id?: string;
}) {
  if (typeof window !== "undefined")
    localStorage.setItem(USER_KEY, JSON.stringify(u));
}

export function getStoredUser(): {
  id: string;
  full_name: string;
  role: string;
  org_id?: string;
} | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function clearStoredUser() {
  if (typeof window !== "undefined") localStorage.removeItem(USER_KEY);
}

// ── Inject Supabase JWT into every API request ───────────────────────────────
// Supabase client auto-refreshes tokens in the background; we just pull the
// current session before each call.
api.interceptors.request.use(async (config) => {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`;
  }
  return config;
});

// ── Retry once on 401 after Supabase refreshes the session ───────────────────
api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as any;
    if (error.response?.status === 401 && !original?._retry) {
      original._retry = true;
      const {
        data: { session },
      } = await supabase.auth.refreshSession();
      if (session?.access_token) {
        original.headers.Authorization = `Bearer ${session.access_token}`;
        return api(original);
      }
      // Refresh failed — send user to login
      if (typeof window !== "undefined") window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

// ── Auth API ─────────────────────────────────────────────────────────────────

export const authApi = {
  /**
   * Sign in with Supabase, then fetch the local profile (role, org_id).
   * Returns the User profile so callers can gate on role immediately.
   */
  login: async (email: string, password: string): Promise<User> => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw { response: { data: { detail: error.message } } };

    // Fetch profile using the fresh session token directly (interceptor may
    // not have propagated yet for this first call).
    const profile = await authApi.me(data.session!.access_token);
    setStoredUser({
      id: profile.id,
      full_name: profile.full_name,
      role: profile.role,
      org_id: profile.org_id,
    });
    return profile;
  },

  logout: async () => {
    await supabase.auth.signOut();
    clearStoredUser();
  },

  /** Fetch the current user's profile from our backend. */
  me: async (token?: string): Promise<User> => {
    const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
    return (await api.get<User>("/employees/me", { headers })).data;
  },
};

// ── Employees API ─────────────────────────────────────────────────────────────

export const employeesApi = {
  list: async () => (await api.get<User[]>("/employees/")).data,
  get: async (id: string) => (await api.get<User>(`/employees/${id}`)).data,
  create: async (body: { email: string; full_name: string; password: string }) =>
    (await api.post<User>("/employees/", body)).data,
  deactivate: async (id: string) =>
    (await api.patch(`/employees/${id}/deactivate`)).data,
  activate: async (id: string) =>
    (await api.patch(`/employees/${id}/activate`)).data,
  // Latest heartbeat per employee in the calling admin's org. Drives
  // the "last seen / agent version / status" columns on /dashboard/employees.
  heartbeats: async () =>
    (await api.get<HeartbeatSummary[]>("/employees/heartbeats")).data,
};

// ── Orgs API ──────────────────────────────────────────────────────────────────

export const orgsApi = {
  /** Public — create org + admin account. Supabase sends verification email. */
  signup: async (body: {
    company_name: string;
    admin_name: string;
    email: string;
    password: string;
    plan?: string;
  }) => (await axios.post(`${baseURL}/orgs/`, body)).data as { message: string; email: string; org_id: string },

  me: async () => (await api.get<Org>("/orgs/me")).data,

  update: async (body: {
    name?: string;
    capture_interval_minutes?: number;
    review_window_minutes?: number;
    idle_skip_minutes?: number;
    onboarding_done?: boolean;
  }) => (await api.patch<Org>("/orgs/me", body)).data,
};

// ── Screenshots API ───────────────────────────────────────────────────────────

export const screenshotsApi = {
  list: async (params: {
    employee_id?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    page_size?: number;
  }) =>
    (await api.get<ScreenshotListResponse>("/screenshots/", { params })).data,
};
