import apiClient from "../api/client";

import type { AlertSource, MarketAlert } from "../types/alerts";

export async function getAlerts(source?: AlertSource, limit = 100): Promise<MarketAlert[]> {
  const response = await apiClient.get<MarketAlert[]>("/alerts", {
    params: { limit, ...(source ? { source } : {}) },
  });
  return response.data;
}
