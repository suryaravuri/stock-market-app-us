/**
 * Upload a CSV of candles for backtesting WITHOUT sending the file.
 *
 * PapaParse reads the file inside the browser. Rows are sent to the API in
 * chunks of 5,000 as plain JSON, so the file never reaches Google Cloud and
 * Cloud Run's 32 MB request limit never applies.
 *
 * Supports common layouts, e.g. Yahoo/yfinance exports:
 *   Datetime,Open,High,Low,Close,Adj Close,Volume
 *   2024-03-01 09:30:00-05:00,180.1,180.6,179.9,180.4,180.4,123456
 * and files with separate Date and Time columns.
 */
import { useMemo, useRef, useState } from "react";
import Papa from "papaparse";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
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
import UploadFileIcon from "@mui/icons-material/UploadFile";

import {
  completeDataset,
  createDataset,
  uploadChunk,
} from "../services/backtestService";
import type { BacktestDataset, CandleRow } from "../types/backtest";

const CHUNK_ROWS = 5000;
const NONE = "";

type Field = "date" | "time" | "open" | "high" | "low" | "close" | "volume";

// Header names we recognise automatically (lower-case, spaces removed).
const GUESSES: Record<Field, string[]> = {
  date: ["datetime", "timestamp", "date", "datetime(utc)", "time_stamp"],
  time: ["time"],
  open: ["open", "o"],
  high: ["high", "h"],
  low: ["low", "l"],
  close: ["close", "c", "last"], // deliberately not "adj close"
  volume: ["volume", "vol", "v"],
};

const TIMEZONES = [
  { value: "America/New_York", label: "US Eastern (NASDAQ/NYSE)" },
  { value: "Asia/Kolkata", label: "India (NSE/BSE)" },
  { value: "UTC", label: "UTC" },
];

function normalise(header: string): string {
  return header.toLowerCase().replace(/\s+/g, "");
}

function guessMapping(headers: string[]): Record<Field, string> {
  const mapping = {} as Record<Field, string>;
  (Object.keys(GUESSES) as Field[]).forEach((field) => {
    const match = headers.find((h) => GUESSES[field].includes(normalise(h)));
    mapping[field] = match ?? NONE;
  });
  // Only a "time" column (holding full date-times): use it as the date column.
  if (!mapping.date && mapping.time) {
    mapping.date = mapping.time;
  }
  // One column can't be both: drop the duplicate.
  if (mapping.time === mapping.date) {
    mapping.time = NONE;
  }
  return mapping;
}

async function withRetry<T>(fn: () => Promise<T>, attempts = 3): Promise<T> {
  let lastError: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      await new Promise((r) => setTimeout(r, 1000 * 2 ** i));
    }
  }
  throw lastError;
}

interface Props {
  onUploaded: (dataset: BacktestDataset) => void;
}

function CsvUploadCard({ onUploaded }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [symbol, setSymbol] = useState("");
  const [timezone, setTimezone] = useState("America/New_York");
  const [headers, setHeaders] = useState<string[]>([]);
  const [preview, setPreview] = useState<Record<string, string>[]>([]);
  const [mapping, setMapping] = useState<Record<Field, string>>(guessMapping([]));

  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const handleFile = (selected: File | null) => {
    setFile(selected);
    setError(null);
    setStatus(null);
    setProgress(0);
    if (!selected) {
      return;
    }
    // Guess the symbol from names like "AAPL_15min.csv".
    const base = selected.name.replace(/\.[^.]+$/, "").split(/[_\s-]/)[0];
    if (base && !symbol) {
      setSymbol(base.toUpperCase());
    }
    Papa.parse<Record<string, string>>(selected, {
      header: true,
      skipEmptyLines: true,
      preview: 5,
      complete: (result) => {
        const fields = result.meta.fields ?? [];
        setHeaders(fields);
        setPreview(result.data);
        setMapping(guessMapping(fields));
      },
      error: (err) => setError(`Could not read the file: ${err.message}`),
    });
  };

  const missing = useMemo(
    () => (["date", "open", "high", "low", "close"] as Field[]).filter((f) => !mapping[f]),
    [mapping]
  );

  const toRow = (raw: Record<string, string>): CandleRow => ({
    time: mapping.time ? `${raw[mapping.date]} ${raw[mapping.time]}` : raw[mapping.date],
    open: raw[mapping.open],
    high: raw[mapping.high],
    low: raw[mapping.low],
    close: raw[mapping.close],
    volume: mapping.volume ? raw[mapping.volume] : 0,
  });

  const startUpload = async () => {
    if (!file || !symbol.trim()) {
      return;
    }
    setUploading(true);
    setError(null);
    setProgress(0);

    try {
      const dataset = await createDataset(symbol.trim().toUpperCase(), timezone);
      let chunkIndex = 0;
      let batch: CandleRow[] = [];
      let sent = 0;

      const send = async (rows: CandleRow[]) => {
        const index = chunkIndex++;
        await withRetry(() => uploadChunk(dataset.backtest_dataset_id, index, rows));
        sent += rows.length;
        setStatus(`Sent ${sent.toLocaleString()} rows...`);
      };

      await new Promise<void>((resolve, reject) => {
        Papa.parse<Record<string, string>>(file, {
          header: true,
          skipEmptyLines: true,
          step: (result, parser) => {
            batch.push(toRow(result.data));
            if (batch.length >= CHUNK_ROWS) {
              const rows = batch;
              batch = [];
              parser.pause();
              setProgress(Math.min(99, (result.meta.cursor / file.size) * 100));
              send(rows)
                .then(() => parser.resume())
                .catch((err) => {
                  parser.abort();
                  reject(err);
                });
            }
          },
          complete: () => {
            const rows = batch;
            batch = [];
            (rows.length ? send(rows) : Promise.resolve()).then(() => resolve(), reject);
          },
          error: (err) => reject(err),
        });
      });

      setStatus("Building 15-minute, hourly and daily bars...");
      const result = await completeDataset(dataset.backtest_dataset_id);
      setProgress(100);

      if (result.status === "READY") {
        setStatus(`${result.symbol} ready: ${result.message}`);
        onUploaded(result);
      } else {
        setError(result.message ?? "Upload failed");
        setStatus(null);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? err?.message ?? "Upload failed");
      setStatus(null);
    } finally {
      setUploading(false);
    }
  };

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="h6" sx={{ fontWeight: 700, mb: 1 }}>
          Upload candle data (CSV)
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          The file is read in your browser; only the price rows are sent. The
          file itself is never stored. Use 1, 5 or 15-minute bars: daily data
          can't drive the 15-minute strategy.
        </Typography>

        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mb: 2 }}>
          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            hidden
            onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
          />
          <Button
            variant="outlined"
            startIcon={<UploadFileIcon />}
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
          >
            {file ? file.name : "Choose CSV file"}
          </Button>
          <TextField
            label="Symbol"
            size="small"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            helperText="Indian stocks: add .NS, e.g. RELIANCE.NS"
            disabled={uploading}
          />
          <TextField
            select
            label="Timezone of times in file"
            size="small"
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            helperText="Ignored when times include an offset"
            disabled={uploading}
            sx={{ minWidth: 240 }}
          >
            {TIMEZONES.map((tz) => (
              <MenuItem key={tz.value} value={tz.value}>
                {tz.label}
              </MenuItem>
            ))}
          </TextField>
        </Stack>

        {headers.length > 0 && (
          <>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              Columns (detected automatically, change if wrong)
            </Typography>
            <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", gap: 1, mb: 2 }}>
              {(Object.keys(GUESSES) as Field[]).map((field) => (
                <TextField
                  key={field}
                  select
                  size="small"
                  label={field === "date" ? "date / datetime" : field}
                  value={mapping[field]}
                  onChange={(e) => setMapping({ ...mapping, [field]: e.target.value })}
                  disabled={uploading}
                  sx={{ minWidth: 130 }}
                >
                  <MenuItem value={NONE}>
                    <em>none</em>
                  </MenuItem>
                  {headers.map((h) => (
                    <MenuItem key={h} value={h}>
                      {h}
                    </MenuItem>
                  ))}
                </TextField>
              ))}
            </Stack>

            <Box sx={{ overflowX: "auto", mb: 2 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    {headers.map((h) => (
                      <TableCell key={h}>{h}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {preview.map((row, i) => (
                    <TableRow key={i}>
                      {headers.map((h) => (
                        <TableCell key={h}>{row[h]}</TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          </>
        )}

        {missing.length > 0 && headers.length > 0 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Pick a column for: {missing.join(", ")}
          </Alert>
        )}

        {uploading && <LinearProgress variant="determinate" value={progress} sx={{ mb: 1 }} />}
        {status && (
          <Alert severity={uploading ? "info" : "success"} sx={{ mb: 2 }}>
            {status}
          </Alert>
        )}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Button
          variant="contained"
          onClick={startUpload}
          disabled={!file || !symbol.trim() || missing.length > 0 || uploading}
        >
          {uploading ? "Uploading..." : "Upload"}
        </Button>
      </CardContent>
    </Card>
  );
}

export default CsvUploadCard;
