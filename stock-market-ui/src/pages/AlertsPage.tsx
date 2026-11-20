import { useCallback, useEffect, useState } from "react";
import RefreshIcon from "@mui/icons-material/Refresh";

import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
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
  Typography,
} from "@mui/material";

import { getAlerts } from "../services/alertsService";
import type { AlertSource, MarketAlert } from "../types/alerts";

const REFRESH_MS = 30_000;

const TRADINGVIEW_MESSAGE = `{
  "secret": "YOUR_TRADINGVIEW_WEBHOOK_SECRET",
  "symbol": "{{exchange}}:{{ticker}}",
  "price": {{close}},
  "interval": "{{interval}}",
  "time": "{{timenow}}",
  "message": "Breakout on {{ticker}} at {{close}}"
}`;

function AlertsPage() {
  const [source, setSource] = useState<AlertSource | "ALL">("ALL");
  const [alerts, setAlerts] = useState<MarketAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updated, setUpdated] = useState<Date | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setAlerts(await getAlerts(source === "ALL" ? undefined : source));
      setUpdated(new Date());
    } catch (err) {
      console.error(err);
      setError("Unable to load alerts.");
    } finally {
      setLoading(false);
    }
  }, [source]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  return (
    <Stack spacing={3}>
      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={2}
        sx={{ justifyContent: "space-between", alignItems: { md: "center" } }}
      >
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            Alerts
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Live early-breakout warnings and TradingView alerts · refreshes every 30 s
            {updated ? ` · updated ${updated.toLocaleTimeString()}` : ""}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <ToggleButtonGroup
            size="small"
            exclusive
            value={source}
            onChange={(_, v: AlertSource | "ALL" | null) => v && setSource(v)}
          >
            <ToggleButton value="ALL">All</ToggleButton>
            <ToggleButton value="EARLY_BREAKOUT">Early breakout</ToggleButton>
            <ToggleButton value="TRADINGVIEW">TradingView</ToggleButton>
          </ToggleButtonGroup>
          <Button
            variant="contained"
            startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <RefreshIcon />}
            disabled={loading}
            onClick={() => void load()}
          >
            Refresh
          </Button>
        </Stack>
      </Stack>

      <Alert severity="info">
        Alerts are early warnings only. No orders are placed from them; the strategy still
        waits for the 15-minute candle to close.
      </Alert>
      {error && <Alert severity="error">{error}</Alert>}

      <Paper variant="outlined" sx={{ p: 2 }}>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Time</TableCell>
                <TableCell>Source</TableCell>
                <TableCell>Symbol</TableCell>
                <TableCell align="right">Price</TableCell>
                <TableCell align="right">Level</TableCell>
                <TableCell align="right">Volume</TableCell>
                <TableCell>Message</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {alerts.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7}>No alerts yet.</TableCell>
                </TableRow>
              )}
              {alerts.map((a) => (
                <TableRow key={a.id}>
                  <TableCell>{new Date(a.created_at).toLocaleString()}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      color={a.source === "EARLY_BREAKOUT" ? "warning" : "info"}
                      label={a.source === "EARLY_BREAKOUT" ? "Early breakout" : "TradingView"}
                    />
                  </TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>{a.symbol}</TableCell>
                  <TableCell align="right">{a.price?.toFixed(2) ?? "-"}</TableCell>
                  <TableCell align="right">{a.level?.toFixed(2) ?? "-"}</TableCell>
                  <TableCell align="right">
                    {a.volume_ratio === null ? "-" : `${a.volume_ratio.toFixed(2)}×`}
                  </TableCell>
                  <TableCell sx={{ maxWidth: 480 }}>
                    <Typography variant="body2">{a.message}</Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          TradingView alert setup
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          In TradingView, create an alert, enable <b>Webhook URL</b> and set it to your public
          address + <code>/api/v1/webhooks/tradingview</code>. Paste this as the alert message
          (replace the secret with the one in your backend .env):
        </Typography>
        <Box
          component="pre"
          sx={{ p: 1.5, bgcolor: "action.hover", borderRadius: 1, overflowX: "auto", fontSize: 13 }}
        >
          {TRADINGVIEW_MESSAGE}
        </Box>
      </Paper>
    </Stack>
  );
}

export default AlertsPage;
