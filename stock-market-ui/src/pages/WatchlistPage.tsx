import { useEffect, useState } from "react";

import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";

import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";

import {
  addStockToWatchlist,
  getStocks,
  getWatchlistStocks,
  removeStockFromWatchlist,
  syncWatchlistMarketData,
  updateWatchlistStock,
} from "../services/watchlistService";

import { getMonitorStatus } from "../services/monitorStatusService";
import { useWatchlist } from "../context/WatchlistContext";

import type {
  Stock,
  WatchlistStock,
} from "../types/watchlist";


type AddProgress =
  | "IDLE"
  | "ADDING"
  | "SYNCING"
  | "VALIDATING"
  | "READY"
  | "FAILED";

function WatchlistPage() {
  const { watchlists, selectedWatchlistId } = useWatchlist();
  const [stocks, setStocks] = useState<WatchlistStock[]>([]);
  const [masterStocks, setMasterStocks] = useState<Stock[]>([]);
  const [selectedStockId, setSelectedStockId] =
    useState<number | "">("");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [priority, setPriority] = useState(10);

  const [profitTargetPercent, setProfitTargetPercent] = useState(5.0);
  const [lossLimitPercent, setLossLimitPercent] = useState(5.0);

  const [addProgress, setAddProgress] =
    useState<AddProgress>("IDLE");

  const loadWatchlist = async () => {
    if (selectedWatchlistId === null) {
      setStocks([]);
      setLoading(false);
      return;
    }
    const watchlistId = selectedWatchlistId;
    try {
      setLoading(true);
      setError(null);
      const response = await getWatchlistStocks(watchlistId);
      setStocks(response);
    } catch (err) {
      console.error(err);
      setError("Unable to load watchlist");
    } finally {
      setLoading(false);
    }
  };

  const loadMasterStocks = async () => {
    try {
      const response = await getStocks();
      setMasterStocks(
        response.filter(
          (stock) => stock.active && stock.asset_type === "STOCK"
        )
      );
    } catch (err) {
      console.error(err);
      setError("Unable to load master stock list");
    }
  };

  useEffect(() => {
    void loadWatchlist();
    void loadMasterStocks();
  }, [selectedWatchlistId]);

  const resetDialog = () => {
    setSelectedStockId("");
    setPriority(10);
    setProfitTargetPercent(5.0);
    setLossLimitPercent(5.0);
    setAddProgress("IDLE");

  };

  const closeDialog = () => {
    if (saving) return;
    setDialogOpen(false);
    resetDialog();
  };

  const handleAddStock = async () => {
    if (selectedWatchlistId === null) {
      setError("No watchlist is available for this user");
      return;
    }

    const watchlistId = selectedWatchlistId;

    if (selectedStockId === "") {
      setError("Please select a stock from the master list");
      return;
    }

    const stock = masterStocks.find(
      (item) => item.stock_id === selectedStockId
    );

    if (!stock) {
      setError("Selected master stock could not be found");
      return;
    }

    const normalizedSymbol = stock.symbol.trim().toUpperCase();
    let onboardingStockId: number | null = null;

    try {
      setSaving(true);
      setError(null);
      setAddProgress("ADDING");

      if (stocks.some((item) => item.stock_id === stock.stock_id)) {
        setAddProgress("FAILED");
        setError(`${normalizedSymbol} is already in this watchlist`);
        return;
      }

      await addStockToWatchlist(watchlistId, {
        stock_id: stock.stock_id,
        priority,
        analysis_enabled: false,
        trading_enabled: false,
        profit_target_percent: profitTargetPercent,
        loss_limit_percent: lossLimitPercent,
      });

      onboardingStockId = stock.stock_id;
      setAddProgress("SYNCING");
      await syncWatchlistMarketData(watchlistId);

      await updateWatchlistStock(watchlistId, stock.stock_id, {
        priority,
        analysis_enabled: true,
        trading_enabled: false,
      });

      setAddProgress("VALIDATING");
      const monitorStatus = await getMonitorStatus(watchlistId);
      const stockStatus = monitorStatus.results.find(
        (result) => result.stock_id === stock.stock_id
      );

      if (
        !stockStatus ||
        stockStatus.status !== "PASS" ||
        !stockStatus.eligible_for_signal_analysis
      ) {
        await updateWatchlistStock(watchlistId, stock.stock_id, {
          priority,
          analysis_enabled: false,
          trading_enabled: false,
        });

        setAddProgress("FAILED");
        await loadWatchlist();
        setError(
          `${normalizedSymbol} was added, but market data is not ready. Analysis remains disabled.`
        );
        return;
      }

      setAddProgress("READY");
      await loadWatchlist();
      await new Promise((resolve) => setTimeout(resolve, 700));
      setDialogOpen(false);
      resetDialog();
    } catch (err) {
      console.error(err);
      setAddProgress("FAILED");

      if (onboardingStockId !== null) {
        try {
          await updateWatchlistStock(watchlistId, onboardingStockId, {
            priority,
            analysis_enabled: false,
            trading_enabled: false,
          });
        } catch (safetyError) {
          console.error(
            "Unable to restore fail-closed analysis state",
            safetyError
          );
        }
      }

      try {
        await loadWatchlist();
      } catch (refreshError) {
        console.error(
          "Unable to refresh watchlist after onboarding failure",
          refreshError
        );
      }

      setError(
        `Unable to complete setup for ${normalizedSymbol}. Analysis remains disabled.`
      );
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveStock = async (
    stockId: number,
    stockSymbol: string
  ) => {
    if (selectedWatchlistId === null) {
      setError("No watchlist is available for this user");
      return;
    }
    const watchlistId = selectedWatchlistId;

    const confirmed = window.confirm(
      `Remove ${stockSymbol} from this watchlist?`
    );

    if (!confirmed) {
      return;
    }

    try {
      setError(null);

      await removeStockFromWatchlist(
        watchlistId,
        stockId
      );

      await loadWatchlist();
    } catch (err) {
      console.error(err);

      setError(
        `Unable to remove ${stockSymbol}`
      );
    }
  };


  // const handleThresholdUpdate = async (
  //   item: WatchlistStock,
  //   field: "profit_target_percent" | "loss_limit_percent",
  //   value: number
  // ) => {
  //   if (selectedWatchlistId === null) {
  //     setError("No watchlist is available for this user");
  //     return;
  //   }

  //   if (!Number.isFinite(value) || value <= 0 || value > 100) {
  //     setError("Threshold must be greater than 0 and no more than 100%");
  //     return;
  //   }

  //   try {
  //     setError(null);

  //     await updateWatchlistStock(
  //       selectedWatchlistId,
  //       item.stock_id,
  //       {
  //         priority: item.priority,
  //         analysis_enabled: item.analysis_enabled,
  //         trading_enabled: false,

  //         profit_target_percent:
  //           field === "profit_target_percent"
  //             ? value
  //             : item.profit_target_percent,

  //         loss_limit_percent:
  //           field === "loss_limit_percent"
  //             ? value
  //             : item.loss_limit_percent,
  //       }
  //     );

  //     await loadWatchlist();
  //   } catch (err) {
  //     console.error(err);

  //     setError(
  //       `Unable to update thresholds for ${item.stock.symbol}`
  //     );
  //   }
  // };

  const watchlistStockIds = new Set(
    stocks.map((item) => item.stock_id)
  );

  const availableMasterStocks = masterStocks.filter(
    (stock) => !watchlistStockIds.has(stock.stock_id)
  );

  const selectedWatchlist = watchlists.find(
    (item) => item.watchlist_id === selectedWatchlistId
  );
  const selectedWatchlistName =
    selectedWatchlist?.name ??
    (selectedWatchlistId !== null
      ? `Watchlist ${selectedWatchlistId}`
      : "Watchlist");

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
        <Stack
          spacing={2}
          sx={{ alignItems: "center" }}
        >
          <CircularProgress />

          <Typography>
            Loading watchlist...
          </Typography>
        </Stack>
      </Box>
    );
  }

  return (
    <Box sx={{ py: 4, px: 3 }}>
      <Stack
        direction={{
          xs: "column",
          md: "row",
        }}
        spacing={2}
        sx={{
          justifyContent:
            "space-between",

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
            Watchlist Management
          </Typography>

          <Typography
            color="text.secondary"
          >
            Manage the instruments monitored by the decision engine
          </Typography>
        </Box>

        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => {
            resetDialog();
            setDialogOpen(true);
          }}
        >
          Add from Master
        </Button>
      </Stack>

      {error && (
        <Alert
          severity="error"
          sx={{ mb: 3 }}
          onClose={() =>
            setError(null)
          }
        >
          {error}
        </Alert>
      )}

      <Alert
        severity="info"
        sx={{ mb: 3 }}
      >
        This screen manages the analysis universe only.
        Trading remains disabled.
      </Alert>

      <Paper
        variant="outlined"
        sx={{
          overflowX: "auto",
        }}
      >
        <Box sx={{ p: 2 }}>
          <Typography
            variant="h6"
            sx={{ fontWeight: 700 }}
          >
            {selectedWatchlistName}
          </Typography>

          <Typography
            variant="body2"
            color="text.secondary"
          >
            {stocks.length} instruments
          </Typography>
        </Box>

        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>
                Symbol
              </TableCell>

              <TableCell>
                Company
              </TableCell>

              <TableCell>
                Exchange
              </TableCell>

              <TableCell align="right">
                Priority
              </TableCell>

              <TableCell align="right">
                Profit Target %
              </TableCell>

              <TableCell align="right">
              Loss Limit %
            </TableCell>

              <TableCell>
                Analysis
              </TableCell>

              <TableCell>
                Trading
              </TableCell>

              <TableCell align="right">
                Action
              </TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {stocks.map((item) => (
              <TableRow
                key={item.stock_id}
              >
                <TableCell
                  sx={{
                    fontWeight: 700,
                  }}
                >
                  {item.stock.symbol}
                </TableCell>

                <TableCell>
                  {
                    item.stock
                      .company_name
                  }
                </TableCell>

                <TableCell>
                  {
                    item.stock
                      .exchange
                  }
                </TableCell>

                <TableCell align="right">
                  {item.priority}
                </TableCell>

                <TableCell align="right">
                  {item.profit_target_percent?.toFixed(1) ?? "5.0"}%
                </TableCell>

                <TableCell align="right">
                  {item.loss_limit_percent?.toFixed(1) ?? "5.0"}%
                </TableCell>

                <TableCell>
                  <Chip
                    size="small"
                    label="OFF"
                    color="default"
                  />
                </TableCell>

                <TableCell align="right">
                  <Button
                    size="small"
                    color="error"
                    startIcon={
                      <DeleteIcon />
                    }
                    onClick={() =>
                      handleRemoveStock(
                        item.stock_id,
                        item.stock.symbol
                      )
                    }
                  >
                    Remove
                  </Button>
                </TableCell>
              </TableRow>
            ))}

            {stocks.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={7}
                  align="center"
                >
                  No stocks in this watchlist.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>

              <Dialog
  open={dialogOpen}
  onClose={closeDialog}
  fullWidth
  maxWidth="sm"
>
  <DialogTitle>
    Add Stock from Master List
  </DialogTitle>

  <DialogContent>
    <Stack spacing={2} sx={{ mt: 1 }}>
      <Alert severity="info">
        Select an existing stock from the master catalog.
        Removing a stock later removes it only from your watchlist.
      </Alert>

      <FormControl fullWidth>
        <InputLabel>Master Stock</InputLabel>

        <Select
          value={selectedStockId}
          label="Master Stock"
          disabled={saving}
          onChange={(event) =>
            setSelectedStockId(
              Number(event.target.value)
            )
          }
        >
          {availableMasterStocks.map((stock) => (
            <MenuItem
              key={stock.stock_id}
              value={stock.stock_id}
            >
              {stock.symbol} -{" "}
              {stock.company_name || stock.symbol}
              {stock.exchange
                ? ` (${stock.exchange})`
                : ""}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {availableMasterStocks.length === 0 && (
        <Alert severity="warning">
          All available master stocks are already
          in this watchlist.
        </Alert>
      )}

      <TextField
        label="Priority"
        type="number"
        value={priority}
        disabled={saving}
        onChange={(event) =>
          setPriority(
            Number(event.target.value)
          )
        }
        fullWidth
      />

        <TextField
        label="Profit Target %"
        type="number"
        value={profitTargetPercent}
        disabled={saving}
        slotProps={{
          htmlInput: {
            min: 0.1,
            max: 100,
            step: 0.1,
          },
        }}
        onChange={(event) =>
          setProfitTargetPercent(
            Number(event.target.value)
          )
        }
        helperText="Monitoring target only. Default: 5%."
        fullWidth
      />

      <TextField
        label="Loss Limit %"
        type="number"
        value={lossLimitPercent}
        disabled={saving}
        slotProps={{
          htmlInput: {
            min: 0.1,
            max: 100,
            step: 0.1,
          },
        }}
        onChange={(event) =>
          setLossLimitPercent(
            Number(event.target.value)
          )
        }
        helperText="Monitoring limit only. Enter a positive value, for example 5 means -5%."
        fullWidth
      />

      <Stack
        direction="row"
        sx={{
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Box>
          <Typography>
            Analysis Enabled
          </Typography>

          <Typography
            variant="body2"
            color="text.secondary"
          >
            Enabled automatically after market
            data passes validation
          </Typography>
        </Box>

        <Switch
          checked={addProgress === "READY"}
          disabled
        />
      </Stack>

      <Stack
        direction="row"
        sx={{
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Box>
          <Typography>
            Trading Enabled
          </Typography>

          <Typography
            variant="body2"
            color="text.secondary"
          >
            Trading remains disabled during stock
            onboarding
          </Typography>
        </Box>

        <Switch
          checked={false}
          disabled
        />
      </Stack>

      {addProgress !== "IDLE" && (
        <Alert
          severity={
            addProgress === "FAILED"
              ? "error"
              : addProgress === "READY"
              ? "success"
              : "info"
          }
        >
          {addProgress === "ADDING" &&
            "Adding master stock to your watchlist..."}

          {addProgress === "SYNCING" &&
            "Syncing market data. This may take a little time..."}

          {addProgress === "VALIDATING" &&
            "Validating market data readiness..."}

          {addProgress === "READY" &&
            "Market data is ready. Analysis enabled."}

          {addProgress === "FAILED" &&
            "Stock setup could not be completed. Analysis remains disabled."}
        </Alert>
      )}
    </Stack>
  </DialogContent>

  <DialogActions>
    <Button
      onClick={closeDialog}
      disabled={saving}
    >
      Cancel
    </Button>

    <Button
      variant="contained"
      onClick={handleAddStock}
      disabled={
        saving ||
        selectedStockId === "" ||
        availableMasterStocks.length === 0 ||
        !Number.isFinite(profitTargetPercent) ||
        profitTargetPercent <= 0 ||
        profitTargetPercent > 100 ||
        !Number.isFinite(lossLimitPercent) ||
        lossLimitPercent <= 0 ||
        lossLimitPercent > 100
      }
    >
      {saving ? (
        <>
          <CircularProgress
            size={18}
            sx={{ mr: 1 }}
            color="inherit"
          />
          PROCESSING
        </>
      ) : (
        "ADD TO MY STOCKS"
      )}
    </Button>
  </DialogActions>
</Dialog>
  
    </Box>
  );
}

export default WatchlistPage;