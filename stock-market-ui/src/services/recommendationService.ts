import apiClient from "../api/client";
import type { MarketCode } from "../types/market";
import type { WatchlistScanResponse } from "../types/recommendation";

export const getWatchlistRecommendations = async (
  watchlistId: number,
  market?: MarketCode
): Promise<WatchlistScanResponse> => {
  const response = await apiClient.get<WatchlistScanResponse>(
    `/watchlists/${watchlistId}/scan`,
    { params: market ? { market } : undefined }
  );

  return response.data;
};
