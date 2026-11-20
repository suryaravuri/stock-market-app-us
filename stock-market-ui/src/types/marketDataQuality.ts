export interface MarketDataQualityResponse {
  symbol: string;
  timeframe: string;
  status: string;
  usable_for_breakout: boolean;

  candles_checked: number;
  valid_candles: number;
  invalid_candles: number;

  zero_volume_candles: number;
  invalid_ohlc_candles: number;

  issue_counts: Record<string, number>;

  latest_candle: {
    timestamp: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    trade_count: number;
    vwap: number;
    source: string;
    valid: boolean;
    issues: string[];
  } | null;

  volume_diagnostics: {
    latest_volume: number;
    valid_prior_volume_count: number;
    average_prior_volume: number;
    volume_ratio_raw: number;
  } | null;

  notes: string[];
}