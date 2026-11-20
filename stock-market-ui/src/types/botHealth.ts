export type CheckStatus = "PASS" | "WARN" | "FAIL";

export interface ReadinessCheck {
  name: string;
  status: CheckStatus;
  detail: string;
  fix: string | null;
}

export interface ReadinessStock {
  symbol: string;
  exchange: string | null;
  trading_enabled: boolean;
  holding_style: string | null;
  latest_15min_candle: string | null;
  candle_age_minutes: number | null;
  stale: boolean;
}

export interface ReadinessWatchlist {
  watchlist_id: number;
  name: string;
  us_stocks: number;
  us_trading_enabled: number;
  indian_stocks: number;
  stocks: ReadinessStock[];
}

export interface TradingReadiness {
  evaluated_at: string;
  ready: boolean;
  headline: string;
  checks: ReadinessCheck[];
  scheduler: Record<string, unknown>;
  last_cycle: Record<string, unknown>;
  decisions_24h: {
    count: number;
    blockers: Record<string, number>;
    would_buy_if_enabled: string[];
  };
  watchlists: ReadinessWatchlist[];
}

export interface TradeDecision {
  evaluated_at: string;
  symbol: string;
  watchlist_id: number;
  outcome: "ORDER_SUBMITTED" | "NO_ORDER";
  blocker: string | null;
  would_buy_if_enabled: boolean;
  trading_enabled: boolean;
  holding_style: string | null;
  price?: number | null;
  score?: number | null;
  breakout_summary?: string;
  bounce_summary?: string;
  order_reason?: string | null;
  order_id?: string | null;
  entry_type?: string | null;
}

export interface TradeDecisionList {
  count: number;
  blockers: Record<string, number>;
  decisions: TradeDecision[];
}
