import apiClient from "../api/client";
import type { MarketCode } from "../types/market";
import type { MonitorStatus } from "../types/monitorStatus";

export const getMonitorStatus = async (
  watchlistId: number,
  market?: MarketCode
): Promise<MonitorStatus> => {
  const response = await apiClient.get<MonitorStatus>(
    `/watchlists/${watchlistId}/monitor-status`,
    { params: market ? { market } : undefined }
  );

  return response.data;
};
