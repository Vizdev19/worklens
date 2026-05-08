export type UserRole = "admin" | "employee";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
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

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  employee_id: string;
  full_name: string;
  role: UserRole;
}
