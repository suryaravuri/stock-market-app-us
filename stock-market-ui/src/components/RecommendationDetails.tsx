import {
  Box,
  Chip,
  Divider,
  Drawer,
  List,
  ListItem,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";

import type { RecommendationStock } from "../types/recommendation";

interface RecommendationDetailsProps {
  stock: RecommendationStock | null;
  open: boolean;
  onClose: () => void;
}

function value(value: number | null, decimals = 2) {
  return value == null ? "-" : value.toFixed(decimals);
}

function RecommendationDetails({
  stock,
  open,
  onClose,
}: RecommendationDetailsProps) {
  if (!stock) {
    return null;
  }

  return (
    <Drawer anchor="right" open={open} onClose={onClose}>
      <Box sx={{ width: { xs: 340, sm: 500 }, p: 3 }}>
        <Stack
        direction="row"
        sx={{
            justifyContent: "space-between",
            alignItems: "center",
            mb: 2,
        }}
        >
          <Box>
           <Typography variant="h4" sx={{ fontWeight: 700 }}>
              {stock.symbol}
            </Typography>

            <Typography color="text.secondary">
              {stock.company_name}
            </Typography>
          </Box>

          <Chip
            label={stock.overall_classification ?? "UNKNOWN"}
            color={
              stock.overall_classification === "STRONG"
                ? "success"
                : stock.overall_classification === "WATCH"
                ? "warning"
                : stock.overall_classification === "AVOID"
                ? "error"
                : "default"
            }
          />
        </Stack>

        <Divider sx={{ my: 2 }} />

        <Typography variant="h6" gutterBottom>
          Recommendation
        </Typography>

        <Stack spacing={1}>
          <Detail label="Current Price" data={`$${value(stock.current_price)}`} />
          <Detail label="Score" data={String(stock.overall_score ?? "-")} />
          <Detail label="Action" data={stock.action} />
          <Detail
            label="Actionable"
            data={stock.actionable ? "YES" : "NO"}
          />
        </Stack>

        <Divider sx={{ my: 2 }} />

        <Typography variant="h6" gutterBottom>
          Risk / Reward
        </Typography>

        <Stack spacing={1}>
          <Detail
            label="RR Quality"
            data={stock.risk_reward_quality ?? "-"}
          />
          <Detail label="RR1" data={value(stock.rr_1)} />
          <Detail label="RR2" data={value(stock.rr_2)} />
          <Detail label="Entry" data={value(stock.entry)} />
          <Detail label="Stop Loss" data={value(stock.stop_loss)} />
          <Detail label="Target 1" data={value(stock.target_1)} />
          <Detail label="Target 2" data={value(stock.target_2)} />
        </Stack>

        <Divider sx={{ my: 2 }} />

        <Typography variant="h6">
          Decision Reasons
        </Typography>

        {stock.decision_reasons.length === 0 ? (
          <Typography color="text.secondary" sx={{ mt: 1 }}>
            No decision reasons available.
          </Typography>
        ) : (
          <List>
            {stock.decision_reasons.map((reason, index) => (
              <ListItem key={index} disableGutters>
                <ListItemText
                  primary={`${index + 1}. ${reason}`}
                />
              </ListItem>
            ))}
          </List>
        )}

        {stock.error && (
          <>
            <Divider sx={{ my: 2 }} />

           <Typography variant="h4" sx={{ fontWeight: 700 }}>
              Analysis Error
            </Typography>

            <Typography color="error">
              {stock.error}
            </Typography>
          </>
        )}
      </Box>
    </Drawer>
  );
}

interface DetailProps {
  label: string;
  data: string;
}

function Detail({ label, data }: DetailProps) {
  return (
    <Stack
  direction="row"
  sx={{
    justifyContent: "space-between",
    alignItems: "center",
    mb: 2,
  }}
>
      <Typography color="text.secondary">{label}</Typography>

      <Typography sx={{ fontWeight: 600, textAlign: "right" }}>
        {data}
      </Typography>
    </Stack>
  );
}

export default RecommendationDetails;