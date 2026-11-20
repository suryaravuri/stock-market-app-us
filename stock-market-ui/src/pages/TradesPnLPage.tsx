import { useCallback, useEffect, useState } from "react";
import RefreshIcon from "@mui/icons-material/Refresh";
import SyncIcon from "@mui/icons-material/Sync";

import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";

import {
  getTradeStatistics,
  syncZerodhaTrades,
} from "../services/tradeStatisticsService";

import type {
  TradeMode,
  TradeStatistics,
} from "../types/tradeStatistics";

function rupees(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }

  return `\u20B9${value.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function signedRupees(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }

  return `${value > 0 ? "+" : ""}${rupees(value)}`;
}

function pnlColor(value: number | null | undefined): string {
  if (!value) {
    return "text.primary";
  }

  return value > 0 ? "success.main" : "error.main";
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  return new Date(value).toLocaleString();
}

function orderStatusColor(
  status: string
): "success" | "warning" | "error" | "info" | "default" {
  switch (status) {
    case "SUBMITTED":
      return "success";
    case "DRY_RUN":
      return "info";
    case "REJECTED":
    case "FAILED":
      return "error";
    case "UNKNOWN":
    case "CANCEL_REQUESTED":
      return "warning";
    default:
      return "default";
  }
}

interface StatCardProps {
  label: string;
  value: string;
  color?: string;
  hint?: string;
}

function StatCard({ label, value, color, hint }: StatCardProps) {
  return (
    <Card variant="outlined" sx={{ height: "100%" }}>
      <CardContent>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {label}
        </Typography>

        <Typography variant="h5" sx={{ fontWeight: 700, color }}>
          {value}
        </Typography>

        {hint && (
          <Typography variant="caption" color="text.secondary">
            {hint}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

function DailyPnlBars({
  days,
}: {
  days: { date: string; pnl: number }[];
}) {
  if (days.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No closed trades yet.
      </Typography>
    );
  }

  const recent = days.slice(-30);
  const maxAbs = Math.max(...recent.map((d) => Math.abs(d.pnl)), 1);
  const half = 70;

  return (
    <Box sx={{ overflowX: "auto" }}>
      <Stack direction="row" spacing={0.75} sx={{ alignItems: "flex-end", minWidth: "fit-content" }}>
        {recent.map((day) => {
          const height = Math.max(2, (Math.abs(day.pnl) / maxAbs) * half);
          const positive = day.pnl >= 0;

          return (
            <Tooltip key={day.date} title={`${day.date}: ${signedRupees(day.pnl)}`}>
              <Stack sx={{ alignItems: "center", width: 28 }}>
                <Box sx={{ height: half, display: "flex", alignItems: "flex-end" }}>
                  {positive && (
                    <Box sx={{ width: 18, height, bgcolor: "success.main", borderRadius: 0.5 }} />
                  )}
                </Box>
                <Box sx={{ width: 28, borderTop: 1, borderColor: "divider" }} />
                <Box sx={{ height: half }}>
                  {!positive && (
                    <Box sx={{ width: 18, height, bgcolor: "error.main", borderRadius: 0.5 }} />
                  )}
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10 }}>
                  {day.date.slice(5)}
                </Typography>
              </Stack>
            </Tooltip>
          );
        })}
      </Stack>
    </Box>
  );
}

function TradesPnLPage() {
  const [mode, setMode] = useState<TradeMode>("DRY_RUN");
  const [data, setData] = useState<TradeStatistics | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  const load = useCallback(async (selectedMode: TradeMode) => {
    setLoading(true);
    setError(null);

    try {
      setData(await getTradeStatistics(selectedMode));
    } catch (err) {
      console.error(err);
      setError("Unable to load trade statistics. Check that the backend is running.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(mode);
  }, [mode, load]);

  const handleSync = async () => {
    setSyncing(true);
    setSyncMessage(null);

    try {
      const result = await syncZerodhaTrades();
      setSyncMessage(
        `Synced: ${result.trades_new ?? 0} new fill(s), ${result.orders_updated ?? 0} order status update(s).`
      );
      await load(mode);
    } catch (err) {
      console.error(err);
      setSyncMessage("Sync failed. Is today's Zerodha login complete?");
    } finally {
      setSyncing(false);
    }
  };

  const summary = data?.summary;

  return (
    <Stack spacing={3}>
      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={2}
        sx={{ justifyContent: "space-between", alignItems: { md: "center" } }}
      >
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            Trades &amp; P&amp;L
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Zerodha orders, fills and profit/loss
            {data?.tracking_since ? ` since ${formatDateTime(data.tracking_since)}` : ""}
          </Typography>
        </Box>

        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <ToggleButtonGroup
            size="small"
            exclusive
            value={mode}
            onChange={(_, value: TradeMode | null) => value && setMode(value)}
          >
            <ToggleButton value="DRY_RUN">Dry run</ToggleButton>
            <ToggleButton value="LIVE">Live</ToggleButton>
          </ToggleButtonGroup>

          {mode === "LIVE" && (
            <Button
              variant="outlined"
              startIcon={syncing ? <CircularProgress size={16} /> : <SyncIcon />}
              disabled={syncing || !data?.zerodha_connected}
              onClick={handleSync}
            >
              Sync trades
            </Button>
          )}

          <Button
            variant="contained"
            startIcon={<RefreshIcon />}
            disabled={loading}
            onClick={() => void load(mode)}
          >
            Refresh
          </Button>
        </Stack>
      </Stack>

      {error && <Alert severity="error">{error}</Alert>}
      {syncMessage && <Alert severity="info" onClose={() => setSyncMessage(null)}>{syncMessage}</Alert>}

      {loading && !data && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      )}

      {data && summary && (
        <>
          {mode === "LIVE" && !data.zerodha_connected && (
            <Alert severity="warning">
              Zerodha is not connected today. Zerodha only provides today&apos;s
              fills, so complete the daily login and open this page (or press
              Sync trades) after trading each day, before the next morning&apos;s reset.
            </Alert>
          )}
          {data.sync?.error && <Alert severity="warning">{data.sync.error}</Alert>}
          {data.prices_error && <Alert severity="warning">{data.prices_error}</Alert>}
          {data.notes.map((note) => (
            <Alert key={note} severity="info">{note}</Alert>
          ))}
          {summary.unmatched_sells > 0 && (
            <Alert severity="warning">
              {summary.unmatched_sells} sell fill(s) had no tracked buy (for example,
              shares bought before tracking started). They are excluded from P&amp;L.
            </Alert>
          )}

          <Grid container spacing={2}>
            <Grid size={{ xs: 12, sm: 6, md: 2 }}>
              <StatCard
                label="Realized P&L"
                value={signedRupees(summary.realized_pnl)}
                color={pnlColor(summary.realized_pnl)}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 2 }}>
              <StatCard
                label="Unrealized P&L"
                value={signedRupees(summary.unrealized_pnl)}
                color={pnlColor(summary.unrealized_pnl)}
                hint={summary.unrealized_complete ? undefined : "Some live prices missing"}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 2 }}>
              <StatCard label="Closed trades" value={String(summary.closed_trades)} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 2 }}>
              <StatCard
                label="Win rate"
                value={summary.win_rate_percent === null ? "-" : `${summary.win_rate_percent}%`}
                hint={`${summary.wins} won / ${summary.losses} lost`}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 2 }}>
              <StatCard
                label="Avg win / avg loss"
                value={`${rupees(summary.average_win)} / ${rupees(summary.average_loss)}`}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 2 }}>
              <StatCard label="Open positions" value={String(summary.open_positions)} />
            </Grid>
          </Grid>

          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
              Daily realized P&amp;L
            </Typography>
            <DailyPnlBars days={summary.daily_pnl} />
          </Paper>

          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 5 }}>
              <Paper variant="outlined" sx={{ p: 2, height: "100%" }}>
                <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
                  By stock
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Symbol</TableCell>
                        <TableCell align="right">Trades</TableCell>
                        <TableCell align="right">Wins</TableCell>
                        <TableCell align="right">Realized</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {summary.per_symbol.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={4}>No closed trades yet.</TableCell>
                        </TableRow>
                      )}
                      {summary.per_symbol.map((row) => (
                        <TableRow key={row.tradingsymbol}>
                          <TableCell>{row.tradingsymbol}</TableCell>
                          <TableCell align="right">{row.trades}</TableCell>
                          <TableCell align="right">{row.wins}</TableCell>
                          <TableCell align="right" sx={{ color: pnlColor(row.realized_pnl) }}>
                            {signedRupees(row.realized_pnl)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>
            </Grid>

            <Grid size={{ xs: 12, md: 7 }}>
              <Paper variant="outlined" sx={{ p: 2, height: "100%" }}>
                <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
                  Open positions
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Symbol</TableCell>
                        <TableCell>Product</TableCell>
                        <TableCell align="right">Qty</TableCell>
                        <TableCell align="right">Avg price</TableCell>
                        <TableCell align="right">Last price</TableCell>
                        <TableCell align="right">Unrealized</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {data.open_positions.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={6}>No open positions.</TableCell>
                        </TableRow>
                      )}
                      {data.open_positions.map((p) => (
                        <TableRow key={`${p.exchange}:${p.tradingsymbol}:${p.product}`}>
                          <TableCell>{p.tradingsymbol}</TableCell>
                          <TableCell>{p.product}</TableCell>
                          <TableCell align="right">{p.quantity}</TableCell>
                          <TableCell align="right">{rupees(p.average_price)}</TableCell>
                          <TableCell align="right">{rupees(p.last_price)}</TableCell>
                          <TableCell align="right" sx={{ color: pnlColor(p.unrealized_pnl) }}>
                            {signedRupees(p.unrealized_pnl)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>
            </Grid>
          </Grid>

          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
              Closed trades
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Closed</TableCell>
                    <TableCell>Symbol</TableCell>
                    <TableCell align="right">Qty</TableCell>
                    <TableCell align="right">Buy</TableCell>
                    <TableCell align="right">Sell</TableCell>
                    <TableCell align="right">P&amp;L</TableCell>
                    <TableCell align="right">Return</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.closed_trades.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7}>No closed trades yet.</TableCell>
                    </TableRow>
                  )}
                  {data.closed_trades.map((t, index) => (
                    <TableRow key={`${t.tradingsymbol}-${t.closed_at}-${index}`}>
                      <TableCell>{formatDateTime(t.closed_at)}</TableCell>
                      <TableCell>{t.tradingsymbol}</TableCell>
                      <TableCell align="right">{t.quantity}</TableCell>
                      <TableCell align="right">{rupees(t.buy_price)}</TableCell>
                      <TableCell align="right">{rupees(t.sell_price)}</TableCell>
                      <TableCell align="right" sx={{ color: pnlColor(t.pnl) }}>
                        {signedRupees(t.pnl)}
                      </TableCell>
                      <TableCell align="right" sx={{ color: pnlColor(t.pnl) }}>
                        {t.return_percent}%
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>

          <Paper variant="outlined" sx={{ p: 2 }}>
            <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 1, flexWrap: "wrap" }}>
              <Typography variant="h6" sx={{ fontWeight: 700, mr: 1 }}>
                Recent orders
              </Typography>
              {Object.entries(data.order_counts).map(([status, count]) => (
                <Chip
                  key={status}
                  size="small"
                  label={`${status}: ${count}`}
                  color={orderStatusColor(status)}
                  variant="outlined"
                />
              ))}
            </Stack>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Time</TableCell>
                    <TableCell>Symbol</TableCell>
                    <TableCell>Side</TableCell>
                    <TableCell align="right">Qty</TableCell>
                    <TableCell align="right">Limit</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Zerodha</TableCell>
                    <TableCell>Reason</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.recent_orders.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={8}>No orders yet.</TableCell>
                    </TableRow>
                  )}
                  {data.recent_orders.map((o) => (
                    <TableRow key={o.id}>
                      <TableCell>{formatDateTime(o.created_at)}</TableCell>
                      <TableCell>{o.tradingsymbol}</TableCell>
                      <TableCell>{o.side}</TableCell>
                      <TableCell align="right">{o.quantity}</TableCell>
                      <TableCell align="right">{rupees(o.limit_price)}</TableCell>
                      <TableCell>
                        <Chip size="small" label={o.status} color={orderStatusColor(o.status)} />
                      </TableCell>
                      <TableCell>
                        {o.kite_status
                          ? `${o.kite_status}${o.filled_quantity ? ` (${o.filled_quantity} filled)` : ""}`
                          : "-"}
                      </TableCell>
                      <TableCell sx={{ maxWidth: 360 }}>
                        <Typography variant="caption">
                          {o.kite_status_message || o.reasons.join("; ") || "-"}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </>
      )}
    </Stack>
  );
}

export default TradesPnLPage;
