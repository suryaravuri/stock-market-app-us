export type TradeMode = "LIVE" | "DRY_RUN";

export interface ClosedTrade {
  exchange: string;
  tradingsymbol: string;
  product: string;
  quantity: number;
  buy_price: number;
  sell_price: number;
  opened_at: string;
  closed_at: string;
  pnl: number;
  return_percent: number;
}

export interface OpenPosition {
  exchange: string;
  tradingsymbol: string;
  product: string;
  quantity: number;
  average_price: number;
  opened_at: string;
  last_price: number | null;
  unrealized_pnl: number | null;
}

export interface UnmatchedSell {
  exchange: string;
  tradingsymbol: string;
  product: string;
  quantity: number;
  price: number;
  timestamp: string;
}

export interface ZerodhaOrderRow {
  id: number;
  kite_order_id: string | null;
  status: string;
  exchange: string;
  tradingsymbol: string;
  side: string;
  product: string;
  order_type: string;
  quantity: number;
  limit_price: number;
  last_price: number | null;
  reasons: string[];
  kite_status: string | null;
  kite_status_message: string | null;
  filled_quantity: number | null;
  average_price: number | null;
  created_at: string;
}

export interface TradeSummary {
  realized_pnl: number;
  unrealized_pnl: number;
  unrealized_complete: boolean;
  closed_trades: number;
  wins: number;
  losses: number;
  win_rate_percent: number | null;
  average_win: number | null;
  average_loss: number | null;
  best_trade: number | null;
  worst_trade: number | null;
  open_positions: number;
  unmatched_sells: number;
  daily_pnl: { date: string; pnl: number }[];
  per_symbol: {
    tradingsymbol: string;
    trades: number;
    wins: number;
    realized_pnl: number;
  }[];
}

export interface TradeSyncInfo {
  trades_seen?: number;
  trades_new?: number;
  orders_updated?: number;
  synced_at?: string;
  error: string | null;
}

export interface TradeStatistics {
  mode: TradeMode;
  zerodha_connected: boolean;
  tracking_since: string | null;
  notes: string[];
  sync: TradeSyncInfo | null;
  prices_error: string | null;
  summary: TradeSummary;
  order_counts: Record<string, number>;
  closed_trades: ClosedTrade[];
  open_positions: OpenPosition[];
  unmatched_sells: UnmatchedSell[];
  recent_orders: ZerodhaOrderRow[];
}
