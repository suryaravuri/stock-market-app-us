export type AlertSource = "EARLY_BREAKOUT" | "TRADINGVIEW";

export interface MarketAlert {
  id: number;
  created_at: string;
  source: AlertSource;
  symbol: string;
  candle_start: string | null;
  price: number | null;
  level: number | null;
  volume_ratio: number | null;
  message: string;
  payload: Record<string, unknown> | null;
}
