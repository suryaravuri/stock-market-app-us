import type { MarketCode } from "../types/market";

/**
 * Which market this dashboard serves. The US and India apps are separate
 * repositories; set VITE_APP_MARKET=IN in the India app's .env.
 */
const raw = String(import.meta.env.VITE_APP_MARKET ?? "US").toUpperCase();

export const APP_MARKET: MarketCode = raw === "IN" ? "IN" : "US";

/** Markets shown in the market tabs. */
export const APP_MARKETS: MarketCode[] = [APP_MARKET];
