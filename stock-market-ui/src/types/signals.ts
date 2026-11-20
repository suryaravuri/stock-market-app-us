export interface BreakoutConfirmation {
  symbol: string;
  timeframe: string;
  timestamp: string;

  status: string;
  confirmed: boolean;

  breakout_level: number | null;
  confirmation_price: number | null;
  buffer_price: number | null;

  volume_ratio: number | null;
  lookback_candles: number;

  min_volume_ratio: number;
  min_body_ratio: number;
  min_close_location: number;
  max_upper_wick_ratio: number;

  price_confirmed: boolean;
  volume_confirmed: boolean;
  candle_quality_confirmed: boolean;

  breakout_detected: boolean;

  follow_through_required: boolean;
  follow_through_confirmed: boolean;
  retest_confirmed: boolean;

  follow_through_status: string;

  breakout_candle_timestamp: string | null;
  follow_through_candle_timestamp: string | null;

  follow_through_close: number | null;
  follow_through_low: number | null;

  failed_quality_checks: string[];

  candle_range: number | null;
  body_ratio: number | null;
  close_location: number | null;
  upper_wick_ratio: number | null;

  ignored_zero_volume_candles: number;
  ignored_invalid_candles: number;
  ignored_out_of_session_candles: number;
  ignored_low_liquidity_candles: number;
  ignored_zero_range_candles: number;
  ignored_low_trade_count_candles: number;

  session: string;
  session_timezone: string;

  latest_volume: number | null;
  average_prior_volume: number | null;
  volume_ratio_raw: number | null;

  data_quality_note: string | null;
  reasons: string[];
}

export interface SignalLifecycle {
  symbol: string;
  timeframe: string;

  state: string;
  previous_state: string | null;
  last_event: string | null;
  state_changed: boolean;

  reason: string | null;

  observed_breakout_status: string | null;

  breakout_level: number | null;
  confirmation_price: number | null;
  confirmed_entry_price: number | null;

  signal_candle_time: string | null;

  expired: boolean;

  staleness_status: string | null;
  expiration_reason: string | null;

  signal_age_minutes: number | null;
  max_signal_age_minutes: number | null;

  pending_candles: number;
  max_pending_candles: number;

  cycle_number: number;
  cycle_started_at: string | null;

  rearmed: boolean;
  rearm_status: string | null;
  rearm_reason: string | null;

  version: number | null;

  created_at: string | null;
  updated_at: string | null;
}