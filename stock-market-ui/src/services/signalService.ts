import apiClient from "../api/client";

import type {
  BreakoutConfirmation,
  SignalLifecycle,
} from "../types/signals";

export async function getBreakoutConfirmation(
  symbol: string
): Promise<BreakoutConfirmation> {
  const response = await apiClient.get<BreakoutConfirmation>(
    `/analysis/${symbol}/breakout-confirmation`
  );

  return response.data;
}

export async function getSignalLifecycle(
  symbol: string
): Promise<SignalLifecycle> {
  const response = await apiClient.get<SignalLifecycle>(
    `/analysis/${symbol}/signal-lifecycle`
  );

  return response.data;
}