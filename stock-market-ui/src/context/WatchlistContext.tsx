import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import apiClient from "../api/client";
import { useAuth } from "./AuthContext";

interface Watchlist {
  watchlist_id: number;
  name: string;
  description?: string | null;
  active: boolean;
}

interface WatchlistContextValue {
  watchlists: Watchlist[];
  selectedWatchlistId: number | null;

  // Allow callers to select a watchlist or clear the selection.
  setSelectedWatchlistId: (id: number | null) => void;

  loading: boolean;
}

const WatchlistContext = createContext<WatchlistContextValue | undefined>(
  undefined
);

export function WatchlistProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated, user } = useAuth();

  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);

  const [selectedWatchlistId, setSelectedWatchlistId] =
    useState<number | null>(null);

  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Logged-out state.
    if (!isAuthenticated || !user) {
      setWatchlists([]);
      setSelectedWatchlistId(null);
      return;
    }

    let cancelled = false;

    async function loadWatchlists() {
      setLoading(true);

      try {
        // 1. Load watchlists belonging to the authenticated user.
        const response = await apiClient.get<Watchlist[]>("/watchlists");

        if (cancelled) {
          return;
        }

        let data = response.data ?? [];

        /*
         * 2. First-time user:
         * create a personal default watchlist when none exists.
         */
        if (data.length === 0) {
          const createResponse = await apiClient.post<Watchlist>(
            "/watchlists",
            {
              name: "My Stocks",
              description: "Default personal watchlist",
              active: true,
            }
          );

          if (cancelled) {
            return;
          }

          data = [createResponse.data];
        }

        // 3. Store the user's watchlists.
        setWatchlists(data);

        // 4. Preserve the existing selection when it is still valid.
        // Otherwise select the first available watchlist.
        setSelectedWatchlistId((currentId) => {
          if (
            currentId !== null &&
            data.some((watchlist) => watchlist.watchlist_id === currentId)
          ) {
            return currentId;
          }

          return data[0]?.watchlist_id ?? null;
        });
      } catch (error) {
        if (!cancelled) {
          console.error("Unable to load or create watchlist", error);

          setWatchlists([]);
          setSelectedWatchlistId(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadWatchlists();

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, user?.id]);

  return (
    <WatchlistContext.Provider
      value={{
        watchlists,
        selectedWatchlistId,
        setSelectedWatchlistId,
        loading,
      }}
    >
      {children}
    </WatchlistContext.Provider>
  );
}

export function useWatchlist() {
  const context = useContext(WatchlistContext);

  if (!context) {
    throw new Error(
      "useWatchlist must be used inside WatchlistProvider"
    );
  }

  return context;
}