export type DatasetStatus = "UPLOADING" | "READY" | "FAILED" | "PURGED";
export type RunStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";

export interface BacktestDataset {
  backtest_dataset_id: number;
  symbol: string;
  source_timezone: string;
  status: DatasetStatus;
  base_timeframe: string | null;
  chunks_received: number;
  rows_received: number;
  rows_rejected: number;
  first_bar: string | null;
  last_bar: string | null;
  bars_by_timeframe: Record<string, number> | null;
  message: string | null;
  created_at: string;
}

export interface BacktestSummary {
  starting_cash: number | null;
  ending_equity: number | null;
  total_return_percent: number | null;
  cagr_percent: number | null;
  max_drawdown_percent: number | null;
  sharpe_ratio: number | null;
  buy_and_hold_return_percent: number | null;
  trades: number;
  win_rate_percent: number | null;
  profit_factor: number | null;
  average_r_multiple: number | null;
  exit_reasons: Record<string, number>;
  evaluation_errors?: Record<string, number>;
  skipped_entries?: Record<string, number>;
}

export interface BacktestRun {
  backtest_run_id: number;
  status: RunStatus;
  symbols: string[];
  start_date: string;
  end_date: string;
  parameters: Record<string, unknown>;
  progress_percent: number;
  message: string | null;
  created_at: string;
  finished_at: string | null;
  summary?: BacktestSummary | null;
  results?: {
    overall?: { summary?: BacktestSummary };
    by_symbol?: Record<string, BacktestSummary>;
  } | null;
}

export interface BacktestCreateRequest {
  symbols: string[];
  start_date: string;
  end_date: string;
  starting_cash: number;
  data_source: "ALPACA" | "UPLOAD";
}

/** One candle row as sent to the API (the CSV file itself is never sent). */
export interface CandleRow {
  time: string;
  open: number | string;
  high: number | string;
  low: number | string;
  close: number | string;
  volume: number | string;
}
