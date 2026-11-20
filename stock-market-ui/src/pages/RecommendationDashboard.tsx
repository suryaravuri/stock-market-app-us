import { useEffect, useMemo, useRef, useState } from "react";
import RefreshIcon from "@mui/icons-material/Refresh";

import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Stack,
  Typography,
} from "@mui/material";

import SummaryCards from "../components/SummaryCards";
import RecommendationTable from "../components/RecommendationTable";
import MarketTabs from "../components/MarketTabs";

import { getWatchlistRecommendations } from "../services/recommendationService";
import { getMonitorStatus } from "../services/monitorStatusService";

import type {
  RecommendationStock,
  WatchlistScanResponse,
} from "../types/recommendation";
import type { MonitorStatus } from "../types/monitorStatus";
import { MARKETS, type MarketCode } from "../types/market";

import { useWatchlist } from "../context/WatchlistContext";
import { useMarket } from "../context/MarketContext";

// Show candle times in the market's own timezone, with the weekday,
// so "3:45 PM" can't be mistaken for today when it was Friday.
function formatCandleTime(iso: string, market: MarketCode): string {
  const info = MARKETS[market];
  return (
    new Date(iso).toLocaleString([], {
      timeZone: info.timezone,
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }) + ` ${info.tzLabel}`
  );
}

function RecommendationDashboard() {
  const [data, setData] = useState<WatchlistScanResponse | null>(null);
  const [monitorStatus, setMonitorStatus] = useState<MonitorStatus | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const { selectedWatchlistId } = useWatchlist();
  const { market, statuses } = useMarket();
  const marketInfo = MARKETS[market];
  const marketStatus = statuses?.[market];

  // Ignore responses from a tab the user has already switched away from.
  const requestId = useRef(0);

  // .NS / .BO = India, everything else = US (same rule as the backend)
  const isIndianSymbol = (symbol: string) => /\.(NS|BO)$/i.test(symbol);

  const loadRecommendations = async (isRefresh = false) => {
    const thisRequest = ++requestId.current;

    try {
      if (selectedWatchlistId === null) {
        setData(null);
        setMonitorStatus(null);
        setError(null);
        return;
      }

      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setError(null);

      const [recommendationResponse, monitorResponse] = await Promise.all([
        getWatchlistRecommendations(selectedWatchlistId, market),
        getMonitorStatus(selectedWatchlistId, market),
      ]);

      if (thisRequest !== requestId.current) {
        return;
      }

      const stocks = recommendationResponse.stocks.filter(
          (s) => isIndianSymbol(s.symbol) === (market === "IN")
        );
        setData(
          stocks.length > 0
            ? {
                ...recommendationResponse,
                stocks,
                total_stocks: stocks.length,
                actionable_count: stocks.filter((s) => s.actionable).length,
              }
            : null
        );
      setMonitorStatus(monitorResponse);
      setLastUpdated(new Date());
    } catch (err: any) {
      if (thisRequest !== requestId.current) {
        return;
      }
      console.error(err);

      const detail = err?.response?.data?.detail;

      if (
        err?.response?.status === 404 &&
        typeof detail === "string" &&
        detail.includes("no active analysis-enabled stocks")
      ) {
        // Valid state: this watchlist has no stocks in this market.
        setData(null);
        setMonitorStatus(null);
        setError(null);
      } else {
        setError("Unable to load recommendation data");
      }
    } finally {
      if (thisRequest === requestId.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  };

  useEffect(() => {
    if (selectedWatchlistId === null) {
      return;
    }

    loadRecommendations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedWatchlistId, market]);

  const summary = useMemo(() => {
    const stocks: RecommendationStock[] = data?.stocks ?? [];

    return {
      strongCount: stocks.filter((s) => s.overall_classification === "STRONG").length,
      watchCount: stocks.filter((s) => s.overall_classification === "WATCH").length,
      avoidCount: stocks.filter((s) => s.overall_classification === "AVOID").length,
    };
  }, [data]);

  const marketClosed = marketStatus ? !marketStatus.is_open : false;

  const renderBody = () => {
    if (loading) {
      return (
        <Box
          sx={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            minHeight: "40vh",
          }}
        >
          <Stack spacing={2} sx={{ alignItems: "center" }}>
            <CircularProgress />
            <Typography>Loading {marketInfo.label} recommendations...</Typography>
          </Stack>
        </Box>
      );
    }

    if (error) {
      return <Alert severity="error">{error}</Alert>;
    }

    if (data === null) {
      return (
        <Alert severity="info">
          This watchlist has no analysis-enabled {marketInfo.label} stocks.
          {market === "IN"
            ? " Add NSE stocks with the .NS suffix (for example RELIANCE.NS) and enable Analysis."
            : " Add a US stock to your Watchlist and enable Analysis."}
        </Alert>
      );
    }

    return (
      <>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={2}
          sx={{
            justifyContent: "space-between",
            alignItems: { xs: "flex-start", sm: "center" },
            mb: 2,
          }}
        >
          <Box>
            <Typography color="text.secondary">
              Watchlist: {data.watchlist_name}
            </Typography>

            <Typography variant="body2" color="text.secondary">
              Last updated: {lastUpdated ? lastUpdated.toLocaleTimeString() : "-"}
            </Typography>

            {monitorStatus && (
              <>
                <Typography variant="body2" color="text.secondary">
                  Data ready: {monitorStatus.eligible_for_signal_analysis} /{" "}
                  {monitorStatus.symbols_checked}
                </Typography>

                <Typography variant="body2" color="text.secondary">
                  Latest candle:{" "}
                  {monitorStatus.latest_available_candle
                    ? formatCandleTime(monitorStatus.latest_available_candle, market)
                    : "N/A"}
                </Typography>
              </>
            )}
          </Box>

          <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
            {monitorStatus && (
              <Chip
                label={`DATA: ${monitorStatus.data_status}`}
                color={
                  monitorStatus.data_status === "PASS"
                    ? "success"
                    : monitorStatus.data_status === "DEGRADED"
                    ? "warning"
                    : "error"
                }
                size="small"
              />
            )}

            <Button
              variant="contained"
              startIcon={<RefreshIcon />}
              disabled={refreshing}
              onClick={() => loadRecommendations(true)}
            >
              {refreshing ? "Refreshing..." : "Refresh"}
            </Button>
          </Stack>
        </Stack>

        {marketClosed && monitorStatus?.data_status === "PASS" && (
          <Alert severity="info" sx={{ mb: 2 }}>
            {marketInfo.label} market is closed. Showing analysis from the last
            completed session.
          </Alert>
        )}

        {monitorStatus && monitorStatus.data_status !== "PASS" && (
          <Alert
            severity={monitorStatus.data_status === "FAIL" ? "error" : "warning"}
            sx={{ mb: 2 }}
          >
            <Typography sx={{ fontWeight: 700 }}>
              {marketInfo.label} market data is{" "}
              {monitorStatus.data_status === "FAIL" ? "stale or unavailable" : "degraded"}
            </Typography>

            <Typography variant="body2">
              Recommendations may not reflect the latest completed candle.
              {market === "IN" &&
                " Indian candles need today's Zerodha login."}
            </Typography>

            <Typography variant="body2">
              {monitorStatus.eligible_for_signal_analysis} /{" "}
              {monitorStatus.symbols_checked} symbols currently eligible for analysis.
            </Typography>
          </Alert>
        )}

        <SummaryCards
          totalStocks={data.total_stocks}
          actionableCount={data.actionable_count}
          strongCount={summary.strongCount}
          watchCount={summary.watchCount}
          avoidCount={summary.avoidCount}
        />

        <RecommendationTable stocks={data.stocks} />
      </>
    );
  };

  return (
    <Box sx={{ py: 4, px: 3 }}>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
        Stock Recommendation Monitor
      </Typography>

      <MarketTabs />

      {renderBody()}
    </Box>
  );
}

export default RecommendationDashboard;
