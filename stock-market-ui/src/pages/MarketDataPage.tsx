import { useEffect, useState } from "react";
import RefreshIcon from "@mui/icons-material/Refresh";

import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";

import { getMonitorStatus } from "../services/monitorStatusService";

import type { MonitorStatus } from "../types/monitorStatus";

import { useWatchlist } from "../context/WatchlistContext";


function statusColor(
  status: string
): "success" | "warning" | "error" | "default" {
  switch (status) {
    case "PASS":
      return "success";

    case "DEGRADED":
      return "warning";

    case "FAIL":
      return "error";

    default:
      return "default";
  }
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "-";
  }

  return new Date(value).toLocaleString();
}

function yesNo(value: boolean) {
  return value ? "YES" : "NO";
}

function MarketDataPage() {
  const { selectedWatchlistId } = useWatchlist();
  const [status, setStatus] =
    useState<MonitorStatus | null>(null);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = async (isRefresh = false) => {
    if (selectedWatchlistId === null) {
      setStatus(null);
      setLoading(false);
      setRefreshing(false);
      return;
    }

    const watchlistId = selectedWatchlistId;

    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setError(null);

      const response = await getMonitorStatus(watchlistId);

      setStatus(response);
    } catch (err) {
      console.error(err);
      setError("Unable to load market-data status");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadStatus();
  }, [selectedWatchlistId]);

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
          <Typography>
            Loading market-data status...
          </Typography>
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

  if (!status) {
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
            Market Data
          </Typography>

          <Typography color="text.secondary">
            Freshness, completeness and indicator-readiness monitoring
          </Typography>
        </Box>

        <Stack
          direction="row"
          spacing={2}
          sx={{ alignItems: "center" }}
        >
          <Chip
            label={`DATA: ${status.data_status}`}
            color={statusColor(
              status.data_status
            )}
          />

          <Button
            variant="contained"
            startIcon={<RefreshIcon />}
            disabled={refreshing}
            onClick={() => loadStatus(true)}
          >
            {refreshing
              ? "Refreshing..."
              : "Refresh"}
          </Button>
        </Stack>
      </Stack>

      {status.data_status !== "PASS" && (
        <Alert
          severity={
            status.data_status === "FAIL"
              ? "error"
              : "warning"
          }
          sx={{ mb: 3 }}
        >
          <Typography sx={{ fontWeight: 700 }}>
            Market data is not fully ready
          </Typography>

          <Typography variant="body2">
            {status.blocked_stocks} /{" "}
            {status.symbols_checked} symbols are
            currently blocked from signal analysis.
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
              Data Status
            </Typography>

            <Box sx={{ mt: 1 }}>
              <Chip
                label={status.data_status}
                color={statusColor(
                  status.data_status
                )}
              />
            </Box>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ flex: 1 }}>
          <CardContent>
            <Typography color="text.secondary">
              Symbols Ready
            </Typography>

            <Typography
              variant="h4"
              sx={{ fontWeight: 700 }}
            >
              {status.eligible_for_signal_analysis} /{" "}
              {status.symbols_checked}
            </Typography>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ flex: 1 }}>
          <CardContent>
            <Typography color="text.secondary">
              Passed
            </Typography>

            <Typography
              variant="h4"
              sx={{ fontWeight: 700 }}
            >
              {status.symbols_passed}
            </Typography>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ flex: 1 }}>
          <CardContent>
            <Typography color="text.secondary">
              Failed
            </Typography>

            <Typography
              variant="h4"
              sx={{ fontWeight: 700 }}
            >
              {status.symbols_failed}
            </Typography>
          </CardContent>
        </Card>
      </Stack>

      <Paper
        variant="outlined"
        sx={{
          mb: 3,
          overflowX: "auto",
        }}
      >
        <Box sx={{ p: 2 }}>
          <Typography
            variant="h6"
            sx={{ fontWeight: 700 }}
          >
            Symbol Data Health
          </Typography>
        </Box>

        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Symbol</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Eligible</TableCell>
              <TableCell align="right">
                Lag Bars
              </TableCell>
              <TableCell>
                Latest Candle
              </TableCell>
              <TableCell>
                Expected Candle
              </TableCell>
              <TableCell>
                Indicators
              </TableCell>
              <TableCell align="right">
                Gaps
              </TableCell>
              <TableCell align="right">
                Duplicates
              </TableCell>
              <TableCell>Reason</TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {status.results.map((row) => (
              <TableRow key={row.stock_id}>
                <TableCell
                  sx={{ fontWeight: 700 }}
                >
                  {row.symbol}
                </TableCell>

                <TableCell>
                  <Chip
                    size="small"
                    label={row.status}
                    color={statusColor(
                      row.status
                    )}
                  />
                </TableCell>

                <TableCell>
                  {yesNo(
                    row.eligible_for_signal_analysis
                  )}
                </TableCell>

                <TableCell align="right">
                  {row.freshness_lag_bars}
                </TableCell>

                <TableCell>
                  {formatDateTime(
                    row.latest_regular_session_candle
                  )}
                </TableCell>

                <TableCell>
                  {formatDateTime(
                    row.expected_latest_completed_candle
                  )}
                </TableCell>

                <TableCell>
                  {row.indicator_ready
                    ? "READY"
                    : "NOT READY"}
                </TableCell>

                <TableCell align="right">
                  {row.intraday_gap_count}
                </TableCell>

                <TableCell align="right">
                  {row.duplicate_timestamp_count}
                </TableCell>

                <TableCell>
                  {row.reasons.length > 0
                    ? row.reasons.join(", ")
                    : "-"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>

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
            Candle Freshness
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="Expected Latest"
              value={formatDateTime(
                status.expected_latest_completed_candle
              )}
            />

            <Metric
              label="Latest Available"
              value={formatDateTime(
                status.latest_available_candle
              )}
            />

            <Metric
              label="Timeframe"
              value={status.timeframe}
            />

            <Metric
              label="Session Timezone"
              value={status.session_timezone}
            />

            <Metric
              label="Evaluated At"
              value={formatDateTime(
                status.evaluated_at
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
            Safety Status
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="Execution Mode"
              value={status.execution_mode}
            />

            <Metric
              label="Broker Order Submitted"
              value={yesNo(
                status.broker_order_submitted
              )}
            />

            <Metric
              label="Database Mutated"
              value={yesNo(
                status.database_mutated
              )}
            />

            <Metric
              label="Production Positions Mutated"
              value={yesNo(
                status.production_position_tables_mutated
              )}
            />
          </Stack>

          <Alert severity="info" sx={{ mt: 3 }}>
            Read-only monitoring. This page does not
            advance signal state or submit broker orders.
          </Alert>
        </Paper>
      </Stack>
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

export default MarketDataPage;