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
  getPositionLifecycle,
  getPositionSize,
} from "../services/riskService";

import {
  getWatchlistStocks,

} from "../services/watchlistService";

import type {
  PositionLifecycle,
  PositionSizeResponse,
} from "../types/risk";

import { useWatchlist } from "../context/WatchlistContext";


function formatMoney(
  value: number | null | undefined
): string {
  if (value === null || value === undefined) {
    return "-";
  }

  return `$${value.toFixed(2)}`;
}

function yesNo(value: boolean) {
  return value ? "YES" : "NO";
}

function statusColor(
  status: string
): "success" | "warning" | "error" | "info" | "default" {
  switch (status) {
    case "OPEN":
    case "ENTRY_CONFIRMED":
      return "success";

    case "NOT_OPEN":
    case "WAITING":
      return "warning";

    case "CLOSED":
    case "BLOCKED":
    case "EXPIRED":
      return "error";

    default:
      return "default";
  }
}

function RiskPositionsPage() {
  const { selectedWatchlistId } = useWatchlist();
  const [symbol, setSymbol] = useState("");
  const [symbols, setSymbols] = useState<string[]>([]);

  const [positionSize, setPositionSize] =
    useState<PositionSizeResponse | null>(null);

  const [lifecycle, setLifecycle] =
    useState<PositionLifecycle | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadRisk = async (selectedSymbol: string) => {
    try {
      setLoading(true);
      setError(null);

      const [sizeResponse, lifecycleResponse] =
        await Promise.all([
          getPositionSize(selectedSymbol),
          getPositionLifecycle(selectedSymbol),
        ]);

      setPositionSize(sizeResponse);
      setLifecycle(lifecycleResponse);
    } catch (err) {
      console.error(err);
      setError(
        `Unable to load risk and position data for ${selectedSymbol}`
      );
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
      void loadRisk(symbol);
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
          <Typography>Loading risk data...</Typography>
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

  if (!positionSize || !lifecycle) {
    return null;
  }

  const position = positionSize.position;
  const setup = positionSize.setup;
  const optionAnalysis = positionSize.option_analysis;

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
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            Risk & Positions
          </Typography>

          <Typography color="text.secondary">
            Position sizing, risk limits and analytical position monitoring
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

      {!position.allowed && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          <Typography sx={{ fontWeight: 700 }}>
            Position Opening Blocked
          </Typography>

          <Typography variant="body2">
            {position.reason ?? "Setup is not actionable"}
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

            <Typography variant="h4" sx={{ fontWeight: 700 }}>
              {positionSize.symbol}
            </Typography>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ flex: 1 }}>
          <CardContent>
            <Typography color="text.secondary">
              Position State
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
              Shares
            </Typography>

            <Typography variant="h4" sx={{ fontWeight: 700 }}>
              {position.shares}
            </Typography>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ flex: 1 }}>
          <CardContent>
            <Typography color="text.secondary">
              Actual Risk
            </Typography>

            <Typography variant="h4" sx={{ fontWeight: 700 }}>
              {formatMoney(position.actual_risk_amount)}
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
            Risk Limits
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="Account Size"
              value={formatMoney(position.account_size)}
            />

            <Metric
              label="Risk Percent"
              value={`${position.risk_percent.toFixed(2)}%`}
            />

            <Metric
              label="Maximum Risk"
              value={formatMoney(
                position.max_risk_amount
              )}
            />

            <Metric
              label="Max Position Percent"
              value={`${position.max_position_percent.toFixed(
                2
              )}%`}
            />

            <Metric
              label="Max Position Value"
              value={formatMoney(
                position.max_position_value
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
            Calculated Position
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="Allowed"
              value={yesNo(position.allowed)}
            />

            <Metric
              label="Shares"
              value={String(position.shares)}
            />

            <Metric
              label="Entry"
              value={formatMoney(
                position.entry_price
              )}
            />

            <Metric
              label="Stop Loss"
              value={formatMoney(
                position.stop_loss
              )}
            />

            <Metric
              label="Risk / Share"
              value={formatMoney(
                position.risk_per_share
              )}
            />

            <Metric
              label="Position Value"
              value={formatMoney(
                position.position_value
              )}
            />

            <Metric
              label="Actual Risk"
              value={formatMoney(
                position.actual_risk_amount
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
            Setup Decision
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="Action"
              value={setup.action}
            />

            <Metric
              label="Actionable"
              value={yesNo(setup.actionable)}
            />

            <Metric
              label="Overall Score"
              value={String(setup.overall_score)}
            />

            <Metric
              label="Classification"
              value={setup.overall_classification}
            />

            <Metric
              label="RR Quality"
              value={setup.risk_reward_quality}
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
            Position Lifecycle
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="State"
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
              label="Opening Gate"
              value={yesNo(
                lifecycle.opening_gate_passed
              )}
            />

            <Metric
              label="Signal Cycle"
              value={String(
                lifecycle.signal_cycle_number
              )}
            />

            <Metric
              label="Entry"
              value={formatMoney(
                lifecycle.entry_price
              )}
            />

            <Metric
              label="Initial Stop"
              value={formatMoney(
                lifecycle.initial_stop
              )}
            />

            <Metric
              label="Active Stop"
              value={formatMoney(
                lifecycle.active_stop
              )}
            />

            <Metric
              label="Target 1"
              value={formatMoney(
                lifecycle.target_1
              )}
            />

            <Metric
              label="Target 2"
              value={formatMoney(
                lifecycle.target_2
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
            Position Monitoring
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="Current Price"
              value={formatMoney(
                lifecycle.current_price
              )}
            />

            <Metric
              label="Unrealized / Share"
              value={formatMoney(
                lifecycle.unrealized_per_share
              )}
            />

            <Metric
              label="Unrealized R"
              value={
                lifecycle.unrealized_r !== null
                  ? lifecycle.unrealized_r.toFixed(2)
                  : "-"
              }
            />

            <Metric
              label="Target 1 Hit"
              value={yesNo(
                lifecycle.target_1_hit
              )}
            />

            <Metric
              label="Target 2 Hit"
              value={yesNo(
                lifecycle.target_2_hit
              )}
            />

            <Metric
              label="Processed Candles"
              value={String(
                lifecycle.processed_candles
              )}
            />

            <Metric
              label="New Candles"
              value={String(
                lifecycle.new_candles_found
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
              value={lifecycle.execution_mode}
            />

            <Metric
              label="Persistence"
              value={lifecycle.persistence_mode}
            />

            <Metric
              label="Broker Order Submitted"
              value={yesNo(
                lifecycle.broker_order_submitted
              )}
            />

            <Metric
              label="Database Mutated"
              value={yesNo(
                lifecycle.database_mutated
              )}
            />

            <Metric
              label="Monitoring Mode"
              value={
                lifecycle.monitoring_mode ?? "-"
              }
            />

            <Metric
              label="Monitoring Status"
              value={
                lifecycle.monitoring_status ?? "-"
              }
            />
          </Stack>

          <Alert
            severity="info"
            sx={{ mt: 3 }}
          >
            Analysis only. This screen does not submit broker orders.
          </Alert>
        </Paper>
        <Paper
  variant="outlined"
  sx={{ p: 3, flex: 1 }}
>
  <Typography
    variant="h6"
    sx={{ fontWeight: 700, mb: 2 }}
  >
    Options Analysis
  </Typography>

  {optionAnalysis ? (
    <>
      <Stack spacing={1.2}>
        <Metric
          label="Status"
          value={optionAnalysis.status}
        />

        <Metric
          label="Strategy"
          value={optionAnalysis.strategy_status}
        />

        <Metric
          label="Option Type"
          value={optionAnalysis.option_type ?? "-"}
        />

        <Metric
          label="Contract"
          value={optionAnalysis.contract_symbol ?? "-"}
        />

        <Metric
          label="Analysis Allowed"
          value={yesNo(
            optionAnalysis.analysis_allowed
          )}
        />

        <Metric
          label="Execution Allowed"
          value={yesNo(
            optionAnalysis.execution_allowed
          )}
        />

        <Metric
          label="Observation"
          value={
            optionAnalysis.observation_id !== null
              ? `#${optionAnalysis.observation_id}`
              : "-"
          }
        />
      </Stack>

      <Alert
        severity={
          optionAnalysis.execution_allowed
            ? "warning"
            : "info"
        }
        sx={{ mt: 3 }}
      >
        {optionAnalysis.execution_allowed
          ? "Option execution is enabled."
          : "Analysis only. Option orders are not submitted."}
      </Alert>
    </>
  ) : (
    <Alert severity="info">
      <Typography sx={{ fontWeight: 700 }}>
        Waiting for confirmed stock entry
      </Typography>

      <Typography variant="body2" sx={{ mt: 0.5 }}>
        Options analysis starts after the stock signal reaches
        ENTRY_CONFIRMED and becomes actionable.
      </Typography>
    </Alert>
  )}
</Paper>
      </Stack>

      <Paper
        variant="outlined"
        sx={{ p: 3, mt: 3 }}
      >
        <Typography
          variant="h6"
          sx={{ fontWeight: 700, mb: 2 }}
        >
          Decision Reasons
        </Typography>

        {setup.decision_reasons.length === 0 ? (
          <Typography color="text.secondary">
            No decision reasons reported.
          </Typography>
        ) : (
          <Stack spacing={1}>
            {setup.decision_reasons.map(
              (reason, index) => (
                <Typography
                  variant="body2"
                  key={`${reason}-${index}`}
                >
                  {index + 1}. {reason}
                </Typography>
              )
            )}
          </Stack>
        )}
      </Paper>
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

export default RiskPositionsPage;