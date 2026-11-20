export interface IndicatorSnapshot {
  ema_9: number | null;
  ema_20: number | null;
  ema_50: number | null;
  rsi_14: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_histogram: number | null;
  atr_14: number | null;
  session_vwap: number | null;
}

export interface PriceLevelDetail {
  price: number;
  level_type: "SUPPORT" | "RESISTANCE";
  strength: number;
  touches: number;
  distance_from_price: number;
}

export interface SupportSummary {
  nearest: number | null;
  next: number | null;
  strongest: number | null;
  nearest_level: PriceLevelDetail | null;
}

export interface ResistanceSummary {
  nearest: number | null;
  next: number | null;
  strongest: number | null;
  nearest_level: PriceLevelDetail | null;
}

export interface AnalysisSummary {
  symbol: string;
  timeframe: string;
  timestamp: string;
  current_price: number;
  indicators: IndicatorSnapshot;
  support: SupportSummary;
  resistance: ResistanceSummary;
  candle_count: number;
}

export interface TimeframeAnalysis {
  score: number;
  classification: string;
  current_price: number;
  nearest_support: number | null;
  nearest_resistance: number | null;
}

export interface MultiTimeframeAnalysis {
  symbol: string;
  timeframes: Record<string, TimeframeAnalysis>;
  overall_score: number;
  overall_classification: string;
}