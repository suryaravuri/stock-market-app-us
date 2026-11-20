import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
  LinearProgress,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/Delete";

import CsvUploadCard from "../components/CsvUploadCard";
import { useAuth } from "../context/AuthContext";
import {
  createBacktest,
  deleteDataset,
  getBacktest,
  listBacktests,
  listDatasets,
} from "../services/backtestService";
import type { BacktestDataset, BacktestRun, BacktestSummary } from "../types/backtest";

const POLL_MS = 5000;

const fmt = (v: number | null | undefined, suffix = "") =>
  v === null || v === undefined ? "-" : `${v.toLocaleString()}${suffix}`;

const day = (iso: string | null) => (iso ? iso.slice(0, 10) : "-");

function statusColor(s: string): "default" | "info" | "success" | "error" | "warning" {
  if (s === "COMPLETED" || s === "READY") return "success";
  if (s === "RUNNING" || s === "UPLOADING") return "info";
  if (s === "FAILED") return "error";
  if (s === "QUEUED") return "warning";
  return "default";
}

function SummaryGrid({ s }: { s: BacktestSummary }) {
  const items: [string, string][] = [
    ["Total return", fmt(s.total_return_percent, "%")],
    ["Buy & hold", fmt(s.buy_and_hold_return_percent, "%")],
    ["CAGR", fmt(s.cagr_percent, "%")],
    ["Max drawdown", fmt(s.max_drawdown_percent, "%")],
    ["Sharpe", fmt(s.sharpe_ratio)],
    ["Trades", fmt(s.trades)],
    ["Win rate", fmt(s.win_rate_percent, "%")],
    ["Profit factor", fmt(s.profit_factor)],
    ["Avg R", fmt(s.average_r_multiple)],
    ["Ending equity", fmt(s.ending_equity)],
  ];
  return (
    <Grid container spacing={2}>
      {items.map(([label, value]) => (
        <Grid key={label} size={{ xs: 6, sm: 4, md: 2.4 }}>
          <Typography variant="caption" color="text.secondary">
            {label}
          </Typography>
          <Typography sx={{ fontWeight: 700 }}>{value}</Typography>
        </Grid>
      ))}
    </Grid>
  );
}

function BacktestsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "ADMIN";

  const [datasets, setDatasets] = useState<BacktestDataset[]>([]);
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [symbols, setSymbols] = useState("");
  const [start, setStart] = useState("2025-01-01");
  const [end, setEnd] = useState("2025-12-31");
  const [cash, setCash] = useState(10000);
  const [source, setSource] = useState<"ALPACA" | "UPLOAD">("UPLOAD");
  const [submitting, setSubmitting] = useState(false);

  const [selected, setSelected] = useState<BacktestRun | null>(null);

  const load = useCallback(async () => {
    try {
      const [d, r] = await Promise.all([listDatasets(), listBacktests()]);
      setDatasets(d);
      setRuns(r);
    } catch {
      setError("Unable to load backtests");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Keep polling while something is queued or running.
  useEffect(() => {
    if (!runs.some((r) => r.status === "QUEUED" || r.status === "RUNNING")) {
      return;
    }
    const timer = window.setInterval(load, POLL_MS);
    return () => window.clearInterval(timer);
  }, [runs, load]);

  const readySymbols = datasets.filter((d) => d.status === "READY").map((d) => d.symbol);

  const onUploaded = (ds: BacktestDataset) => {
    setSource("UPLOAD");
    setSymbols(ds.symbol);
    // Leave ~3 months for indicator warm-up at the start of the file.
    if (ds.first_bar && ds.last_bar) {
      const first = new Date(ds.first_bar);
      first.setMonth(first.getMonth() + 3);
      setStart(first.toISOString().slice(0, 10));
      setEnd(ds.last_bar.slice(0, 10));
    }
    load();
  };

  const startRun = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await createBacktest({
        symbols: symbols.split(",").map((s) => s.trim()).filter(Boolean),
        start_date: start,
        end_date: end,
        starting_cash: cash,
        data_source: source,
      });
      await load();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Could not start the backtest");
    } finally {
      setSubmitting(false);
    }
  };

  const openRun = async (run: BacktestRun) => {
    setSelected(await getBacktest(run.backtest_run_id));
  };

  return (
    <Box sx={{ py: 4, px: 3 }}>
      <Typography variant="h4" sx={{ fontWeight: 700, mb: 3 }}>
        Backtests
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Stack spacing={3}>
        {isAdmin && <CsvUploadCard onUploaded={onUploaded} />}

        {datasets.length > 0 && (
          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
                Uploaded data
              </Typography>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Symbol</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Bars</TableCell>
                    <TableCell>From</TableCell>
                    <TableCell>To</TableCell>
                    <TableCell>Note</TableCell>
                    {isAdmin && <TableCell />}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {datasets.map((d) => (
                    <TableRow key={d.backtest_dataset_id}>
                      <TableCell>{d.symbol}</TableCell>
                      <TableCell>
                        <Chip size="small" label={d.status} color={statusColor(d.status)} />
                      </TableCell>
                      <TableCell>{d.base_timeframe ?? "-"}</TableCell>
                      <TableCell>{day(d.first_bar)}</TableCell>
                      <TableCell>{day(d.last_bar)}</TableCell>
                      <TableCell>{d.message}</TableCell>
                      {isAdmin && (
                        <TableCell>
                          {d.status === "READY" && (
                            <IconButton
                              size="small"
                              aria-label="Delete data"
                              onClick={async () => {
                                await deleteDataset(d.backtest_dataset_id);
                                load();
                              }}
                            >
                              <DeleteOutlineIcon fontSize="small" />
                            </IconButton>
                          )}
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}

        {isAdmin && (
          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>
                New backtest
              </Typography>
              <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                <TextField
                  select
                  size="small"
                  label="Data"
                  value={source}
                  onChange={(e) => setSource(e.target.value as "ALPACA" | "UPLOAD")}
                  sx={{ minWidth: 180 }}
                >
                  <MenuItem value="UPLOAD">Uploaded CSV</MenuItem>
                  <MenuItem value="ALPACA">Alpaca history (US)</MenuItem>
                </TextField>
                <TextField
                  size="small"
                  label="Symbols"
                  value={symbols}
                  onChange={(e) => setSymbols(e.target.value.toUpperCase())}
                  helperText={
                    source === "UPLOAD"
                      ? `Ready: ${readySymbols.join(", ") || "none yet"}`
                      : "Comma-separated, max 10"
                  }
                />
                <TextField size="small" type="date" label="Start" value={start}
                  onChange={(e) => setStart(e.target.value)} slotProps={{ inputLabel: { shrink: true } }} />
                <TextField size="small" type="date" label="End" value={end}
                  onChange={(e) => setEnd(e.target.value)} slotProps={{ inputLabel: { shrink: true } }} />
                <TextField size="small" type="number" label="Starting cash" value={cash}
                  onChange={(e) => setCash(Number(e.target.value))} />
                <Button variant="contained" onClick={startRun} disabled={submitting || !symbols.trim()}>
                  {submitting ? "Starting..." : "Run backtest"}
                </Button>
              </Stack>
            </CardContent>
          </Card>
        )}

        <Card variant="outlined">
          <CardContent>
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
              Runs
            </Typography>
            {runs.length === 0 ? (
              <Typography color="text.secondary">No backtests yet.</Typography>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>#</TableCell>
                    <TableCell>Symbols</TableCell>
                    <TableCell>Period</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Return</TableCell>
                    <TableCell>Buy & hold</TableCell>
                    <TableCell>Max DD</TableCell>
                    <TableCell>Trades</TableCell>
                    <TableCell>Message</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {runs.map((r) => (
                    <TableRow
                      key={r.backtest_run_id}
                      hover
                      sx={{ cursor: r.status === "COMPLETED" ? "pointer" : "default" }}
                      onClick={() => r.status === "COMPLETED" && openRun(r)}
                    >
                      <TableCell>{r.backtest_run_id}</TableCell>
                      <TableCell>{r.symbols.join(", ")}</TableCell>
                      <TableCell>
                        {r.start_date} → {r.end_date}
                      </TableCell>
                      <TableCell sx={{ minWidth: 140 }}>
                        <Chip size="small" label={r.status} color={statusColor(r.status)} />
                        {r.status === "RUNNING" && (
                          <LinearProgress variant="determinate" value={r.progress_percent} sx={{ mt: 0.5 }} />
                        )}
                      </TableCell>
                      <TableCell>{fmt(r.summary?.total_return_percent, "%")}</TableCell>
                      <TableCell>{fmt(r.summary?.buy_and_hold_return_percent, "%")}</TableCell>
                      <TableCell>{fmt(r.summary?.max_drawdown_percent, "%")}</TableCell>
                      <TableCell>{fmt(r.summary?.trades)}</TableCell>
                      <TableCell sx={{ maxWidth: 320 }}>{r.message}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </Stack>

      <Dialog open={selected !== null} onClose={() => setSelected(null)} maxWidth="md" fullWidth>
        <DialogTitle>
          Backtest #{selected?.backtest_run_id}: {selected?.symbols.join(", ")}
        </DialogTitle>
        <DialogContent>
          {selected?.results?.overall?.summary && (
            <Box sx={{ mb: 3 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                Overall
              </Typography>
              <SummaryGrid s={selected.results.overall.summary} />
            </Box>
          )}
          {Object.entries(selected?.results?.by_symbol ?? {}).map(([sym, s]) => (
            <Box key={sym} sx={{ mb: 3 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                {sym}
              </Typography>
              <SummaryGrid s={s} />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Exits:{" "}
                {Object.entries(s.exit_reasons).map(([k, v]) => `${k} ${v}`).join(", ") || "none"}
                {s.evaluation_errors && Object.keys(s.evaluation_errors).length > 0 &&
                  ` · Strategy errors: ${Object.entries(s.evaluation_errors).map(([k, v]) => `${k} ${v}`).join(", ")}`}
                {s.skipped_entries && Object.keys(s.skipped_entries).length > 0 &&
                  ` · Skipped entries: ${Object.entries(s.skipped_entries).map(([k, v]) => `${k} ${v}`).join(", ")}`}
              </Typography>
            </Box>
          ))}
        </DialogContent>
      </Dialog>
    </Box>
  );
}

export default BacktestsPage;
