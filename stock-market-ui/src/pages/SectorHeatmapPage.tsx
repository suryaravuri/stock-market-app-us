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
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";

import { getSectorHeatmap } from "../services/performanceService";
import type { HeatmapPeriod, HeatmapStock, SectorHeatmap } from "../types/performance";

// % change that gets the strongest colour, per period.
const COLOR_CAP: Record<HeatmapPeriod, number> = { "1D": 3, "1W": 6, "1M": 12, "3M": 25, "6M": 40 };
const PERIOD_LABEL: Record<HeatmapPeriod, string> = {
  "1D": "today vs yesterday's close",
  "1W": "vs 5 sessions ago",
  "1M": "vs 21 sessions ago",
  "3M": "vs 63 sessions ago",
  "6M": "vs 126 sessions ago",
};

function tileColor(change: number | null, cap: number): string {
  if (change === null) {
    return "rgba(128,128,128,0.15)";
  }
  const strength = Math.min(Math.abs(change) / cap, 1);
  const alpha = 0.15 + strength * 0.75;
  return change >= 0 ? `rgba(22,163,74,${alpha})` : `rgba(220,38,38,${alpha})`;
}

function signedPct(value: number | null): string {
  if (value === null) {
    return "n/a";
  }
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function prettySector(sector: string): string {
  return sector
    .toLowerCase()
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function Tile({ stock, cap }: { stock: HeatmapStock; cap: number }) {
  const strong = stock.change_pct !== null && Math.abs(stock.change_pct) / cap > 0.55;
  return (
    <Tooltip
      title={
        <>
          <div>{stock.company_name ?? stock.symbol}</div>
          <div>Price {stock.price.toFixed(2)}</div>
          <div>Compared with {stock.reference_price?.toFixed(2) ?? "n/a"}</div>
        </>
      }
    >
      <Box
        sx={{
          bgcolor: tileColor(stock.change_pct, cap),
          color: strong ? "#fff" : "text.primary",
          borderRadius: 1,
          px: 1,
          py: 0.75,
          minWidth: 84,
          textAlign: "center",
          cursor: "default",
        }}
      >
        <Typography variant="body2" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
          {stock.symbol}
        </Typography>
        <Typography variant="caption" sx={{ fontVariantNumeric: "tabular-nums" }}>
          {signedPct(stock.change_pct)}
        </Typography>
      </Box>
    </Tooltip>
  );
}

function SectorHeatmapPage() {
  const [period, setPeriod] = useState<HeatmapPeriod>("1D");
  const [data, setData] = useState<SectorHeatmap | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (p: HeatmapPeriod) => {
    setLoading(true);
    setError(null);
    try {
      setData(await getSectorHeatmap(p));
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setError(typeof detail === "string" ? detail : "Unable to load the heatmap.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(period);
  }, [load, period]);

  const cap = COLOR_CAP[period];

  return (
    <Box sx={{ p: 2 }}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mb: 2, alignItems: { sm: "center" } }}>
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h5">Sector Heatmap</Typography>
          <Typography variant="body2" color="text.secondary">
            % change {PERIOD_LABEL[period]}
            {data?.as_of ? ` · prices as of ${new Date(data.as_of).toLocaleString("en-US", { timeZone: "America/New_York" })} ET` : ""}
          </Typography>
        </Box>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={period}
          onChange={(_, value: HeatmapPeriod | null) => value && setPeriod(value)}
        >
          {(["1D", "1W", "1M", "3M", "6M"] as HeatmapPeriod[]).map((p) => (
            <ToggleButton key={p} value={p}>{p}</ToggleButton>
          ))}
        </ToggleButtonGroup>
        <Button
          variant="outlined"
          startIcon={loading ? <CircularProgress size={16} /> : <RefreshIcon />}
          onClick={() => void load(period)}
          disabled={loading}
        >
          Refresh
        </Button>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Box
        sx={{
          display: "grid",
          gap: 2,
          gridTemplateColumns: { xs: "1fr", md: "repeat(2, 1fr)", xl: "repeat(3, 1fr)" },
        }}
      >
        {(data?.sectors ?? []).map((sector) => (
          <Paper key={sector.sector} variant="outlined" sx={{ p: 1.5 }}>
            <Stack direction="row" sx={{ mb: 1, alignItems: "baseline" }} spacing={1}>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, flexGrow: 1 }}>
                {prettySector(sector.sector)}
              </Typography>
              <Typography
                variant="subtitle1"
                sx={{
                  fontWeight: 700,
                  fontVariantNumeric: "tabular-nums",
                  color: (sector.avg_change_pct ?? 0) >= 0 ? "success.main" : "error.main",
                }}
              >
                {signedPct(sector.avg_change_pct)}
              </Typography>
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
              {sector.advancers} up · {sector.decliners} down · best {sector.stocks[0]?.symbol ?? "-"}
            </Typography>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
              {sector.stocks.map((stock) => (
                <Tile key={stock.symbol} stock={stock} cap={cap} />
              ))}
            </Box>
          </Paper>
        ))}
      </Box>

      {data && data.sectors.length === 0 && (
        <Alert severity="info">No US stocks with candle data in your watchlists yet.</Alert>
      )}
    </Box>
  );
}

export default SectorHeatmapPage;
