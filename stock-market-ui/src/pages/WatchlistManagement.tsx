import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Paper,
  Select,
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
import DeleteOutlineIcon from "@mui/icons-material/Delete";

import {
  addStockToWatchlist,
  getStocks,
  getWatchlistStocks,
  removeStockFromWatchlist,
  syncWatchlistMarketData,
  updateWatchlistStock,
} from "../services/watchlistService";

import { getMarketDataQuality } from "../services/analysisService";

import type {
  Stock,
  WatchlistStock,
} from "../types/watchlist";

import { useWatchlist } from "../context/WatchlistContext";


type SetupStatus =
  | "IDLE"
  | "CREATING"
  | "SYNCING"
  | "VALIDATING"
  | "READY"
  | "FAILED";



export default function WatchlistManagement() {
  const [stocks, setStocks] = useState<WatchlistStock[]>([]);

  const [masterStocks, setMasterStocks] = useState<Stock[]>([]);
  const [selectedStockId, setSelectedStockId] =
                                  useState<number | "">("");

  const [loading, setLoading] = useState(false);

  const [open, setOpen] = useState(false);
  const [setupStatus, setSetupStatus] =
    useState<SetupStatus>("IDLE");

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");



  const [priority, setPriority] =
    useState(10);

  const { selectedWatchlistId } = useWatchlist();

  useEffect(() => {
  if (selectedWatchlistId === null) {
    return;
  }

  loadWatchlist();
  loadMasterStocks();
}, [selectedWatchlistId]);

async function loadMasterStocks() {
  try {
    const data = await getStocks();

    setMasterStocks(
      data.filter(
        (stock) =>
          stock.active &&
          stock.asset_type === "STOCK"
      )
    );
  } catch (err) {
    console.error(err);
    setError("Unable to load master stocks.");
  }
}

  async function loadWatchlist() {
    if (selectedWatchlistId === null) {
      return;
    }

    const watchlistId = selectedWatchlistId;

    try {
      setLoading(true);
      setError("");

      const data =
        await getWatchlistStocks(watchlistId);

      setStocks(data);
    } catch (err) {
      console.error(err);
      setError("Unable to load watchlist.");
    } finally {
      setLoading(false);
    }
  }

function resetForm() {
  setSelectedStockId("");
  setPriority(10);
  setSetupStatus("IDLE");
  setMessage("");
  setError("");
}

  function handleClose() {
    if (
      setupStatus === "CREATING" ||
      setupStatus === "SYNCING" ||
      setupStatus === "VALIDATING"
    ) {
      return;
    }

    setOpen(false);
    resetForm();
  }


  async function handleAddStock() {
  if (selectedWatchlistId === null) {
    setError("No watchlist is available for this user.");
    return;
  }

  if (selectedStockId === "") {
    setError("Please select a stock.");
    return;
  }

  const watchlistId = selectedWatchlistId;

  const stock = masterStocks.find(
    (item) => item.stock_id === selectedStockId
  );

  if (!stock) {
    setError("Selected stock was not found in the master list.");
    return;
  }

  const normalizedSymbol =
    stock.symbol.trim().toUpperCase();

  let addedToWatchlist = false;

  try {
    setError("");
    setMessage("");
    setSetupStatus("CREATING");

    // ---------------------------------
    // 1. Add existing MASTER stock
    //    to this user's watchlist.
    // ---------------------------------

    await addStockToWatchlist(
      watchlistId,
      {
        stock_id: stock.stock_id,
        priority,
        analysis_enabled: false,
        trading_enabled: false,
      }
    );

    addedToWatchlist = true;

    // ---------------------------------
    // 2. Sync market data
    // ---------------------------------

    setSetupStatus("SYNCING");

    await syncWatchlistMarketData(
      watchlistId
    );

    // ---------------------------------
    // 3. Validate market data
    // ---------------------------------

    setSetupStatus("VALIDATING");

    const quality =
      await getMarketDataQuality(
        normalizedSymbol
      );

    const ready =
      quality.status === "PASS" &&
      quality.usable_for_breakout === true;

    // ---------------------------------
    // 4. Fail closed if data isn't ready
    // ---------------------------------

    if (!ready) {
      await updateWatchlistStock(
        watchlistId,
        stock.stock_id,
        {
          priority,
          analysis_enabled: false,
          trading_enabled: false,
        }
      );

      setSetupStatus("FAILED");

      setMessage(
        `${normalizedSymbol} was added successfully, but market data is not ready. Analysis remains disabled.`
      );

      await loadWatchlist();
      await loadMasterStocks();
      return;
    }

    // ---------------------------------
    // 5. Enable analysis
    // ---------------------------------

    await updateWatchlistStock(
      watchlistId,
      stock.stock_id,
      {
        priority,
        analysis_enabled: true,
        trading_enabled: false,
      }
    );

    setSetupStatus("READY");

    setMessage(
      `${normalizedSymbol} is ready for analysis. Trading remains disabled.`
    );

    await loadWatchlist();
    await loadMasterStocks();

    setTimeout(() => {
      setOpen(false);
      resetForm();
    }, 1200);

  } catch (err) {
    console.error(err);

    // ---------------------------------
    // Fail closed
    // ---------------------------------

    if (addedToWatchlist) {
      try {
        await updateWatchlistStock(
          watchlistId,
          stock.stock_id,
          {
            priority,
            analysis_enabled: false,
            trading_enabled: false,
          }
        );
      } catch (disableError) {
        console.error(
          "Failed to disable analysis:",
          disableError
        );
      }
    }

    setSetupStatus("FAILED");

    setError(
      `${normalizedSymbol} setup could not be completed. Analysis remains disabled.`
    );

    await loadWatchlist();
  }
}

async function handleAnalysisToggle(
  row: WatchlistStock,
  enabled: boolean
) {
  if (selectedWatchlistId === null) {
    setError("No watchlist is available for this user.");
    return;
  }

  const watchlistId = selectedWatchlistId;

  try {
    await updateWatchlistStock(
      watchlistId,
      row.stock_id,
      {
        priority: row.priority,
        analysis_enabled: enabled,
        trading_enabled: false,
      }
    );

    await loadWatchlist();
  } catch (err) {
    console.error(err);
    setError(`Unable to update ${row.stock.symbol}.`);
  }
}

async function handleRemove(
  row: WatchlistStock
) {
  if (selectedWatchlistId === null) {
    setError("No watchlist is available for this user.");
    return;
  }

  const watchlistId = selectedWatchlistId;

  try {
    await removeStockFromWatchlist(
      watchlistId,
      row.stock_id
    );

    // Refresh both views after removal.
    await Promise.all([
      loadWatchlist(),
      loadMasterStocks(),
    ]);

    // await loadWatchlist();
  } catch (err) {
    console.error(err);
    setError(`Unable to remove ${row.stock.symbol}.`);
  }
}



  const busy =
    setupStatus === "CREATING" ||
    setupStatus === "SYNCING" ||
    setupStatus === "VALIDATING";

    // Stocks already belonging to this user's watchlist.
    const watchlistStockIds = new Set(
      stocks.map((row) => row.stock_id)
    );

    // Master stocks that the user has NOT added yet.
    const availableMasterStocks =
      masterStocks.filter(
        (stock) =>
          !watchlistStockIds.has(stock.stock_id)
      );

  return (
    <Box>
            <Stack
            direction="row"
            sx={{
                justifyContent: "space-between",
                alignItems: "center",
                mb: 3,
            }}
            >
        <Box>
          <Typography variant="h4">
            Watchlist Management
          </Typography>

          <Typography
            variant="body2"
            color="text.secondary"
          >
            Manage stocks eligible for
            analysis. Trading remains
            disabled.
          </Typography>
        </Box>

        <Button
          variant="contained"
          onClick={() => {
            resetForm();
            setOpen(true);
          }}
        >
          Add Stock
        </Button>
      </Stack>

      {error && (
        <Alert
          severity="error"
          sx={{ mb: 2 }}
        >
          {error}
        </Alert>
      )}

      <TableContainer
        component={Paper}
      >
        <Table>
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

              <TableCell>
                Priority
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
            {stocks.map((row) => (
              <TableRow
                key={row.stock_id}
              >
                <TableCell>
                  <strong>
                    {row.stock.symbol}
                  </strong>
                </TableCell>

                <TableCell>
                  {row.stock.company_name}
                </TableCell>

                <TableCell>
                  {row.stock.exchange}
                </TableCell>

                <TableCell>
                  {row.priority}
                </TableCell>

                <TableCell>
                  <Switch
                    checked={
                      row.analysis_enabled
                    }
                    onChange={(e) =>
                      handleAnalysisToggle(
                        row,
                        e.target.checked
                      )
                    }
                  />
                </TableCell>

                <TableCell>
                  <Switch
                    checked={false}
                    disabled
                  />
                </TableCell>

                <TableCell align="right">
                  <Button
                    color="error"
                    startIcon={
                      <DeleteOutlineIcon />
                    }
                    onClick={() =>
                      handleRemove(row)
                    }
                  >
                    Remove
                  </Button>
                </TableCell>
              </TableRow>
            ))}

            {!loading &&
              stocks.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    align="center"
                  >
                    No stocks in
                    watchlist.
                  </TableCell>
                </TableRow>
              )}
          </TableBody>
        </Table>
      </TableContainer>

          <Dialog
  open={open}
  onClose={handleClose}
  fullWidth
  maxWidth="sm"
>
  <DialogTitle>
    Add Stock from Master List
  </DialogTitle>

  <DialogContent>
    <Stack
      spacing={3}
      sx={{ mt: 1 }}
    >
      <FormControl fullWidth>
        <InputLabel>
          Master Stock
        </InputLabel>

        <Select
          label="Master Stock"
          value={selectedStockId}
          disabled={busy}
          onChange={(e) =>
            setSelectedStockId(
              Number(e.target.value)
            )
          }
        >
          {availableMasterStocks.map(
            (stock) => (
              <MenuItem
                key={stock.stock_id}
                value={stock.stock_id}
              >
                {stock.symbol}
                {" — "}
                {stock.company_name ||
                  stock.symbol}
                {stock.exchange
                  ? ` (${stock.exchange})`
                  : ""}
              </MenuItem>
            )
          )}
        </Select>
      </FormControl>

      {availableMasterStocks.length === 0 && (
        <Alert severity="info">
          All available master stocks are already
          in this watchlist.
        </Alert>
      )}

      <TextField
        label="Priority"
        type="number"
        value={priority}
        disabled={busy}
        onChange={(e) =>
          setPriority(
            Number(e.target.value)
          )
        }
        // inputProps={{
        //   min: 0,
        // }}
      />

      <FormControlLabel
        control={
          <Switch
            checked={
              setupStatus === "READY"
            }
            disabled
          />
        }
        label={
          setupStatus === "READY"
            ? "Analysis Enabled"
            : "Analysis Disabled"
        }
      />

      <FormControlLabel
        control={
          <Switch
            checked={false}
            disabled
          />
        }
        label="Trading Disabled"
      />

      {setupStatus !== "IDLE" && (
        <Alert
          severity={
            setupStatus === "READY"
              ? "success"
              : setupStatus === "FAILED"
                ? "warning"
                : "info"
          }
        >
          {setupStatus === "CREATING" &&
            "Adding stock to your watchlist..."}

          {setupStatus === "SYNCING" &&
            "Syncing market data..."}

          {setupStatus === "VALIDATING" &&
            "Validating market data quality..."}

          {setupStatus === "READY" &&
            message}

          {setupStatus === "FAILED" &&
            (message || error)}
        </Alert>
      )}
    </Stack>
  </DialogContent>

  <DialogActions>
    <Button
      onClick={handleClose}
      disabled={busy}
    >
      Cancel
    </Button>

    <Button
      variant="contained"
      onClick={handleAddStock}
      disabled={
        busy ||
        selectedStockId === ""
      }
    >
      Add to My Stocks
    </Button>
  </DialogActions>
</Dialog>
    </Box>
  );
}