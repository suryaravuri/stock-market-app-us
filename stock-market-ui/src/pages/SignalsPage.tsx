import { useEffect, useState } from "react";

import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Typography,
} from "@mui/material";

import {
  getBreakoutConfirmation,
  getSignalLifecycle,
  
} from "../services/signalService";

import type {
  BreakoutConfirmation,
  SignalLifecycle,
} from "../types/signals";

import {
  getWatchlistStocks,

} from "../services/watchlistService";

import { useWatchlist } from "../context/WatchlistContext";


function formatNumber(
  value: number | null | undefined,
  digits = 2
): string {
  if (value === null || value === undefined) {
    return "-";
  }

  return value.toFixed(digits);
}

function yesNo(value: boolean) {
  return value ? "YES" : "NO";
}

function statusColor(
  status: string
): "success" | "warning" | "error" | "info" | "default" {
  switch (status) {
    case "ENTRY_CONFIRMED":
    case "CONFIRMED":
      return "success";

    case "WATCHING":
    case "BREAKOUT_PENDING":
    case "WAITING_FOR_PRICE":
      return "warning";

    case "EXPIRED":
    case "INVALIDATED":
    case "AVOID":
      return "error";

    default:
      return "default";
  }
}

function SignalsPage() {
  const { selectedWatchlistId } = useWatchlist();
  const [symbol, setSymbol] = useState("");
  const [symbols, setSymbols] = useState<string[]>([]);

  const [breakout, setBreakout] =
    useState<BreakoutConfirmation | null>(null);

  const [lifecycle, setLifecycle] =
    useState<SignalLifecycle | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSignals = async (selectedSymbol: string) => {
    try {
      setLoading(true);
      setError(null);

      const [breakoutResponse, lifecycleResponse] =
        await Promise.all([
          getBreakoutConfirmation(selectedSymbol),
          getSignalLifecycle(selectedSymbol),
        ]);

      setBreakout(breakoutResponse);
      setLifecycle(lifecycleResponse);
    } catch (err) {
      console.error(err);
      setError(`Unable to load signals for ${selectedSymbol}`);
    } finally {
      setLoading(false);
    }
  };



useEffect(() => {
  const loadWatchlistSymbols = async () => {
    if (selectedWatchlistId === null) {
      setSymbols([]);
      setSymbol("");
      setLoading(false);
      return;
    }

    const watchlistId = selectedWatchlistId;

    try {
      const stocks = await getWatchlistStocks(watchlistId);

      const enabledSymbols = stocks
        .filter((stock) => stock.analysis_enabled)
        .map((stock) => stock.stock.symbol);

      setSymbols(enabledSymbols);

      if (
        enabledSymbols.length > 0 &&
        !enabledSymbols.includes(symbol)
      ) {
        setSymbol(enabledSymbols[0]);
      }
    } catch (error) {
      console.error(
        "Failed to load watchlist symbols:",
        error
      );
    }
    };

  void loadWatchlistSymbols();
}, [selectedWatchlistId]);

  useEffect(() => {
    if (symbol) {
      void loadSignals(symbol);
    }
  }, [symbol]);

  if (loading) {
    return (
      <Box
        sx={{
          minHeight: "60vh",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <Stack spacing={2} sx={{ alignItems: "center" }}>
          <CircularProgress />
          <Typography>Loading signal analysis...</Typography>
        </Stack>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  if (!breakout || !lifecycle) {
    return null;
  }

  return (
    <Box sx={{ py: 4, px: 3 }}>
      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={2}
        sx={{
          justifyContent: "space-between",
          alignItems: {
            xs: "flex-start",
            md: "center",
          },
          mb: 3,
        }}
      >
        <Box>
          <Typography
            variant="h4"
            sx={{ fontWeight: 700 }}
          >
            Signals
          </Typography>

          <Typography color="text.secondary">
            Signal lifecycle, breakout confirmation and entry-gate readiness
          </Typography>
        </Box>

        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Symbol</InputLabel>

          <Select
            value={symbol}
            label="Symbol"
            onChange={(event) =>
              setSymbol(event.target.value)
            }
          >
            {symbols.map((stockSymbol) => (
              <MenuItem
                key={stockSymbol}
                value={stockSymbol}
              >
                {stockSymbol}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Stack>

      {lifecycle.expired && (
        <Alert severity="error" sx={{ mb: 3 }}>
          <Typography sx={{ fontWeight: 700 }}>
            Signal Expired
          </Typography>

          <Typography variant="body2">
            {lifecycle.expiration_reason ??
              lifecycle.reason ??
              "Signal is no longer valid."}
          </Typography>
        </Alert>
      )}

      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={2}
        sx={{ mb: 3 }}
      >
        <Card variant="outlined" sx={{ flex: 1 }}>
          <CardContent>
            <Typography color="text.secondary">
              Symbol
            </Typography>

            <Typography
              variant="h4"
              sx={{ fontWeight: 700 }}
            >
              {symbol}
            </Typography>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ flex: 1 }}>
          <CardContent>
            <Typography color="text.secondary">
              Signal State
            </Typography>

            <Box sx={{ mt: 1 }}>
              <Chip
                label={lifecycle.state}
                color={statusColor(lifecycle.state)}
              />
            </Box>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ flex: 1 }}>
          <CardContent>
            <Typography color="text.secondary">
              Breakout Status
            </Typography>

            <Box sx={{ mt: 1 }}>
              <Chip
                label={breakout.status}
                color={statusColor(breakout.status)}
              />
            </Box>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ flex: 1 }}>
          <CardContent>
            <Typography color="text.secondary">
              Cycle
            </Typography>

            <Typography
              variant="h4"
              sx={{ fontWeight: 700 }}
            >
              {lifecycle.cycle_number}
            </Typography>
          </CardContent>
        </Card>
      </Stack>

      <Stack
        direction={{ xs: "column", lg: "row" }}
        spacing={3}
        sx={{ mb: 3 }}
      >
        <Paper
          variant="outlined"
          sx={{ p: 3, flex: 1 }}
        >
          <Typography
            variant="h6"
            sx={{ fontWeight: 700, mb: 2 }}
          >
            Entry Gate
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="Breakout Level"
              value={`$${formatNumber(
                breakout.breakout_level
              )}`}
            />

            <Metric
              label="Confirmation Price"
              value={`$${formatNumber(
                breakout.confirmation_price
              )}`}
            />

            <Metric
              label="Buffer"
              value={`$${formatNumber(
                breakout.buffer_price,
                4
              )}`}
            />

            <Metric
              label="Price Confirmed"
              value={yesNo(
                breakout.price_confirmed
              )}
            />

            <Metric
              label="Volume Confirmed"
              value={yesNo(
                breakout.volume_confirmed
              )}
            />

            <Metric
              label="Candle Quality"
              value={yesNo(
                breakout.candle_quality_confirmed
              )}
            />

            <Metric
              label="Breakout Detected"
              value={yesNo(
                breakout.breakout_detected
              )}
            />
          </Stack>
        </Paper>

        <Paper
          variant="outlined"
          sx={{ p: 3, flex: 1 }}
        >
          <Typography
            variant="h6"
            sx={{ fontWeight: 700, mb: 2 }}
          >
            Volume & Candle Quality
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="Volume Ratio"
              value={`${formatNumber(
                breakout.volume_ratio
              )}x`}
            />

            <Metric
              label="Minimum Volume Ratio"
              value={`${formatNumber(
                breakout.min_volume_ratio
              )}x`}
            />

            <Metric
              label="Latest Volume"
              value={
                breakout.latest_volume?.toLocaleString() ??
                "-"
              }
            />

            <Metric
              label="Average Prior Volume"
              value={
                breakout.average_prior_volume?.toLocaleString(
                  undefined,
                  {
                    maximumFractionDigits: 0,
                  }
                ) ?? "-"
              }
            />

            <Metric
              label="Body Ratio"
              value={
                breakout.body_ratio !== null
                  ? `${(
                      breakout.body_ratio * 100
                    ).toFixed(1)}%`
                  : "-"
              }
            />

            <Metric
              label="Close Location"
              value={
                breakout.close_location !== null
                  ? `${(
                      breakout.close_location * 100
                    ).toFixed(1)}%`
                  : "-"
              }
            />

            <Metric
              label="Upper Wick"
              value={
                breakout.upper_wick_ratio !== null
                  ? `${(
                      breakout.upper_wick_ratio * 100
                    ).toFixed(1)}%`
                  : "-"
              }
            />
          </Stack>
        </Paper>

        <Paper
          variant="outlined"
          sx={{ p: 3, flex: 1 }}
        >
          <Typography
            variant="h6"
            sx={{ fontWeight: 700, mb: 2 }}
          >
            Follow Through
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="Required"
              value={yesNo(
                breakout.follow_through_required
              )}
            />

            <Metric
              label="Confirmed"
              value={yesNo(
                breakout.follow_through_confirmed
              )}
            />

            <Metric
              label="Retest Confirmed"
              value={yesNo(
                breakout.retest_confirmed
              )}
            />

            <Metric
              label="Status"
              value={breakout.follow_through_status}
            />

            <Metric
              label="Pending Candles"
              value={`${lifecycle.pending_candles} / ${lifecycle.max_pending_candles}`}
            />
          </Stack>
        </Paper>
      </Stack>

      <Stack
        direction={{ xs: "column", lg: "row" }}
        spacing={3}
      >
        <Paper
          variant="outlined"
          sx={{ p: 3, flex: 1 }}
        >
          <Typography
            variant="h6"
            sx={{ fontWeight: 700, mb: 2 }}
          >
            Signal Lifecycle
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="Current State"
              value={lifecycle.state}
            />

            <Metric
              label="Previous State"
              value={lifecycle.previous_state ?? "-"}
            />

            <Metric
              label="Last Event"
              value={lifecycle.last_event ?? "-"}
            />

            <Metric
              label="Observed Breakout"
              value={
                lifecycle.observed_breakout_status ??
                "-"
              }
            />

            <Metric
              label="Staleness"
              value={
                lifecycle.staleness_status ?? "-"
              }
            />

            <Metric
              label="Signal Age"
              value={
                lifecycle.signal_age_minutes !== null
                  ? `${formatNumber(
                      lifecycle.signal_age_minutes,
                      1
                    )} min`
                  : "-"
              }
            />

            <Metric
              label="Freshness Limit"
              value={
                lifecycle.max_signal_age_minutes !==
                null
                  ? `${lifecycle.max_signal_age_minutes} min`
                  : "-"
              }
            />

            <Metric
              label="Rearmed"
              value={yesNo(lifecycle.rearmed)}
            />

            <Metric
              label="Rearm Status"
              value={lifecycle.rearm_status ?? "-"}
            />
          </Stack>
        </Paper>

        <Paper
          variant="outlined"
          sx={{ p: 3, flex: 1 }}
        >
          <Typography
            variant="h6"
            sx={{ fontWeight: 700, mb: 2 }}
          >
            Decision Reasons
          </Typography>

          {breakout.reasons.length === 0 ? (
            <Typography color="text.secondary">
              No breakout reasons reported.
            </Typography>
          ) : (
            <Stack spacing={1.2}>
              {breakout.reasons.map(
                (reason, index) => (
                  <Typography
                    key={`${reason}-${index}`}
                    variant="body2"
                  >
                    {index + 1}. {reason}
                  </Typography>
                )
              )}
            </Stack>
          )}

          {breakout.failed_quality_checks.length >
            0 && (
            <Box sx={{ mt: 3 }}>
              <Typography
                sx={{ fontWeight: 700, mb: 1 }}
              >
                Failed Quality Checks
              </Typography>

              <Stack
                direction="row"
                spacing={1}
                useFlexGap
                sx={{ flexWrap: "wrap" }}
              >
                {breakout.failed_quality_checks.map(
                  (check) => (
                    <Chip
                      key={check}
                      label={check}
                      color="error"
                      variant="outlined"
                      size="small"
                    />
                  )
                )}
              </Stack>
            </Box>
          )}
        </Paper>
      </Stack>

      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ display: "block", mt: 2 }}
      >
        Signal candle:{" "}
        {lifecycle.signal_candle_time
          ? new Date(
              lifecycle.signal_candle_time
            ).toLocaleString()
          : "-"}{" "}
        · Breakout analysis:{" "}
        {new Date(
          breakout.timestamp
        ).toLocaleString()}
      </Typography>
    </Box>
  );
}

interface MetricProps {
  label: string;
  value: string;
}

function Metric({ label, value }: MetricProps) {
  return (
    <Stack
      direction="row"
      sx={{
        justifyContent: "space-between",
        gap: 2,
      }}
    >
      <Typography color="text.secondary">
        {label}
      </Typography>

      <Typography
        sx={{
          fontWeight: 600,
          textAlign: "right",
        }}
      >
        {value}
      </Typography>
    </Stack>
  );
}

export default SignalsPage;