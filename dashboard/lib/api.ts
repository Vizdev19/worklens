import axios, { AxiosError } from "axios";
import type {
  User,
  Screenshot,
  ScreenshotListResponse,
  TokenResponse,
} from "@/types/api";

const baseURL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({ baseURL });

// ── Token storage (localStorage for simplicity — single-user phase) ─────────
const ACCESS_KEY = "em_access_token";
const REFRESH_KEY = "em_refresh_token";
const USER_KEY = "em_user";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}
export function setAccessToken(t: string) {
  localStorage.setItem(ACCESS_KEY, t);
}
export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}
export function setRefreshToken(t: string) {
  localStorage.setItem(REFRESH_KEY, t);
}
export function setStoredUser(u: { id: string; full_name: string; role: string }) {
  localStorage.setItem(USER_KEY, JSON.stringify(u));
}
export function getStoredUser() {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}
export function clearAuth() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
}

// ── Inject auth header ───────────────────────────────────────────────────────
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Auto-refresh on 401 ──────────────────────────────────────────────────────
let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  try {
    const res = await axios.post<TokenResponse>(
      `${baseURL}/auth/refresh`,
      { refresh_token: refresh },
    );
    setAccessToken(res.data.access_token);
    setRefreshToken(res.data.refresh_token);
    return res.data.access_token;
  } catch {
    clearAuth();
    return null;
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as any;
    if (error.response?.status === 401 && !original?._retry) {
      original._retry = true;
      refreshing ||= refreshAccessToken().finally(() => (refreshing = null));
      const token = await refreshing;
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      }
      if (typeof window !== "undefined") window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

// ── API methods ──────────────────────────────────────────────────────────────

export const authApi = {
  login: async (email: string, password: string) => {
    const res = await api.post<TokenResponse>("/auth/login", { email, password });
    setAccessToken(res.data.access_token);
    setRefreshToken(res.data.refresh_token);
    setStoredUser({
      id: res.data.employee_id,
      full_name: res.data.full_name,
      role: res.data.role,
    });
    return res.data;
  },
  logout: async () => {
    const refresh = getRefreshToken();
    if (refresh) {
      try {
        await api.post("/auth/logout", { refresh_token: refresh });
      } catch {
        /* ignore */
      }
    }
    clearAuth();
  },
  me: async () => (await api.get<User>("/employees/me")).data,
};

export const employeesApi = {
  list: async () => (await api.get<User[]>("/employees/")).data,
  get: async (id: string) => (await api.get<User>(`/employees/${id}`)).data,
};

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
