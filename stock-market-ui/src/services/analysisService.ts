import apiClient from "../api/client";

import type {
  AnalysisSummary,
  MultiTimeframeAnalysis,
} from "../types/analysis";
import type { MarketDataQualityResponse } from "../types/marketDataQuality";


export async function getAnalysisSummary(
  symbol: string
): Promise<AnalysisSummary> {
  const response = await apiClient.get<AnalysisSummary>(
    `/analysis/${symbol}/summary`
  );

  return response.data;
}

export async function getMultiTimeframeAnalysis(
  symbol: string
): Promise<MultiTimeframeAnalysis> {
  const response = await apiClient.get<MultiTimeframeAnalysis>(
    `/analysis/${symbol}/multi-timeframe`
  );

  return response.data;
}



export async function getMarketDataQuality(
  symbol: string
): Promise<MarketDataQualityResponse> {
  const response =
    await apiClient.get<MarketDataQualityResponse>(
      `/analysis/${symbol}/market-data-quality`,
      {
        params: {
          timeframe: "15Min",
        },
      }
    );

  return response.data;
}