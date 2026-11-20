import apiClient from "../api/client";

import type {
  PositionLifecycle,
  PositionSizeResponse,
} from "../types/risk";

export async function getPositionSize(
  symbol: string,
  accountSize = 10000,
  riskPercent = 1
): Promise<PositionSizeResponse> {
  const response = await apiClient.get<PositionSizeResponse>(
    `/analysis/${symbol}/position-size`,
    {
      params: {
        account_size: accountSize,
        risk_percent: riskPercent,
      },
    }
  );

  return response.data;
}

export async function getPositionLifecycle(
  symbol: string
): Promise<PositionLifecycle> {
  const response = await apiClient.get<PositionLifecycle>(
    `/analysis/${symbol}/position-lifecycle`
  );

  return response.data;
}