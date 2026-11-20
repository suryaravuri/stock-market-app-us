import apiClient from "../api/client";

import type { BreakoutDiagnostics } from "../types/diagnostics";

export async function getBreakoutDiagnostics(
  symbol: string,
  rows = 30
): Promise<BreakoutDiagnostics> {
  const response = await apiClient.get<BreakoutDiagnostics>(
    `/diagnostics/breakout/${encodeURIComponent(symbol.trim().toUpperCase())}`,
    { params: { rows } }
  );
  return response.data;
}
