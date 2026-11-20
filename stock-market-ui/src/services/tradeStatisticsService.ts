import apiClient from "../api/client";

import type {
  TradeMode,
  TradeStatistics,
  TradeSyncInfo,
} from "../types/tradeStatistics";

export async function getTradeStatistics(
  mode: TradeMode
): Promise<TradeStatistics> {
  const response = await apiClient.get<TradeStatistics>(
    "/zerodha/statistics",
    { params: { mode } }
  );

  return response.data;
}

export async function syncZerodhaTrades(): Promise<TradeSyncInfo> {
  const response = await apiClient.post<TradeSyncInfo>("/zerodha/trades/sync");

  return response.data;
}
