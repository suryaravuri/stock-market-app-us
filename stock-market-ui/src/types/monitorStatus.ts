// export interface MonitorStatus {
//   watchlist_id: number;
//   watchlist_name: string;
//   timeframe: string;

//   execution_mode: string;
//   data_status: "PASS" | "DEGRADED" | "FAIL";

//   symbols_checked: number;
//   symbols_passed: number;
//   symbols_degraded: number;
//   symbols_failed: number;

//   eligible_for_signal_analysis: number;
//   blocked_stocks: number;

//   expected_latest_completed_candle: string | null;
//   latest_available_candle: string | null;

//   session_timezone: string;
//   evaluated_at: string;

//   broker_order_submitted: boolean;
//   database_mutated: boolean;
//   production_position_tables_mutated: boolean;
// }

export interface MonitorSymbolStatus {
  stock_id: number;
  symbol: string;
  timeframe: string;

  status: "PASS" | "DEGRADED" | "FAIL";
  eligible_for_signal_analysis: boolean;

  latest_regular_session_candle: string | null;
  expected_latest_completed_candle: string | null;

  freshness_lag_bars: number;

  candles_examined: number;
  valid_regular_completed_candles: number;
  required_history_candles: number;

  indicator_ready: boolean;

  duplicate_timestamp_count: number;
  intraday_gap_count: number;

  latest_candle_valid: boolean;
  latest_candle_issues: string[];

  reasons: string[];
}

export interface MonitorStatus {
  watchlist_id: number;
  watchlist_name: string;
  timeframe: string;

  execution_mode: string;
  data_status: "PASS" | "DEGRADED" | "FAIL";

  symbols_checked: number;
  symbols_passed: number;
  symbols_degraded: number;
  symbols_failed: number;

  eligible_for_signal_analysis: number;
  blocked_stocks: number;

  expected_latest_completed_candle: string | null;
  latest_available_candle: string | null;

  session_timezone: string;
  evaluated_at: string;

  broker_order_submitted: boolean;
  database_mutated: boolean;
  production_position_tables_mutated: boolean;

  results: MonitorSymbolStatus[];
}