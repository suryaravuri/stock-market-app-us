import { Box, Chip, Stack, Tab, Tabs, Typography } from "@mui/material";

import { useMarket } from "../context/MarketContext";
import { APP_MARKETS } from "../config/appMarket";
import { MARKETS, type MarketCode, type MarketStatus } from "../types/market";

function formatInMarket(iso: string, market: MarketCode, withDay: boolean): string {
  const info = MARKETS[market];
  return (
    new Date(iso).toLocaleString([], {
      timeZone: info.timezone,
      weekday: withDay ? "short" : undefined,
      hour: "numeric",
      minute: "2-digit",
    }) + ` ${info.tzLabel}`
  );
}

export function marketStatusText(status: MarketStatus | undefined, market: MarketCode): string {
  if (!status) {
    return "";
  }
  if (status.is_open && status.closes_at) {
    const early = status.early_close ? " (early close)" : "";
    return `Open \u00B7 closes ${formatInMarket(status.closes_at, market, false)}${early}`;
  }
  if (status.next_open) {
    const reason = status.is_session_day ? "Closed" : "Closed today";
    return `${reason} \u00B7 opens ${formatInMarket(status.next_open, market, true)}`;
  }
  return "Closed";
}

function MarketTabs() {
  const { market, setMarket, statuses } = useMarket();

  return (
    <Box sx={{ borderBottom: 1, borderColor: "divider", mb: 3 }}>
      <Tabs
        value={market}
        onChange={(_, value: MarketCode) => setMarket(value)}
        aria-label="Market"
      >
        {APP_MARKETS.map((code) => {
          const status = statuses?.[code];
          return (
            <Tab
              key={code}
              value={code}
              sx={{ textTransform: "none", alignItems: "flex-start", py: 1 }}
              label={
                <Stack spacing={0.5} sx={{ alignItems: "flex-start" }}>
                  <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                    <Typography sx={{ fontWeight: 700 }}>
                      {MARKETS[code].flag} {MARKETS[code].label}
                    </Typography>
                    {status && (
                      <Chip
                        size="small"
                        label={status.is_open ? "OPEN" : "CLOSED"}
                        color={status.is_open ? "success" : "default"}
                        variant={status.is_open ? "filled" : "outlined"}
                      />
                    )}
                  </Stack>
                  <Typography variant="caption" color="text.secondary">
                    {marketStatusText(status, code)}
                  </Typography>
                </Stack>
              }
            />
          );
        })}
      </Tabs>
    </Box>
  );
}

export default MarketTabs;
