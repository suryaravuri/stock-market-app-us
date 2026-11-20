export type HeatmapPeriod = "1D" | "1W" | "1M" | "3M" | "6M";
export type PnlGroup = "day" | "week" | "month";
export type PnlRange = "1M" | "3M" | "6M" | "1A";

export interface HeatmapStock {
  symbol: string;
  company_name: string | null;
  sector: string;
  price: number;
  reference_price: number | null;
  change_pct: number | null;
}

export interface HeatmapSector {
  sector: string;
  avg_change_pct: number | null;
  advancers: number;
  decliners: number;
  stocks: HeatmapStock[];
}

export interface SectorHeatmap {
  period: HeatmapPeriod;
  as_of: string | null;
  stocks: number;
  sectors: HeatmapSector[];
}

export interface PnlBucket {
  key: string;
  label: string;
  account_pnl: number;
  account_pnl_pct: number | null;
  realized_pnl: number;
  trades: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  end_equity: number | null;
}

export interface ClosedTrade {
  symbol: string;
  qty: number;
  entry_price: number;
  exit_price: number;
  entry_time: string;
  exit_time: string;
  pnl: number;
  pnl_pct: number | null;
}

export interface OpenPosition {
  symbol: string;
  qty: number;
  avg_entry_price: number;
  current_price: number | null;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

export interface PnlReport {
  group: PnlGroup;
  range: PnlRange;
  totals: {
    account_pnl: number;
    realized_pnl: number;
    unrealized_pnl: number;
    trades: number;
    wins: number;
    losses: number;
    win_rate: number | null;
    end_equity: number | null;
  };
  buckets: PnlBucket[];
  trades: ClosedTrade[];
  open_positions: OpenPosition[];
  orders_capped: boolean;
}
