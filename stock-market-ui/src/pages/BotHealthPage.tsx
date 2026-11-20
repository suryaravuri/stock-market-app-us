import { useCallback, useEffect, useState } from "react";
import RefreshIcon from "@mui/icons-material/Refresh";
import axios from "axios";

import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControlLabel,
  Paper,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";

import { getTradeDecisions, getTradingReadiness } from "../services/botHealthService";
import type { CheckStatus, TradeDecisionList, TradingReadiness } from "../types/botHealth";

const STATUS_COLOR: Record<CheckStatus, "success" | "warning" | "error"> = {
  PASS: "success",
  WARN: "warning",
  FAIL: "error",
};

function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
  }
  return "Unable to load bot health.";
}

function timeEt(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("en-US", {
    timeZone: "America/New_York",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function BotHealthPage() {
  const [readiness, setReadiness] = useState<TradingReadiness | null>(null);
  const [decisions, setDecisions] = useState<TradeDecisionList | null>(null);
  const [symbol, setSymbol] = useState("");
  const [onlyBlocked, setOnlyBlocked] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [r, d] = await Promise.all([
        getTradingReadiness(),
        getTradeDecisions(symbol, onlyBlocked),
      ]);
      setReadiness(r);
      setDecisions(d);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [symbol, onlyBlocked]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Box sx={{ p: 2 }}>
      <Stack direction="row" spacing={2} sx={{ mb: 2, alignItems: "center" }}>
        <Typography variant="h5" sx={{ flexGrow: 1 }}>
          Bot Health - why no buy?
        </Typography>
        <Button
          variant="contained"
          startIcon={loading ? <CircularProgress size={16} /> : <RefreshIcon />}
          onClick={() => void load()}
          disabled={loading}
        >
          Refresh
        </Button>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {readiness && (
        <>
          <Alert severity={readiness.ready ? "success" : "error"} sx={{ mb: 2 }}>
            {readiness.headline}
          </Alert>

          <Paper sx={{ mb: 2 }}>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Gate</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Detail</TableCell>
                    <TableCell>Fix</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {readiness.checks.map((check) => (
                    <TableRow key={check.name}>
                      <TableCell>{check.name}</TableCell>
                      <TableCell>
                        <Chip size="small" label={check.status} color={STATUS_COLOR[check.status]} />
                      </TableCell>
                      <TableCell>{check.detail}</TableCell>
                      <TableCell>{check.fix ?? ""}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>

          <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: "wrap", rowGap: 1 }}>
            <Typography variant="body2" sx={{ mr: 1 }}>
              Last 24h ({readiness.decisions_24h.count} decisions):
            </Typography>
            {Object.entries(readiness.decisions_24h.blockers).map(([key, count]) => (
              <Chip key={key} size="small" variant="outlined" label={`${key}: ${count}`} />
            ))}
          </Stack>
          {readiness.decisions_24h.would_buy_if_enabled.length > 0 && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Strategy wanted to buy {readiness.decisions_24h.would_buy_if_enabled.join(", ")} but
              trading was switched off for them.
            </Alert>
          )}
        </>
      )}

      <Stack direction="row" spacing={2} sx={{ mb: 1, alignItems: "center" }}>
        <Typography variant="h6" sx={{ flexGrow: 1 }}>
          Decisions (newest first)
        </Typography>
        <TextField
          size="small"
          label="Symbol"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              void load();
            }
          }}
        />
        <FormControlLabel
          control={<Switch checked={onlyBlocked} onChange={(e) => setOnlyBlocked(e.target.checked)} />}
          label="Only no-buy"
        />
      </Stack>

      <Paper>
        <TableContainer sx={{ maxHeight: 520 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>Time (ET)</TableCell>
                <TableCell>Symbol</TableCell>
                <TableCell>Outcome</TableCell>
                <TableCell>Blocker</TableCell>
                <TableCell>Breakout</TableCell>
                <TableCell>Support bounce</TableCell>
                <TableCell>Order</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(decisions?.decisions ?? []).map((d, i) => (
                <TableRow key={`${d.evaluated_at}-${d.symbol}-${i}`}>
                  <TableCell sx={{ whiteSpace: "nowrap" }}>{timeEt(d.evaluated_at)}</TableCell>
                  <TableCell>{d.symbol}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={d.outcome === "ORDER_SUBMITTED" ? "BOUGHT" : "NO BUY"}
                      color={d.outcome === "ORDER_SUBMITTED" ? "success" : d.would_buy_if_enabled ? "warning" : "default"}
                    />
                  </TableCell>
                  <TableCell>{d.blocker ?? "-"}</TableCell>
                  <TableCell>{d.breakout_summary ?? "-"}</TableCell>
                  <TableCell>{d.bounce_summary ?? "-"}</TableCell>
                  <TableCell>{d.order_id ?? d.order_reason ?? "-"}</TableCell>
                </TableRow>
              ))}
              {decisions && decisions.decisions.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7}>
                    No decisions yet. They appear after the next scan or trading cycle.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Box>
  );
}

export default BotHealthPage;
