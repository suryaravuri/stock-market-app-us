export interface ActiveValidationRun {
  validation_run_id: number;
  strategy_version: string;
  validation_phase: string;
  execution_mode: string;
  status: string;
  baseline_hash: string;
  baseline_status: string;
  baseline_note: string | null;
  started_at: string;
  completed_at: string | null;
  broker_order_submitted: boolean;
}

export interface ValidationProgress {
  validation_run_id: number;
  strategy_version: string;
  status: string;
  baseline_status: string;

  signals_observed: number;
  breakouts_detected: number;
  follow_through_confirmed: number;
  entries_confirmed: number;

  positions_opened: number;
  positions_closed: number;

  wins: number;
  losses: number;
  breakeven: number;

  execution_mode: string;
  isolated_test_positions_included: boolean;
  broker_order_submitted: boolean;
}