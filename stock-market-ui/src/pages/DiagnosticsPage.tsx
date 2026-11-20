import { useState } from "react";
import SearchIcon from "@mui/icons-material/Search";
import CheckIcon from "@mui/icons-material/Check";
import CloseIcon from "@mui/icons-material/Close";
import axios from "axios";

import {
  Alert,
  Box,
  Button,
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
  TextField,
  Typography,
} from "@mui/material";

import { getBreakoutDiagnostics } from "../services/diagnosticsService";
import type { BreakoutDiagnostics } from "../types/diagnostics";

function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function Pass({ ok }: { ok: boolean }) {
  return ok ? (
    <CheckIcon fontSize="small" sx={{ color: "success.main" }} />
  ) : (
    <CloseIcon fontSize="small" sx={{ color: "error.main" }} />
  );
}

function statusColor(status: string): "success" | "warning" | "default" {
  if (status === "BREAKOUT_CONFIRMED") {
    return "success";
  }
  if (status.startsWith("PRICE_BREAKOUT")) {
    return "warning";
  }
  return "default";
}

function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
  }
  return "Unable to load diagnostics.";
}

function DiagnosticsPage() {
  const [symbol, setSymbol] = useState("AMGN");
  const [rows, setRows] = useState(30);
  const [data, setData] = useState<BreakoutDiagnostics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    if (!symbol.trim()) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(await getBreakoutDiagnostics(symbol, rows));
    } catch (err) {
      console.error(err);
      setData(null);
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const minRatio = data?.rules.min_volume_ratio ?? 1.2;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Breakout diagnostics
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Why a breakout was or wasn't confirmed, candle by candle (15-minute)
        </Typography>
      </Box>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ alignItems: { md: "center" } }}>
          <TextField
            label="Symbol"
            size="small"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && void load()}
          />
          <TextField
            label="Candles"
            type="number"
            size="small"
            value={rows}
            onChange={(e) => setRows(Number(e.target.value))}
            sx={{ width: 110 }}
          />
          <Button
            variant="contained"
            startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <SearchIcon />}
            disabled={loading}
            onClick={() => void load()}
          >
            Diagnose
          </Button>
        </Stack>
      </Paper>

      {error && <Alert severity="error">{error}</Alert>}

      {data && (
        <>
          <Grid container spacing={2}>
            {[
              ["Candles checked", data.summary.candles_checked],
              ["Price broke out", data.summary.price_breakouts],
              ["Blocked by volume", data.summary.blocked_by_volume],
              ["Blocked by candle quality", data.summary.blocked_by_candle_quality],
              ["Confirmed breakouts", data.summary.confirmed_breakouts],
            ].map(([label, value]) => (
              <Grid key={label as string} size={{ xs: 6, md: 2.4 }}>
                <Paper variant="outlined" sx={{ p: 2, textAlign: "center" }}>
                  <Typography variant="body2" color="text.secondary">
                    {label}
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 700 }}>
                    {value}
                  </Typography>
                </Paper>
              </Grid>
            ))}
          </Grid>

          {data.summary.notes.map((note) => (
            <Alert key={note} severity="info">
              {note}
            </Alert>
          ))}
          {data.data_feed_note && <Alert severity="warning">{data.data_feed_note}</Alert>}

          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              Rules used
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Breakout level = {data.rules.breakout_level}; must close above it plus{" "}
              {data.rules.confirmation_buffer}. Volume ≥ {data.rules.min_volume_ratio}× the prior{" "}
              {data.rules.lookback_candles}-candle average. Candle body ≥{" "}
              {Math.round(data.rules.min_body_ratio * 100)}% of range, close in the top{" "}
              {Math.round((1 - data.rules.min_close_location) * 100)}%, upper wick ≤{" "}
              {Math.round(data.rules.max_upper_wick_ratio * 100)}%. {data.rules.note}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Data: {data.data_feed} · times in {data.session_timezone}
            </Typography>
          </Paper>

          <Paper variant="outlined" sx={{ p: 2 }}>
            <TableContainer sx={{ maxHeight: 600 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Time</TableCell>
                    <TableCell align="right">Close</TableCell>
                    <TableCell align="right">Breakout at</TableCell>
                    <TableCell align="center">Price</TableCell>
                    <TableCell align="right">Volume</TableCell>
                    <TableCell align="right">Avg prior vol</TableCell>
                    <TableCell align="right">Ratio</TableCell>
                    <TableCell align="center">Volume</TableCell>
                    <TableCell align="center">Candle</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.candles.map((row) => (
                    <TableRow key={row.time}>
                      <TableCell>{row.time}</TableCell>
                      <TableCell align="right">{fmt(row.close)}</TableCell>
                      <TableCell align="right">{fmt(row.confirmation_price)}</TableCell>
                      <TableCell align="center">
                        <Pass ok={row.price_ok} />
                      </TableCell>
                      <TableCell align="right">{fmt(row.volume, 0)}</TableCell>
                      <TableCell align="right">{fmt(row.average_prior_volume, 0)}</TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          fontWeight: 700,
                          color:
                            row.volume_ratio !== null && row.volume_ratio >= minRatio
                              ? "success.main"
                              : "text.primary",
                        }}
                      >
                        {row.volume_ratio === null ? "-" : `${fmt(row.volume_ratio)}×`}
                      </TableCell>
                      <TableCell align="center">
                        <Pass ok={row.volume_ok} />
                      </TableCell>
                      <TableCell align="center">
                        <Pass ok={row.candle_ok} />
                      </TableCell>
                      <TableCell>
                        <Chip size="small" color={statusColor(row.status)} label={row.status} />
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

export default DiagnosticsPage;
