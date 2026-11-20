import apiClient from "../api/client";

import type {
  AdminUser,
  AdminUserCreate,
} from "../types/adminUser";

export async function enrollUser(
  request: AdminUserCreate
): Promise<AdminUser> {
  const response = await apiClient.post<AdminUser>(
    "/admin/users",
    request
  );

  return response.data;
}