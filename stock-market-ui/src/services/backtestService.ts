import apiClient from "../api/client";
import type {
  BacktestCreateRequest,
  BacktestDataset,
  BacktestRun,
  CandleRow,
} from "../types/backtest";

export const listBacktests = async (): Promise<BacktestRun[]> =>
  (await apiClient.get<BacktestRun[]>("/backtests")).data;

export const getBacktest = async (id: number): Promise<BacktestRun> =>
  (await apiClient.get<BacktestRun>(`/backtests/${id}`)).data;

export const createBacktest = async (req: BacktestCreateRequest): Promise<BacktestRun> =>
  (await apiClient.post<BacktestRun>("/backtests", req)).data;

export const listDatasets = async (): Promise<BacktestDataset[]> =>
  (await apiClient.get<BacktestDataset[]>("/backtests/datasets")).data;

export const createDataset = async (
  symbol: string,
  sourceTimezone: string
): Promise<BacktestDataset> =>
  (
    await apiClient.post<BacktestDataset>("/backtests/datasets", {
      symbol,
      source_timezone: sourceTimezone,
    })
  ).data;

export const uploadChunk = async (
  datasetId: number,
  chunkIndex: number,
  rows: CandleRow[]
): Promise<{ rows_received: number; rows_rejected: number }> =>
  (
    await apiClient.post(`/backtests/datasets/${datasetId}/chunks`, {
      chunk_index: chunkIndex,
      rows,
    })
  ).data;

export const completeDataset = async (datasetId: number): Promise<BacktestDataset> =>
  (await apiClient.post<BacktestDataset>(`/backtests/datasets/${datasetId}/complete`)).data;

export const deleteDataset = async (datasetId: number): Promise<void> => {
  await apiClient.delete(`/backtests/datasets/${datasetId}`);
};
