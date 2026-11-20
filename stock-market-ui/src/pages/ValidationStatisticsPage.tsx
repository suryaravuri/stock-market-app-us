import { useEffect, useState } from "react";
import RefreshIcon from "@mui/icons-material/Refresh";

import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Typography,
} from "@mui/material";

import {
  getActiveValidationRun,
  getValidationProgress,
} from "../services/validationService";

import type {
  ActiveValidationRun,
  ValidationProgress,
} from "../types/validation";

function statusColor(
  status: string
): "success" | "warning" | "error" | "info" | "default" {
  switch (status) {
    case "MATCH":
      return "success";

    case "ACTIVE":
      return "info";

    case "COMPLETED":
      return "success";

    case "MISMATCH":
    case "FAILED":
      return "error";

    default:
      return "default";
  }
}

function yesNo(value: boolean) {
  return value ? "YES" : "NO";
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "-";
  }

  return new Date(value).toLocaleString();
}

function ValidationStatisticsPage() {
  const [run, setRun] =
    useState<ActiveValidationRun | null>(null);

  const [progress, setProgress] =
    useState<ValidationProgress | null>(null);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadValidation = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setError(null);

      const activeRun = await getActiveValidationRun();

      const progressResponse =
        await getValidationProgress(
          activeRun.validation_run_id
        );

      setRun(activeRun);
      setProgress(progressResponse);
    } catch (err) {
      console.error(err);
      setError("Unable to load validation statistics");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadValidation();
  }, []);

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
          <Typography>
            Loading validation statistics...
          </Typography>
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

  if (!run || !progress) {
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
            Validation & Statistics
          </Typography>

          <Typography color="text.secondary">
            Strategy validation progress and analytical performance
          </Typography>
        </Box>

        <Stack
          direction="row"
          spacing={2}
          sx={{ alignItems: "center" }}
        >
          <Chip
            label={`RUN ${run.validation_run_id}: ${run.status}`}
            color={statusColor(run.status)}
          />

          <Chip
            label={`BASELINE: ${run.baseline_status}`}
            color={statusColor(
              run.baseline_status
            )}
          />

          <Button
            variant="contained"
            startIcon={<RefreshIcon />}
            disabled={refreshing}
            onClick={() => loadValidation(true)}
          >
            {refreshing
              ? "Refreshing..."
              : "Refresh"}
          </Button>
        </Stack>
      </Stack>

      {run.baseline_status !== "MATCH" && (
        <Alert severity="error" sx={{ mb: 3 }}>
          <Typography sx={{ fontWeight: 700 }}>
            Validation Baseline Mismatch
          </Typography>

          <Typography variant="body2">
            {run.baseline_note ??
              "The running strategy no longer matches the validation baseline."}
          </Typography>
        </Alert>
      )}

      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={2}
        sx={{ mb: 3 }}
      >
        <StatCard
          label="Signals Observed"
          value={progress.signals_observed}
        />

        <StatCard
          label="Breakouts"
          value={progress.breakouts_detected}
        />

        <StatCard
          label="Follow Through"
          value={progress.follow_through_confirmed}
        />

        <StatCard
          label="Entries"
          value={progress.entries_confirmed}
        />
      </Stack>

      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={2}
        sx={{ mb: 3 }}
      >
        <StatCard
          label="Positions Opened"
          value={progress.positions_opened}
        />

        <StatCard
          label="Positions Closed"
          value={progress.positions_closed}
        />

        <StatCard
          label="Wins"
          value={progress.wins}
        />

        <StatCard
          label="Losses"
          value={progress.losses}
        />

        <StatCard
          label="Breakeven"
          value={progress.breakeven}
        />
      </Stack>

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
            Validation Run
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="Run ID"
              value={String(
                run.validation_run_id
              )}
            />

            <Metric
              label="Strategy"
              value={run.strategy_version}
            />

            <Metric
              label="Phase"
              value={run.validation_phase}
            />

            <Metric
              label="Status"
              value={run.status}
            />

            <Metric
              label="Baseline"
              value={run.baseline_status}
            />

            <Metric
              label="Started"
              value={formatDateTime(
                run.started_at
              )}
            />

            <Metric
              label="Completed"
              value={formatDateTime(
                run.completed_at
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
            Signal Funnel
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="Signals Observed"
              value={String(
                progress.signals_observed
              )}
            />

            <Metric
              label="Breakouts Detected"
              value={String(
                progress.breakouts_detected
              )}
            />

            <Metric
              label="Follow Through Confirmed"
              value={String(
                progress.follow_through_confirmed
              )}
            />

            <Metric
              label="Entries Confirmed"
              value={String(
                progress.entries_confirmed
              )}
            />

            <Metric
              label="Positions Opened"
              value={String(
                progress.positions_opened
              )}
            />

            <Metric
              label="Positions Closed"
              value={String(
                progress.positions_closed
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
            Safety & Isolation
          </Typography>

          <Stack spacing={1.2}>
            <Metric
              label="Execution Mode"
              value={progress.execution_mode}
            />

            <Metric
              label="Baseline"
              value={progress.baseline_status}
            />

            <Metric
              label="Test Positions Included"
              value={yesNo(
                progress.isolated_test_positions_included
              )}
            />

            <Metric
              label="Broker Order Submitted"
              value={yesNo(
                progress.broker_order_submitted
              )}
            />
          </Stack>

          <Alert severity="info" sx={{ mt: 3 }}>
            Validation remains analysis-only and isolated from broker execution.
          </Alert>
        </Paper>
      </Stack>

      <Paper
        variant="outlined"
        sx={{ p: 3, mt: 3 }}
      >
        <Typography
          variant="h6"
          sx={{ fontWeight: 700, mb: 2 }}
        >
          Outcome Statistics
        </Typography>

        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={4}
        >
          <Metric
            label="Wins"
            value={String(progress.wins)}
          />

          <Metric
            label="Losses"
            value={String(progress.losses)}
          />

          <Metric
            label="Breakeven"
            value={String(
              progress.breakeven
            )}
          />
        </Stack>

        {progress.positions_closed === 0 && (
          <Alert severity="warning" sx={{ mt: 3 }}>
            No analytical positions have closed yet, so win rate and realized performance are not available.
          </Alert>
        )}
      </Paper>
    </Box>
  );
}

interface StatCardProps {
  label: string;
  value: number;
}

function StatCard({
  label,
  value,
}: StatCardProps) {
  return (
    <Card
      variant="outlined"
      sx={{ flex: 1 }}
    >
      <CardContent>
        <Typography
          color="text.secondary"
          sx={{ textAlign: "center" }}
        >
          {label}
        </Typography>

        <Typography
          variant="h4"
          sx={{
            fontWeight: 700,
            textAlign: "center",
            mt: 1,
          }}
        >
          {value}
        </Typography>
      </CardContent>
    </Card>
  );
}

interface MetricProps {
  label: string;
  value: string;
}

function Metric({
  label,
  value,
}: MetricProps) {
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

      <Typography
        sx={{
          fontWeight: 600,
          textAlign: "right",
        }}
      >
        {value}
      </Typography>
    </Stack>
  );
}

export default ValidationStatisticsPage;