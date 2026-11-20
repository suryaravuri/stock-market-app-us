import axios from "axios";

import { tokenService } from "../services/tokenService";

const apiClient = axios.create({
  baseURL:
    import.meta.env.VITE_API_BASE_URL ||
    (import.meta.env.DEV
      ? "http://127.0.0.1:8000/api/v1"
      : "/api/v1"),
});

apiClient.interceptors.request.use((config) => {
  const token = tokenService.getToken();

  if (token) {
    config.headers.Authorization =
      `Bearer ${token}`;
  }

  return config;
});

export default apiClient;