export type UserRole = "admin" | "employee";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  org_id?: string;
  created_at: string;
}

export interface Screenshot {
  id: string;
  user_id: string;
  file_url: string;
  thumbnail_url: string | null;
  file_size: number | null;
  monitor_index: number;
  os_platform: string | null;
  captured_at: string;
  uploaded_at: string;
}

export interface ScreenshotListResponse {
  total: number;
  items: Screenshot[];
}

// Latest heartbeat per employee — populated from /employees/heartbeats.
// All heartbeat-derived fields are null for employees whose agent has
// never pinged (fresh hire, broken install, etc.).
export interface HeartbeatSummary {
  user_id: string;
  full_name: string;
  email: string;
  is_active: boolean;

  agent_version: string | null;
  os_platform: string | null;
  status: string | null;
  queue_size: number | null;
  pending_review: number | null;
  captures_today: number | null;
  last_capture_at: string | null;
  last_upload_ok: boolean | null;
  last_error: string | null;
  last_seen: string | null;
}

export type Plan = "free" | "starter" | "pro" | "enterprise";

export interface Org {
  id: string;
  name: string;
  slug: string;
  plan: Plan;
  is_active: boolean;
  max_seats: number;
  capture_interval_minutes: number;
  review_window_minutes: number;
  idle_skip_minutes: number;
  retention_days: number;
  onboarding_done: boolean;
  trial_ends_at: string | null;
  created_at: string;
}
