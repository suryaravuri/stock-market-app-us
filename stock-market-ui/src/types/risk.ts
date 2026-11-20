export interface PositionSizeSetup {
  actionable: boolean;
  action: string;
  decision_reasons: string[];
  overall_score: number;
  overall_classification: string;
  risk_reward_quality: string;
}

export interface PositionSizeResult {
  allowed: boolean;
  shares: number;
  account_size: number;
  risk_percent: number;
  max_risk_amount: number;
  max_position_percent: number;
  max_position_value: number;
  entry_price: number | null;
  stop_loss: number | null;
  risk_per_share: number | null;
  position_value: number;
  actual_risk_amount: number;
  reason: string | null;
}

export interface PositionSizeResponse {
  symbol: string;
  setup: PositionSizeSetup;
  position: PositionSizeResult;
}

export interface PositionLifecycle {
  symbol: string;
  timeframe: string;

  execution_mode: string;
  persistence_mode: string;

  broker_order_submitted: boolean;
  database_mutated: boolean;

  opening_gate_passed: boolean;
  opening_gate_reason: string | null;

  processed_candles: number;
  ignored_out_of_session_candles: number;
  ignored_incomplete_candles: number;

  monitoring_mode: string | null;
  monitoring_trigger: string | null;
  monitoring_status: string | null;

  new_candles_found: number;
  duplicate_candles_skipped: number;

  state: string;
  previous_state: string | null;
  last_event: string | null;
  state_changed: boolean;

  reason: string | null;

  signal_cycle_number: number;

  entry_price: number | null;
  initial_stop: number | null;
  active_stop: number | null;

  target_1: number | null;
  target_2: number | null;

  initial_risk_per_share: number | null;

  target_1_hit: boolean;
  target_2_hit: boolean;

  opened_at: string | null;
  last_evaluated_candle_time: string | null;

  current_price: number | null;

  unrealized_per_share: number | null;
  unrealized_r: number | null;

  exit_price: number | null;
  exit_reason: string | null;
  closed_at: string | null;

  version: number | null;
}

export interface OptionAnalysis {
  status: string;
  reason: string;
  strategy_status: string;
  option_type: string | null;
  analysis_allowed: boolean;
  execution_allowed: boolean;
  contract_symbol: string | null;
  observation_id: number | null;
}

export interface PositionSizeResponse {
  symbol: string;
  setup: PositionSizeSetup;
  position: PositionSizeResult;
  option_analysis: OptionAnalysis | null;
}