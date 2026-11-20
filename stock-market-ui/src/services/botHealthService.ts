import apiClient from "../api/client";

import type { TradeDecisionList, TradingReadiness } from "../types/botHealth";

export async function getTradingReadiness(): Promise<TradingReadiness> {
  const response = await apiClient.get<TradingReadiness>("/diagnostics/trading-readiness");
  return response.data;
}

export async function getTradeDecisions(
  symbol?: string,
  onlyBlocked = false,
  limit = 300
): Promise<TradeDecisionList> {
  const response = await apiClient.get<TradeDecisionList>("/diagnostics/decisions", {
    params: {
      symbol: symbol?.trim() ? symbol.trim().toUpperCase() : undefined,
      only_blocked: onlyBlocked,
      limit,
    },
  });
  return response.data;
}
