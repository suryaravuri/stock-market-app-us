import { useCallback, useEffect, useState } from "react";
import RefreshIcon from "@mui/icons-material/Refresh";
import axios from "axios";

import {
  Alert,
  Box,
  Button,
  CircularProgress,
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

import { getFuturesWatch } from "../services/derivativesService";
import type { FuturesWatch } from "../types/derivatives";

const DEFAULT_UNDERLYINGS = "NIFTY, BANKNIFTY, GOLDM, CRUDEOILM";

function rupees(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `\u20B9${value.toLocaleString("en-IN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

function changeColor(value: number | null): string {
  if (!value) {
    return "text.primary";
  }
  return value > 0 ? "success.main" : "error.main";
}

function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
  }
  return "Unable to load futures. Is today's Zerodha login complete?";
}

function FuturesPage() {
  const [underlyings, setUnderlyings] = useState(DEFAULT_UNDERLYINGS);
  const [data, setData] = useState<FuturesWatch | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (list: string) => {
    const names = list.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean);
    if (names.length === 0) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(await getFuturesWatch(names));
    } catch (err) {
      console.error(err);
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(DEFAULT_UNDERLYINGS);
  }, [load]);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          Futures
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Index (NFO) and commodity (MCX) futures via Zerodha
          {data ? ` · as of ${new Date(data.as_of).toLocaleTimeString()}` : ""}
        </Typography>
      </Box>

      <Alert severity="warning">
        Watch only. The app places no futures orders.{" "}
        {data?.risk_note ??
          "Futures are leveraged: losses can exceed the margin you put up."}
      </Alert>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ alignItems: { md: "center" } }}>
          <TextField
            label="Underlyings (comma-separated)"
            size="small"
            value={underlyings}
            onChange={(e) => setUnderlyings(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void load(underlyings)}
            sx={{ minWidth: 360 }}
          />
          <Button
            variant="contained"
            startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <RefreshIcon />}
            disabled={loading}
            onClick={() => void load(underlyings)}
          >
            Refresh
          </Button>
        </Stack>
      </Paper>

      {error && <Alert severity="error">{error}</Alert>}
      {data && data.not_found.length > 0 && (
        <Alert severity="info">No futures found for: {data.not_found.join(", ")}</Alert>
      )}

      {data && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Contract</TableCell>
                  <TableCell>Exch.</TableCell>
                  <TableCell>Expiry</TableCell>
                  <TableCell align="right">Price</TableCell>
                  <TableCell align="right">Change</TableCell>
                  <TableCell align="right">Spot / basis</TableCell>
                  <TableCell align="right">Lot size</TableCell>
                  <TableCell align="right">Value / lot</TableCell>
                  <TableCell align="right">Margin / lot</TableCell>
                  <TableCell align="right">₹ per point</TableCell>
                  <TableCell align="right">OI</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.contracts.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={11}>No contracts.</TableCell>
                  </TableRow>
                )}
                {data.contracts.map((row) => (
                  <TableRow key={`${row.exchange}:${row.tradingsymbol}`}>
                    <TableCell>
                      <Typography sx={{ fontWeight: 700 }}>{row.underlying}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {row.tradingsymbol}
                      </Typography>
                    </TableCell>
                    <TableCell>{row.exchange}</TableCell>
                    <TableCell>
                      {row.expiry} ({row.days_to_expiry}d)
                    </TableCell>
                    <TableCell align="right">{rupees(row.last_price)}</TableCell>
                    <TableCell align="right" sx={{ color: changeColor(row.change_percent) }}>
                      {row.change_percent === null ? "-" : `${row.change_percent > 0 ? "+" : ""}${row.change_percent}%`}
                    </TableCell>
                    <TableCell align="right">
                      {row.spot_price === null ? "-" : rupees(row.spot_price)}
                      {row.basis_points !== null && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                          {row.basis_points > 0 ? "+" : ""}
                          {row.basis_points} ({row.basis_percent}%)
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell align="right">{row.lot_size}</TableCell>
                    <TableCell align="right">{rupees(row.notional_per_lot, 0)}</TableCell>
                    <TableCell align="right">{rupees(row.margin_per_lot, 0)}</TableCell>
                    <TableCell align="right">
                      {row.rupees_per_point_per_lot === null ? "-" : rupees(row.rupees_per_point_per_lot, 0)}
                    </TableCell>
                    <TableCell align="right">{row.open_interest?.toLocaleString("en-IN") ?? "-"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
            "Value / lot" is price × lot size (NFO only; MCX contract units differ per commodity).
            "Margin / lot" is what Zerodha would block for one lot (NRML). A 1-point move changes a
            1-lot NFO position by the "₹ per point" amount. Educational information only.
          </Typography>
        </Paper>
      )}
    </Stack>
  );
}

export default FuturesPage;
