import apiClient from "../api/client";

import type { FuturesWatch, OptionsAnalysis } from "../types/derivatives";

export interface OptionsQuery {
  optionType: "CALL" | "PUT";
  minDte: number;
  maxDte: number;
  strikeRangePercent: number;
}

export async function getOptionsAnalysis(
  symbol: string,
  query: OptionsQuery
): Promise<OptionsAnalysis> {
  const response = await apiClient.get<OptionsAnalysis>(
    `/options/analysis/${encodeURIComponent(symbol.trim().toUpperCase())}`,
    {
      params: {
        option_type: query.optionType,
        min_dte: query.minDte,
        max_dte: query.maxDte,
        strike_range_percent: query.strikeRangePercent,
      },
    }
  );

  return response.data;
}

export async function getFuturesWatch(
  underlyings: string[],
  contracts = 2
): Promise<FuturesWatch> {
  const response = await apiClient.get<FuturesWatch>("/futures/watch", {
    params: { underlyings: underlyings.join(","), contracts },
  });

  return response.data;
}
