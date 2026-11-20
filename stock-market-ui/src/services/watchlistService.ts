import apiClient from "../api/client";

import type {
  AddWatchlistStockRequest,
  CreateStockRequest,
  Stock,
  UpdateWatchlistStockRequest,
  Watchlist,
  WatchlistStock,
} from "../types/watchlist";

import axios from "axios";


export async function updateWatchlistStock(
  watchlistId: number,
  stockId: number,
  request: UpdateWatchlistStockRequest
): Promise<WatchlistStock> {
  const payload: UpdateWatchlistStockRequest = {
    ...request,

    // Safety boundary.
    trading_enabled: false,
  };

  const response = await apiClient.put<WatchlistStock>(
    `/watchlists/${watchlistId}/stocks/${stockId}`,
    payload
  );

  return response.data;
}

export async function syncWatchlistMarketData(
  watchlistId: number
): Promise<unknown> {
  const response = await apiClient.post(
    `/watchlists/${watchlistId}/market-data/sync`
  );

  return response.data;
}

export async function getStocks(): Promise<Stock[]> {
  const response = await apiClient.get<Stock[]>("/stocks");
  return response.data;
}


export async function getStock(symbol: string): Promise<Stock> {
  const response = await apiClient.get<Stock>(
    `/stocks/${encodeURIComponent(symbol.toUpperCase())}`
  );

  return response.data;
}


export async function createStock(
  request: CreateStockRequest
): Promise<Stock> {
  const payload: CreateStockRequest = {
    ...request,
    symbol: request.symbol.trim().toUpperCase(),

    // Analysis-only safety.
    tradable: false,
  };

  const response = await apiClient.post<Stock>(
    "/stocks",
    payload
  );

  return response.data;
}


export async function getWatchlists(): Promise<Watchlist[]> {
  const response = await apiClient.get<Watchlist[]>("/watchlists");
  return response.data;
}


export async function getWatchlistStocks(
  watchlistId: number
): Promise<WatchlistStock[]> {
  const response = await apiClient.get<WatchlistStock[]>(
    `/watchlists/${watchlistId}/stocks`
  );

  return response.data;
}


export async function addStockToWatchlist(
  watchlistId: number,
  request: AddWatchlistStockRequest
): Promise<WatchlistStock> {
  const payload: AddWatchlistStockRequest = {
    ...request,

    // Never enable broker trading from this UI.
    trading_enabled: false,
  };

  const response = await apiClient.post<WatchlistStock>(
    `/watchlists/${watchlistId}/stocks`,
    payload
  );

  return response.data;
}


export async function removeStockFromWatchlist(
  watchlistId: number,
  stockId: number
): Promise<void> {
  await apiClient.delete(
    `/watchlists/${watchlistId}/stocks/${stockId}`
  );
}

export async function getStockBySymbol(
  symbol: string
): Promise<Stock | null> {
  const normalizedSymbol = symbol.trim().toUpperCase();

  try {
    const response = await apiClient.get<Stock>(
      `/stocks/${encodeURIComponent(normalizedSymbol)}`
    );

    return response.data;
  } catch (error) {
    if (
      axios.isAxiosError(error) &&
      error.response?.status === 404
    ) {
      return null;
    }

    throw error;
  }
}