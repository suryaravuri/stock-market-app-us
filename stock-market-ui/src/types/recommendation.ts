export interface RecommendationStock {
  stock_id: number;
  symbol: string;
  company_name: string;
  exchange: string;
  priority: number;
  current_price: number | null;
  overall_score: number | null;
  overall_classification: string | null;
  risk_reward_quality: string | null;
  rr_1: number | null;
  rr_2: number | null;
  entry: number | null;
  stop_loss: number | null;
  target_1: number | null;
  target_2: number | null;
  action: string;
  decision_reasons: string[];
  actionable: boolean;
  error: string | null;
}

export interface WatchlistScanResponse {
  watchlist_id: number;
  watchlist_name: string;
  total_stocks: number;
  actionable_count: number;
  stocks: RecommendationStock[];
}