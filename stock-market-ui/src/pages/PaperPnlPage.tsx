import { useCallback, useEffect, useState } from "react";
import RefreshIcon from "@mui/icons-material/Refresh";
import axios from "axios";

import {
  Alert,
  Box,
  Button,
  CircularProgress,
  MenuItem,
  Paper,
  Select,
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

import { getPnlReport } from "../services/performanceService";
import type { PnlBucket, PnlGroup, PnlRange, PnlReport } from "../types/performance";

function usd(value: number | null | undefined, signed = false): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const text = Math.abs(value).toLocaleString("en-US", { style: "currency", currency: "USD" });
  if (!signed) {
    return value < 0 ? `-${text}` : text;
  }
  return `${value > 0 ? "+" : value < 0 ? "-" : ""}${text}`;
}

function color(value: number | null | undefined): string {
  if (!value) {
    return "text.primary";
  }
  return value > 0 ? "success.main" : "error.main";
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: number | null }) {
  return (
    <Paper variant="outlined" sx={{ p: 1.5, flex: 1, minWidth: 140 }}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography variant="h6" sx={{ fontWeight: 700, color: color(tone), fontVariantNumeric: "tabular-nums" }}>
        {value}
      </Typography>
    </Paper>
  );
}

function PnlBars({ buckets, field }: { buckets: PnlBucket[]; field: "account_pnl" | "realized_pnl" }) {
  if (buckets.length === 0) {
    return <Typography variant="body2" color="text.secondary">No data in this range yet.</Typography>;
  }
  const maxAbs = Math.max(...buckets.map((b) => Math.abs(b[field])), 1);
  const half = 70;
  return (
    <Box sx={{ overflowX: "auto" }}>
      <Stack direction="row" spacing={0.75} sx={{ alignItems: "flex-end", minWidth: "fit-content" }}>
        {buckets.map((b) => {
          const value = b[field];
          const height = Math.max(2, (Math.abs(value) / maxAbs) * half);
          return (
            <Tooltip key={b.key} title={`${b.label}: ${usd(value, true)} · ${b.trades} closed trades`}>
              <Stack sx={{ alignItems: "center", width: 40 }}>
                <Box sx={{ height: half, display: "flex", alignItems: "flex-end" }}>
                  {value >= 0 && <Box sx={{ width: 24, height, bgcolor: "success.main", borderRadius: 0.5 }} />}
                </Box>
                <Box sx={{ width: 40, borderTop: 1, borderColor: "divider" }} />
                <Box sx={{ height: half }}>
                  {value < 0 && <Box sx={{ width: 24, height, bgcolor: "error.main", borderRadius: 0.5 }} />}
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10, whiteSpace: "nowrap" }}>
                  {b.key.length === 10 ? b.key.slice(5) : b.key}
                </Typography>
              </Stack>
            </Tooltip>
          );
        })}
      </Stack>
    </Box>
  );
}

function PaperPnlPage() {
  const [group, setGroup] = useState<PnlGroup>("day");
  const [range, setRange] = useState<PnlRange>("1M");
  const [field, setField] = useState<"account_pnl" | "realized_pnl">("account_pnl");
  const [report, setReport] = useState<PnlReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (g: PnlGroup, r: PnlRange) => {
    setLoading(true);
    setError(null);
    try {
      setReport(await getPnlReport(g, r));
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setError(typeof detail === "string" ? detail : "Unable to load P&L.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(group, range);
  }, [load, group, range]);

  const t = report?.totals;

  return (
    <Box sx={{ p: 2 }}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ mb: 2, alignItems: { md: "center" } }}>
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h5">Paper P&amp;L (Alpaca)</Typography>
          <Typography variant="body2" color="text.secondary">
            Account P&amp;L includes open positions; realized = closed trades only.
          </Typography>
        </Box>
        <ToggleButtonGroup size="small" exclusive value={group}
          onChange={(_, v: PnlGroup | null) => v && setGroup(v)}>
          <ToggleButton value="day">Daily</ToggleButton>
          <ToggleButton value="week">Weekly</ToggleButton>
          <ToggleButton value="month">Monthly</ToggleButton>
        </ToggleButtonGroup>
        <Select size="small" value={range} onChange={(e) => setRange(e.target.value as PnlRange)}>
          <MenuItem value="1M">Last month</MenuItem>
          <MenuItem value="3M">Last 3 months</MenuItem>
          <MenuItem value="6M">Last 6 months</MenuItem>
          <MenuItem value="1A">Last year</MenuItem>
        </Select>
        <Button variant="outlined" onClick={() => void load(group, range)} disabled={loading}
          startIcon={loading ? <CircularProgress size={16} /> : <RefreshIcon />}>
          Refresh
        </Button>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {report?.orders_capped && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          More than 500 orders in this range: the oldest closed trades may be missing. Choose a shorter range.
        </Alert>
      )}

      {t && (
        <Stack direction="row" spacing={1.5} sx={{ mb: 2, flexWrap: "wrap", rowGap: 1.5 }}>
          <Stat label="Account P&L" value={usd(t.account_pnl, true)} tone={t.account_pnl} />
          <Stat label="Realized P&L" value={usd(t.realized_pnl, true)} tone={t.realized_pnl} />
          <Stat label="Unrealized (open)" value={usd(t.unrealized_pnl, true)} tone={t.unrealized_pnl} />
          <Stat label="Closed trades" value={`${t.trades} (${t.wins}W / ${t.losses}L)`} />
          <Stat label="Win rate" value={t.win_rate === null ? "-" : `${t.win_rate}%`} />
          <Stat label="Equity" value={usd(t.end_equity)} />
        </Stack>
      )}

      {report && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Stack direction="row" sx={{ mb: 1, alignItems: "center" }}>
            <Typography variant="h6" sx={{ flexGrow: 1 }}>
              {group === "day" ? "Daily" : group === "week" ? "Weekly" : "Monthly"} P&amp;L
            </Typography>
            <ToggleButtonGroup size="small" exclusive value={field}
              onChange={(_, v: "account_pnl" | "realized_pnl" | null) => v && setField(v)}>
              <ToggleButton value="account_pnl">Account</ToggleButton>
              <ToggleButton value="realized_pnl">Realized</ToggleButton>
            </ToggleButtonGroup>
          </Stack>
          <PnlBars buckets={report.buckets} field={field} />
          <TableContainer sx={{ mt: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Period</TableCell>
                  <TableCell align="right">Account P&amp;L</TableCell>
                  <TableCell align="right">%</TableCell>
                  <TableCell align="right">Realized</TableCell>
                  <TableCell align="right">Trades</TableCell>
                  <TableCell align="right">Win rate</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {[...report.buckets].reverse().map((b) => (
                  <TableRow key={b.key}>
                    <TableCell>{b.label}</TableCell>
                    <TableCell align="right" sx={{ color: color(b.account_pnl) }}>{usd(b.account_pnl, true)}</TableCell>
                    <TableCell align="right">{b.account_pnl_pct === null ? "-" : `${b.account_pnl_pct}%`}</TableCell>
                    <TableCell align="right" sx={{ color: color(b.realized_pnl) }}>{usd(b.realized_pnl, true)}</TableCell>
                    <TableCell align="right">{b.trades}</TableCell>
                    <TableCell align="right">{b.win_rate === null ? "-" : `${b.win_rate}%`}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {report && (
        <Stack direction={{ xs: "column", lg: "row" }} spacing={2}>
          <Paper variant="outlined" sx={{ p: 2, flex: 2 }}>
            <Typography variant="h6" sx={{ mb: 1 }}>Closed trades</Typography>
            <TableContainer sx={{ maxHeight: 420 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Exit (ET)</TableCell>
                    <TableCell>Symbol</TableCell>
                    <TableCell align="right">Qty</TableCell>
                    <TableCell align="right">Entry</TableCell>
                    <TableCell align="right">Exit</TableCell>
                    <TableCell align="right">P&amp;L</TableCell>
                    <TableCell align="right">%</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {report.trades.map((tr, i) => (
                    <TableRow key={`${tr.symbol}-${tr.exit_time}-${i}`}>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>
                        {new Date(tr.exit_time).toLocaleString("en-US", { timeZone: "America/New_York", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
                      </TableCell>
                      <TableCell>{tr.symbol}</TableCell>
                      <TableCell align="right">{tr.qty}</TableCell>
                      <TableCell align="right">{tr.entry_price.toFixed(2)}</TableCell>
                      <TableCell align="right">{tr.exit_price.toFixed(2)}</TableCell>
                      <TableCell align="right" sx={{ color: color(tr.pnl) }}>{usd(tr.pnl, true)}</TableCell>
                      <TableCell align="right">{tr.pnl_pct === null ? "-" : `${tr.pnl_pct}%`}</TableCell>
                    </TableRow>
                  ))}
                  {report.trades.length === 0 && (
                    <TableRow><TableCell colSpan={7}>No closed trades in this range.</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
          <Paper variant="outlined" sx={{ p: 2, flex: 1 }}>
            <Typography variant="h6" sx={{ mb: 1 }}>Open positions</Typography>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Symbol</TableCell>
                  <TableCell align="right">Qty</TableCell>
                  <TableCell align="right">Unrealized</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {report.open_positions.map((p) => (
                  <TableRow key={p.symbol}>
                    <TableCell>{p.symbol}</TableCell>
                    <TableCell align="right">{p.qty}</TableCell>
                    <TableCell align="right" sx={{ color: color(p.unrealized_pnl) }}>
                      {usd(p.unrealized_pnl, true)} ({p.unrealized_pnl_pct}%)
                    </TableCell>
                  </TableRow>
                ))}
                {report.open_positions.length === 0 && (
                  <TableRow><TableCell colSpan={3}>No open positions.</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </Paper>
        </Stack>
      )}
    </Box>
  );
}

export default PaperPnlPage;
