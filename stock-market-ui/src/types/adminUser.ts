import type { UserRole } from "./auth";

export interface AdminUserCreate {
  email: string;
  full_name?: string;
  temporary_password: string;
  role: UserRole;
}

export interface AdminUser {
  id: number;
  email: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
}