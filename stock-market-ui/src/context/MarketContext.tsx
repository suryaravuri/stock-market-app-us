import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { getMarketsStatus } from "../services/marketStatusService";
import type { MarketCode, MarketsStatus } from "../types/market";

const STORAGE_KEY = "selectedMarket";
const STATUS_REFRESH_MS = 60_000;

interface MarketContextValue {
  market: MarketCode;
  setMarket: (market: MarketCode) => void;
  statuses: MarketsStatus | null;
}

const MarketContext = createContext<MarketContextValue | undefined>(undefined);

function initialMarket(): MarketCode {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "US" || saved === "IN") {
      return saved;
    }
  } catch {
    // Storage unavailable: fall back to US.
  }
  return "US";
}

export function MarketProvider({ children }: { children: ReactNode }) {
  const [market, setMarketState] = useState<MarketCode>(initialMarket);
  const [statuses, setStatuses] = useState<MarketsStatus | null>(null);

  const setMarket = useCallback((value: MarketCode) => {
    setMarketState(value);
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch {
      // Selection still works for this session.
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const data = await getMarketsStatus();
        if (!cancelled) {
          setStatuses(data);
        }
      } catch (err) {
        console.error("Unable to load market status", err);
      }
    };

    load();
    const timer = window.setInterval(load, STATUS_REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <MarketContext.Provider value={{ market, setMarket, statuses }}>
      {children}
    </MarketContext.Provider>
  );
}

export function useMarket(): MarketContextValue {
  const context = useContext(MarketContext);
  if (!context) {
    throw new Error("useMarket must be used inside MarketProvider");
  }
  return context;
}
