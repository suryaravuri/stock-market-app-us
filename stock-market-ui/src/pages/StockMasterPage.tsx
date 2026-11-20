import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
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

import {
  createStock,
  getStocks,
} from "../services/watchlistService";

import type {
  CreateStockRequest,
  Stock,
} from "../types/watchlist";
import axios from "axios";
import { useRef } from "react";
import apiClient from "../api/client";

const emptyForm: CreateStockRequest = {
  symbol: "",
  company_name: "",
  exchange: "",
  asset_type: "STOCK",
  sector: "",
  industry: "",
  tradable: false,
  active: true,
};

function StockMasterPage() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);

  const [form, setForm] =
    useState<CreateStockRequest>({ ...emptyForm });

  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const bulkFileInputRef = useRef<HTMLInputElement | null>(null);

  async function loadStocks() {
    setLoading(true);
    setError(null);

    try {
      const data = await getStocks();
      setStocks(data ?? []);
    } catch (err) {
      console.error("Unable to load stock master", err);
      setError("Unable to load stock master.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadStocks();
  }, []);

  const filteredStocks = useMemo(() => {
    const value = search.trim().toLowerCase();

    if (!value) {
      return stocks;
    }

    return stocks.filter((stock) =>
      [
        stock.symbol,
        stock.company_name,
        stock.exchange,
        stock.asset_type,
        stock.sector,
        stock.industry,
      ]
        .filter((field) => field != null)
        .some((field) =>
          String(field).toLowerCase().includes(value)
        )
    );
  }, [stocks, search]);

  function handleChange<K extends keyof CreateStockRequest>(
    field: K,
    value: CreateStockRequest[K]
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function handleOpen() {
    setForm({ ...emptyForm });
    setError(null);
    setSuccess(null);
    setOpen(true);
  }

  function handleClose() {
    if (!saving) {
      setOpen(false);
      setError(null);
    }
  }

  function handleBulkImportClick() {
    bulkFileInputRef.current?.click();
    }

async function handleBulkFileSelected(
  event: React.ChangeEvent<HTMLInputElement>
) {
  const file = event.target.files?.[0];

  if (!file) {
    return;
  }

  try {
    const formData = new FormData();

    formData.append("file", file);

    console.log(
      "Uploading stock master CSV:",
      file.name
    );

    const response = await apiClient.post(
      "/stocks/bulk-upload",
      formData
    );

    console.log(
      "Bulk upload response:",
      response.data
    );

    // Refresh master-stock table after successful import.
    await loadStocks();

  } catch (error) {
   if (axios.isAxiosError(error)) {
    console.error(
      "Bulk stock upload failed:",
      error.response?.status,
      error.response?.data
    );
  } else {
    console.error(
      "Bulk stock upload failed:",
      error
    );
  }
  } finally {
    // Allows selecting the same CSV again.
    event.target.value = "";
  }
}

  async function handleSave() {
    const symbol = form.symbol.trim().toUpperCase();

    if (!symbol) {
      setError("Symbol is required.");
      return;
    }

    if (!form.company_name.trim()) {
      setError("Company name is required.");
      return;
    }

    if (!form.exchange.trim()) {
      setError("Exchange is required.");
      return;
    }

    setSaving(true);
    setError(null);

    const payload: CreateStockRequest = {
      symbol,
      company_name: form.company_name.trim(),
      exchange: form.exchange.trim().toUpperCase(),
      asset_type:
        form.asset_type.trim().toUpperCase() || "STOCK",
      sector: form.sector.trim(),
      industry: form.industry.trim(),

      /*
       * Keep analysis-only safety for now.
       * watchlistService.createStock() also enforces
       * tradable=false.
       */
      tradable: false,

      active: form.active,
    };

    try {
      await createStock(payload);

      setOpen(false);

      setSuccess(
        `${symbol} was successfully added to Stock Master.`
      );

      setForm({ ...emptyForm });

      await loadStocks();
    } catch (err: any) {
      console.error("Unable to create master stock", err);

      const detail = err?.response?.data?.detail;

      if (typeof detail === "string") {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(
          detail
            .map((item) => item?.msg ?? "Validation error")
            .join(", ")
        );
      } else {
        setError("Unable to add stock.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Box sx={{ py: 3 }}>

        <Box
  sx={{
    display: "flex",
    flexDirection: {
      xs: "column",
      md: "row",
    },
    justifyContent: "space-between",
    alignItems: {
      xs: "stretch",
      md: "center",
    },
    gap: 2,
    mb: 3,
  }}
>
  <Box>
    <Typography
      variant="h5"
      sx={{ fontWeight: 700, mb: 0.5 }}
    >
      Stock Master
    </Typography>

    <Typography
      variant="body2"
      color="text.secondary"
    >
      Maintain the global stock catalog available to
      application users.
    </Typography>
  </Box>

  <Box
    sx={{
      display: "flex",
      gap: 1,
    }}
  >
    <>
        <input
            ref={bulkFileInputRef}
            type="file"
            accept=".csv,text/csv"
            hidden
            onChange={handleBulkFileSelected}
        />

        <Button
            variant="outlined"
            onClick={handleBulkImportClick}
        >
            Upload CSV
        </Button>
        </>

    <Button
      variant="contained"
      onClick={handleOpen}
    >
      Add Stock
    </Button>
  </Box>
</Box>

      {error && !open && (
        <Alert
          severity="error"
          sx={{ mb: 2 }}
          onClose={() => setError(null)}
        >
          {error}
        </Alert>
      )}

      {success && (
        <Alert
          severity="success"
          sx={{ mb: 2 }}
          onClose={() => setSuccess(null)}
        >
          {success}
        </Alert>
      )}

      <Paper sx={{ p: 2, mb: 2 }}>
        <TextField
          fullWidth
          size="small"
          label="Search Stocks"
          placeholder="Search by symbol, company, exchange, sector or industry"
          value={search}
          onChange={(event) =>
            setSearch(event.target.value)
          }
        />
      </Paper>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Symbol</TableCell>
              <TableCell>Company</TableCell>
              <TableCell>Exchange</TableCell>
              <TableCell>Asset Type</TableCell>
              <TableCell>Sector</TableCell>
              <TableCell>Industry</TableCell>
              <TableCell align="center">
                Tradable
              </TableCell>
              <TableCell align="center">
                Active
              </TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell
                  colSpan={8}
                  align="center"
                  sx={{ py: 4 }}
                >
                  <CircularProgress size={28} />
                </TableCell>
              </TableRow>
            ) : filteredStocks.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={8}
                  align="center"
                  sx={{ py: 4 }}
                >
                  No stocks found.
                </TableCell>
              </TableRow>
            ) : (
              filteredStocks.map((stock) => (
                <TableRow
                  key={stock.stock_id}
                  hover
                >
                  <TableCell>
                    <Typography
                      variant="body2"
                      sx={{ fontWeight: 700 }}
                    >
                      {stock.symbol}
                    </Typography>
                  </TableCell>

                  <TableCell>
                    {stock.company_name || "-"}
                  </TableCell>

                  <TableCell>
                    {stock.exchange || "-"}
                  </TableCell>

                  <TableCell>
                    {stock.asset_type || "-"}
                  </TableCell>

                  <TableCell>
                    {stock.sector || "-"}
                  </TableCell>

                  <TableCell>
                    {stock.industry || "-"}
                  </TableCell>

                  <TableCell align="center">
                    {stock.tradable ? "Yes" : "No"}
                  </TableCell>

                  <TableCell align="center">
                    {stock.active ? "Yes" : "No"}
                  </TableCell>
                </TableRow>
              ))
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
        <DialogTitle>Add Stock to Master</DialogTitle>

        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {error && (
              <Alert severity="error">
                {error}
              </Alert>
            )}

                <TextField
  required
  label="Symbol"
  value={form.symbol}
  slotProps={{
    htmlInput: {
      maxLength: 20,
    },
  }}
  onChange={(event) =>
    handleChange(
      "symbol",
      event.target.value.toUpperCase()
    )
  }
/>

<TextField
  required
  label="Company Name"
  value={form.company_name}
  slotProps={{
    htmlInput: {
      maxLength: 255,
    },
  }}
  onChange={(event) =>
    handleChange(
      "company_name",
      event.target.value
    )
  }
/>

<TextField
  required
  label="Exchange"
  value={form.exchange}
  slotProps={{
    htmlInput: {
      maxLength: 30,
    },
  }}
  onChange={(event) =>
    handleChange(
      "exchange",
      event.target.value.toUpperCase()
    )
  }
/>

<TextField
  label="Asset Type"
  value={form.asset_type}
  slotProps={{
    htmlInput: {
      maxLength: 30,
    },
  }}
  onChange={(event) =>
    handleChange(
      "asset_type",
      event.target.value.toUpperCase()
    )
  }
/>

<TextField
  label="Sector"
  value={form.sector}
  slotProps={{
    htmlInput: {
      maxLength: 100,
    },
  }}
  onChange={(event) =>
    handleChange(
      "sector",
      event.target.value
    )
  }
/>

<TextField
  label="Industry"
  value={form.industry}
  slotProps={{
    htmlInput: {
      maxLength: 150,
    },
  }}
  onChange={(event) =>
    handleChange(
      "industry",
      event.target.value
    )
  }
/>

            <FormControlLabel
              control={
                <Checkbox
                  checked={form.active}
                  onChange={(event) =>
                    handleChange(
                      "active",
                      event.target.checked
                    )
                  }
                />
              }
              label="Active"
            />

            <Typography
              variant="caption"
              color="text.secondary"
            >
              New master stocks remain analysis-only until
              trading is explicitly enabled.
            </Typography>
          </Stack>
        </DialogContent>

        <DialogActions>
          <Button
            onClick={handleClose}
            disabled={saving}
          >
            Cancel
          </Button>

          <Button
            variant="contained"
            onClick={handleSave}
            disabled={
              saving ||
              !form.symbol.trim() ||
              !form.company_name.trim() ||
              !form.exchange.trim()
            }
          >
            {saving ? "Saving..." : "Add Stock"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default StockMasterPage;