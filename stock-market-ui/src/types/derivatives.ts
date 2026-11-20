export interface OptionCandidateRow {
  contract_symbol: string;
  strike_price: number;
  expiration_date: string;
  dte: number;
  bid_price: number | null;
  ask_price: number | null;
  spread_percent: number | null;
  open_interest: number;
  delta: number | null;
  implied_volatility: number | null;
  qualified: boolean;
  reason: string;
}

export interface OptionGreeks {
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
  rho: number | null;
}

export interface SelectedOption {
  contract_symbol: string;
  option_type: string;
  strike_price: number;
  expiration_date: string;
  dte: number;
  bid_price: number;
  ask_price: number;
  midpoint: number;
  spread_percent: number;
  open_interest: number;
  implied_volatility: number | null;
  greeks: OptionGreeks | null;
  cost_per_contract: number;
  max_loss_per_contract: number;
  breakeven_at_expiry: number;
}

export interface OptionsAnalysis {
  symbol: string;
  underlying_price: number;
  option_type: "CALL" | "PUT";
  analysis_only: boolean;
  orders_enabled: boolean;
  signal: {
    state: string;
    score: number;
    actionable: boolean;
    recommendation: string | null;
  };
  gate: {
    status: string;
    reason: string;
    analysis_allowed: boolean;
    execution_allowed: boolean;
  };
  filters: {
    min_dte: number;
    max_dte: number;
    strike_range_percent: number;
    max_spread_percent: number;
    min_open_interest: number;
  };
  selection_status: string;
  selection_reason: string;
  candidates_examined: number;
  candidates_qualified: number;
  selected: SelectedOption | null;
  candidates: OptionCandidateRow[];
  data_feed_note: string;
}

export interface FutureContractRow {
  underlying: string;
  exchange: "NFO" | "MCX" | string;
  tradingsymbol: string;
  expiry: string;
  days_to_expiry: number;
  lot_size: number;
  tick_size: number | null;
  last_price: number | null;
  change_percent: number | null;
  volume: number | null;
  open_interest: number | null;
  spot_price: number | null;
  basis_points: number | null;
  basis_percent: number | null;
  notional_per_lot: number | null;
  rupees_per_point_per_lot: number | null;
  margin_per_lot: number | null;
}

export interface FuturesWatch {
  as_of: string;
  watch_only: boolean;
  orders_enabled: boolean;
  contracts: FutureContractRow[];
  not_found: string[];
  risk_note: string;
}
