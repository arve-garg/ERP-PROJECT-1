export interface AuthUser {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  roles: string[];
  totp_required: boolean;
  approval_status: "pending" | "approved" | "rejected";
  employee_number?: string | null;
  department_name?: string | null;
  designation_title?: string | null;
  phone?: string | null;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: AuthUser;
}

export interface ApiError {
  detail?: string;
  otp_code?: string[];
  [key: string]: unknown;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Notification {
  id: number;
  category: string;
  title: string;
  body: string;
  target_url: string;
  read_at: string | null;
  is_read: boolean;
  created_at: string;
}

export interface ActivityItem {
  id: number;
  actor_email: string | null;
  verb: string;
  target_type: string;
  target_id: string;
  metadata: Record<string, unknown>;
  created_at: string;
}
