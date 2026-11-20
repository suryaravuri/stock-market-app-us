export interface BreakoutCandleRow {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  average_prior_volume: number | null;
  volume_ratio: number | null;
  breakout_level: number | null;
  confirmation_price: number | null;
  atr_14: number | null;
  price_ok: boolean;
  volume_ok: boolean;
  candle_ok: boolean;
  body_ratio: number | null;
  close_location: number | null;
  upper_wick_ratio: number | null;
  status: string;
}

export interface BreakoutDiagnostics {
  symbol: string;
  timeframe: string;
  session_timezone: string;
  data_feed: string;
  data_feed_note: string | null;
  rules: {
    lookback_candles: number;
    breakout_level: string;
    confirmation_buffer: string;
    min_volume_ratio: number;
    min_body_ratio: number;
    min_close_location: number;
    max_upper_wick_ratio: number;
    note: string;
  };
  summary: {
    candles_checked: number;
    price_breakouts: number;
    blocked_by_volume: number;
    blocked_by_candle_quality: number;
    confirmed_breakouts: number;
    notes: string[];
  };
  candles: BreakoutCandleRow[];
}
