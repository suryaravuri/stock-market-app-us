import apiClient from "../api/client";

import type {
  HeatmapPeriod,
  PnlGroup,
  PnlRange,
  PnlReport,
  SectorHeatmap,
} from "../types/performance";

export async function getSectorHeatmap(period: HeatmapPeriod): Promise<SectorHeatmap> {
  const response = await apiClient.get<SectorHeatmap>("/analytics/sector-heatmap", {
    params: { period },
  });
  return response.data;
}

export async function getPnlReport(group: PnlGroup, range: PnlRange): Promise<PnlReport> {
  const response = await apiClient.get<PnlReport>("/analytics/pnl", {
    params: { group, range },
  });
  return response.data;
}
