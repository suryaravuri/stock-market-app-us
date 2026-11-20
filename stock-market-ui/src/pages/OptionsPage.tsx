import { useState } from "react";
import SearchIcon from "@mui/icons-material/Search";
import axios from "axios";

import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  MenuItem,
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

import { getOptionsAnalysis } from "../services/derivativesService";
import type { OptionsAnalysis } from "../types/derivatives";

function money(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

function num(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return value.toFixed(digits);
}

function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
  }
  return "Unable to load options analysis.";
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card variant="outlined" sx={{ height: "100%" }}>
      <CardContent>
        <Typography variant="body2" color="text.secondary">
          {label}
        </Typography>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>
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

function OptionsPage() {
  const [symbol, setSymbol] = useState("AAPL");
  const [optionType, setOptionType] = useState<"CALL" | "PUT">("CALL");
  const [minDte, setMinDte] = useState(7);
  const [maxDte, setMaxDte] = useState(45);
  const [strikeRange, setStrikeRange] = useState(10);

  const [data, setData] = useState<OptionsAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyze = async () => {
    if (!symbol.trim()) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(
        await getOptionsAnalysis(symbol, {
          optionType,
          minDte,
          maxDte,
          strikeRangePercent: strikeRange,
        })
      );
    } catch (err) {
      console.error(err);
      setData(null);
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const selected = data?.selected;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Options
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Option-chain analysis for US stocks
        </Typography>
      </Box>

      <Alert severity="warning">
        Analysis only. This screen never places option orders. Options can lose
        100% of the premium paid.
      </Alert>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ alignItems: { md: "center" } }}>
          <TextField
            label="Symbol"
            size="small"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && void analyze()}
          />
          <TextField
            select
            label="Type"
            size="small"
            value={optionType}
            onChange={(e) => setOptionType(e.target.value as "CALL" | "PUT")}
            sx={{ minWidth: 110 }}
          >
            <MenuItem value="CALL">CALL</MenuItem>
            <MenuItem value="PUT">PUT</MenuItem>
          </TextField>
          <TextField
            label="Min days"
            type="number"
            size="small"
            value={minDte}
            onChange={(e) => setMinDte(Number(e.target.value))}
            sx={{ width: 110 }}
          />
          <TextField
            label="Max days"
            type="number"
            size="small"
            value={maxDte}
            onChange={(e) => setMaxDte(Number(e.target.value))}
            sx={{ width: 110 }}
          />
          <TextField
            label="Strike range %"
            type="number"
            size="small"
            value={strikeRange}
            onChange={(e) => setStrikeRange(Number(e.target.value))}
            sx={{ width: 140 }}
          />
          <Button
            variant="contained"
            startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <SearchIcon />}
            disabled={loading}
            onClick={() => void analyze()}
          >
            Analyze
          </Button>
        </Stack>
      </Paper>

      {error && <Alert severity="error">{error}</Alert>}

      {data && (
        <>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
              <Typography variant="h6" sx={{ fontWeight: 700, mr: 1 }}>
                {data.symbol} {money(data.underlying_price)}
              </Typography>
              <Chip size="small" label={`Signal: ${data.signal.state}`} />
              <Chip size="small" label={`Score: ${data.signal.score}`} />
              {data.signal.recommendation && (
                <Chip size="small" variant="outlined" label={data.signal.recommendation} />
              )}
              <Chip
                size="small"
                color={data.gate.analysis_allowed ? "success" : "default"}
                label={`Options gate: ${data.gate.status}`}
              />
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {data.gate.reason}
            </Typography>
          </Paper>

          {selected ? (
            <>
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                Selected contract: {selected.contract_symbol}
              </Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 6, md: 2 }}>
                  <Stat label="Strike / expiry" value={money(selected.strike_price)} hint={`${selected.expiration_date} (${selected.dte} days)`} />
                </Grid>
                <Grid size={{ xs: 6, md: 2 }}>
                  <Stat label="Bid / ask" value={`${num(selected.bid_price)} / ${num(selected.ask_price)}`} hint={`Spread ${num(selected.spread_percent, 1)}%`} />
                </Grid>
                <Grid size={{ xs: 6, md: 2 }}>
                  <Stat label="Cost per contract" value={money(selected.cost_per_contract)} hint="Midpoint × 100 shares" />
                </Grid>
                <Grid size={{ xs: 6, md: 2 }}>
                  <Stat label="Max loss (1 contract)" value={money(selected.max_loss_per_contract)} hint="If it expires worthless" />
                </Grid>
                <Grid size={{ xs: 6, md: 2 }}>
                  <Stat label="Breakeven at expiry" value={money(selected.breakeven_at_expiry)} />
                </Grid>
                <Grid size={{ xs: 6, md: 2 }}>
                  <Stat label="Open interest" value={selected.open_interest.toLocaleString()} />
                </Grid>
              </Grid>

              <Paper variant="outlined" sx={{ p: 2 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                  Greeks
                </Typography>
                <Stack direction="row" spacing={3} sx={{ flexWrap: "wrap" }}>
                  <Typography>Delta: {num(selected.greeks?.delta, 3)}</Typography>
                  <Typography>Gamma: {num(selected.greeks?.gamma, 3)}</Typography>
                  <Typography>Theta: {num(selected.greeks?.theta, 3)}</Typography>
                  <Typography>Vega: {num(selected.greeks?.vega, 3)}</Typography>
                  <Typography>
                    IV: {selected.implied_volatility === null ? "-" : `${(selected.implied_volatility * 100).toFixed(1)}%`}
                  </Typography>
                </Stack>
              </Paper>
            </>
          ) : (
            <Alert severity="info">{data.selection_reason}</Alert>
          )}

          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
              Contracts examined: {data.candidates_examined} (qualified: {data.candidates_qualified})
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Filters: {data.filters.min_dte}–{data.filters.max_dte} days, strike within{" "}
              {data.filters.strike_range_percent}%, spread ≤ {data.filters.max_spread_percent}%,
              open interest ≥ {data.filters.min_open_interest}
            </Typography>
            <TableContainer sx={{ mt: 1, maxHeight: 480 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Contract</TableCell>
                    <TableCell align="right">Strike</TableCell>
                    <TableCell>Expiry</TableCell>
                    <TableCell align="right">Bid</TableCell>
                    <TableCell align="right">Ask</TableCell>
                    <TableCell align="right">OI</TableCell>
                    <TableCell align="right">Delta</TableCell>
                    <TableCell>Result</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.candidates.map((row) => (
                    <TableRow key={row.contract_symbol}>
                      <TableCell>{row.contract_symbol}</TableCell>
                      <TableCell align="right">{num(row.strike_price)}</TableCell>
                      <TableCell>{row.expiration_date} ({row.dte}d)</TableCell>
                      <TableCell align="right">{num(row.bid_price)}</TableCell>
                      <TableCell align="right">{num(row.ask_price)}</TableCell>
                      <TableCell align="right">{row.open_interest}</TableCell>
                      <TableCell align="right">{num(row.delta, 2)}</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          color={row.qualified ? "success" : "default"}
                          variant={row.qualified ? "filled" : "outlined"}
                          label={row.reason}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>

          <Typography variant="caption" color="text.secondary">
            {data.data_feed_note} Educational analysis only, not investment advice.
          </Typography>
        </>
      )}
    </Stack>
  );
}

export default OptionsPage;
