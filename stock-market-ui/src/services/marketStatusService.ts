import apiClient from "../api/client";
import type { MarketsStatus } from "../types/market";

export const getMarketsStatus = async (): Promise<MarketsStatus> => {
  const response = await apiClient.get<MarketsStatus>("/markets/status");
  return response.data;
};
