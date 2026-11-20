export interface Stock {
  stock_id: number;
  symbol: string;
  company_name: string;
  exchange: string;
  asset_type?: string;
  sector?: string | null;
  industry?: string | null;
  tradable?: boolean;
  active?: boolean;
}

export interface Watchlist {
  watchlist_id: number;
  name: string;
  description?: string | null;
  active?: boolean;
}

export interface WatchlistStock {
  watchlist_id: number;
  stock_id: number;
  priority: number;
  analysis_enabled: boolean;
  trading_enabled: boolean;

  profit_target_percent: number;
  loss_limit_percent: number;

  added_at?: string;
  stock: Stock;
}

export interface CreateStockRequest {
  symbol: string;
  company_name: string;
  exchange: string;
  asset_type: string;
  sector: string;
  industry: string;
  tradable: boolean;
  active: boolean;
}

export interface AddWatchlistStockRequest {
  stock_id: number;
  priority: number;
  analysis_enabled: boolean;
  trading_enabled: boolean;

  profit_target_percent?: number;
  loss_limit_percent?: number;
}

export interface UpdateWatchlistStockRequest {
  priority: number;
  analysis_enabled: boolean;
  trading_enabled: boolean;

  profit_target_percent?: number;
  loss_limit_percent?: number;
}
