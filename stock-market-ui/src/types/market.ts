export type MarketCode = "US" | "IN";

export interface MarketStatus {
  market: MarketCode;
  timezone: string;
  is_open: boolean;
  is_session_day: boolean;
  local_time: string;
  opens_at: string | null;
  closes_at: string | null;
  next_open: string | null;
  early_close: boolean;
}

export type MarketsStatus = Record<MarketCode, MarketStatus>;

export const MARKETS: Record<
  MarketCode,
  { label: string; flag: string; timezone: string; tzLabel: string; currency: string }
> = {
  US: {
    label: "US",
    flag: "\u{1F1FA}\u{1F1F8}",
    timezone: "America/New_York",
    tzLabel: "ET",
    currency: "USD",
  },
  IN: {
    label: "India",
    flag: "\u{1F1EE}\u{1F1F3}",
    timezone: "Asia/Kolkata",
    tzLabel: "IST",
    currency: "INR",
  },
};
