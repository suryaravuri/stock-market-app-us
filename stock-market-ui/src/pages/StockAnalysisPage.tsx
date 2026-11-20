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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";

import {
  getAnalysisSummary,
  getMultiTimeframeAnalysis,
} from "../services/analysisService";

import type {
  AnalysisSummary,
  MultiTimeframeAnalysis,
} from "../types/analysis";

import { getWatchlistStocks } from "../services/watchlistService";

// const SYMBOLS = [
//   "AMD",
//   "NVDA",
//   "META",
//   "MSFT",
//   "AMZN",
//   "PLTR",
//   "GOOGL",
// ];

import { useWatchlist } from "../context/WatchlistContext";




function classificationColor(
  classification: string
): "success" | "warning" | "error" | "default" {
  switch (classification) {
    case "STRONG":
      return "success";

    case "WATCH":
      return "warning";

    case "AVOID":
      return "error";

    default:
      return "default";
  }
}

function formatNumber(
  value: number | null | undefined,
  digits = 2
): string {
  if (value === null || value === undefined) {
    return "-";
  }

  return value.toFixed(digits);
}


function StockAnalysisPage() {
  const { selectedWatchlistId } = useWatchlist();
  const [symbol, setSymbol] = useState("AMD");
  const [symbols, setSymbols] = useState<string[]>([]);

  const [summary, setSummary] =
    useState<AnalysisSummary | null>(null);

  const [multiTimeframe, setMultiTimeframe] =
    useState<MultiTimeframeAnalysis | null>(null);



  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAnalysis = async (selectedSymbol: string) => {
    try {
      setLoading(true);
      setError(null);

      const [summaryResponse, multiTimeframeResponse] =
        await Promise.all([
          getAnalysisSummary(selectedSymbol),
          getMultiTimeframeAnalysis(selectedSymbol),
        ]);

      setSummary(summaryResponse);
      setMultiTimeframe(multiTimeframeResponse);
    } catch (err) {
      console.error(err);
      setError(`Unable to load analysis for ${selectedSymbol}`);
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
    loadAnalysis(symbol);
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
          <Typography>Loading stock analysis...</Typography>
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

  if (!summary || !multiTimeframe) {
    return null;
  }

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
          <Typography
            variant="h4"
            sx={{ fontWeight: 700 }}
          >
            Stock Analysis
          </Typography>

          <Typography color="text.secondary">
            Multi-timeframe technical analysis and indicator snapshot
          </Typography>
        </Box>

        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Symbol</InputLabel>

          <Select
            value={symbol}
            label="Symbol"
            onChange={(event) => setSymbol(event.target.value)}
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

            <Typography
              variant="h4"
              sx={{ fontWeight: 700 }}
            >
              {summary.symbol}
            </Typography>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ flex: 1 }}>
          <CardContent>
            <Typography color="text.secondary">
              Current Price
            </Typography>

            <Typography
              variant="h4"
              sx={{ fontWeight: 700 }}
            >
              ${formatNumber(summary.current_price)}
            </Typography>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ flex: 1 }}>
          <CardContent>
            <Typography color="text.secondary">
              Overall Score
            </Typography>

            <Typography
              variant="h4"
              sx={{ fontWeight: 700 }}
            >
              {multiTimeframe.overall_score}
            </Typography>
          </CardContent>
        </Card>

        <Card variant="outlined" sx={{ flex: 1 }}>
          <CardContent>
            <Typography color="text.secondary">
              Classification
            </Typography>

            <Box sx={{ mt: 1 }}>
              <Chip
                label={
                  multiTimeframe.overall_classification
                }
                color={classificationColor(
                  multiTimeframe.overall_classification
                )}
              />
            </Box>
          </CardContent>
        </Card>
      </Stack>

      <Paper
        variant="outlined"
        sx={{ mb: 3, overflow: "hidden" }}
      >
        <Box sx={{ p: 2 }}>
          <Typography
            variant="h6"
            sx={{ fontWeight: 700 }}
          >
            Multi-Timeframe Analysis
          </Typography>
        </Box>

        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Timeframe</TableCell>
              <TableCell align="right">Score</TableCell>
              <TableCell>Classification</TableCell>
              <TableCell align="right">Price</TableCell>
              <TableCell align="right">Support</TableCell>
              <TableCell align="right">Resistance</TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {Object.entries(
              multiTimeframe.timeframes
            ).map(([timeframe, analysis]) => (
              <TableRow key={timeframe}>
                <TableCell sx={{ fontWeight: 700 }}>
                  {timeframe}
                </TableCell>

                <TableCell align="right">
                  {analysis.score}
                </TableCell>

                <TableCell>
                  <Chip
                    label={analysis.classification}
                    color={classificationColor(
                      analysis.classification
                    )}
                    size="small"
                  />
                </TableCell>

                <TableCell align="right">
                  ${formatNumber(analysis.current_price)}
                </TableCell>

                <TableCell align="right">
                  ${formatNumber(
                    analysis.nearest_support
                  )}
                </TableCell>

                <TableCell align="right">
                  ${formatNumber(
                    analysis.nearest_resistance
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>

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
            Indicators — {summary.timeframe}
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="EMA 9"
              value={formatNumber(
                summary.indicators.ema_9,
                4
              )}
            />

            <Metric
              label="EMA 20"
              value={formatNumber(
                summary.indicators.ema_20,
                4
              )}
            />

            <Metric
              label="EMA 50"
              value={formatNumber(
                summary.indicators.ema_50,
                4
              )}
            />

            <Metric
              label="RSI 14"
              value={formatNumber(
                summary.indicators.rsi_14,
                2
              )}
            />

            <Metric
              label="MACD"
              value={formatNumber(
                summary.indicators.macd,
                4
              )}
            />

            <Metric
              label="MACD Signal"
              value={formatNumber(
                summary.indicators.macd_signal,
                4
              )}
            />

            <Metric
              label="MACD Histogram"
              value={formatNumber(
                summary.indicators.macd_histogram,
                4
              )}
            />

            <Metric
              label="ATR 14"
              value={formatNumber(
                summary.indicators.atr_14,
                4
              )}
            />

            <Metric
              label="Session VWAP"
              value={formatNumber(
                summary.indicators.session_vwap,
                4
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
            Support
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="Nearest"
              value={`$${formatNumber(
                summary.support.nearest
              )}`}
            />

            <Metric
              label="Next"
              value={`$${formatNumber(
                summary.support.next
              )}`}
            />

            <Metric
              label="Strongest"
              value={`$${formatNumber(
                summary.support.strongest
              )}`}
            />

            <Metric
              label="Strength"
              value={
                summary.support.nearest_level
                  ? String(
                      summary.support.nearest_level
                        .strength
                    )
                  : "-"
              }
            />

            <Metric
              label="Touches"
              value={
                summary.support.nearest_level
                  ? String(
                      summary.support.nearest_level
                        .touches
                    )
                  : "-"
              }
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
            Resistance
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="Nearest"
              value={`$${formatNumber(
                summary.resistance.nearest
              )}`}
            />

            <Metric
              label="Next"
              value={`$${formatNumber(
                summary.resistance.next
              )}`}
            />

            <Metric
              label="Strongest"
              value={`$${formatNumber(
                summary.resistance.strongest
              )}`}
            />

            <Metric
              label="Strength"
              value={
                summary.resistance.nearest_level
                  ? String(
                      summary.resistance.nearest_level
                        .strength
                    )
                  : "-"
              }
            />

            <Metric
              label="Touches"
              value={
                summary.resistance.nearest_level
                  ? String(
                      summary.resistance.nearest_level
                        .touches
                    )
                  : "-"
              }
            />
          </Stack>
        </Paper>
      </Stack>

      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ display: "block", mt: 2 }}
      >
        Analysis candle:{" "}
        {new Date(summary.timestamp).toLocaleString()} ·{" "}
        {summary.candle_count} candles analyzed
      </Typography>
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

      <Typography sx={{ fontWeight: 600 }}>
        {value}
      </Typography>
    </Stack>
  );
}

export default StockAnalysisPage;