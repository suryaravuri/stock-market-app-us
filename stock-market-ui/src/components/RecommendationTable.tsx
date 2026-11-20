import { useState } from "react";
import {
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";

import type { RecommendationStock } from "../types/recommendation";
import RecommendationDetails from "./RecommendationDetails";

interface RecommendationTableProps {
  stocks: RecommendationStock[];
}

function getClassificationColor(
  classification: string | null
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

function getActionColor(
  action: string
): "success" | "warning" | "error" | "info" | "default" {
  switch (action) {
    case "ENTRY_CONFIRMED":
      return "success";

    case "WAIT_FOR_BREAKOUT":
    case "WAIT_FOR_PULLBACK":
      return "warning";

    case "AVOID":
    case "SIGNAL_EXPIRED":
      return "error";

    default:
      return "info";
  }
}

function formatNumber(
  value: number | null,
  decimals = 2
): string {
  if (value === null || value === undefined) {
    return "-";
  }

  return value.toFixed(decimals);
}

// NSE/BSE symbols carry a .NS/.BO suffix and are priced in rupees.
function currencySymbol(symbol: string): string {
  return /\.(NS|BO)$/i.test(symbol) ? "\u20B9" : "$";
}

function RecommendationTable({
  stocks,
}: RecommendationTableProps) {
  const [selectedStock, setSelectedStock] =
    useState<RecommendationStock | null>(null);

  const handleRowClick = (stock: RecommendationStock) => {
    setSelectedStock(stock);
  };

  const handleClose = () => {
    setSelectedStock(null);
  };

  return (
    <>
      <TableContainer component={Paper} sx={{ mt: 3 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell><strong>Symbol</strong></TableCell>
              <TableCell align="right"><strong>Price</strong></TableCell>
              <TableCell align="right"><strong>Score</strong></TableCell>
              <TableCell><strong>Classification</strong></TableCell>
              <TableCell><strong>Recommendation</strong></TableCell>
              <TableCell><strong>RR Quality</strong></TableCell>
              <TableCell align="right"><strong>RR1</strong></TableCell>
              <TableCell align="right"><strong>RR2</strong></TableCell>
              <TableCell><strong>Actionable</strong></TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {stocks.map((stock) => (
              <TableRow
                key={stock.stock_id}
                hover
                onClick={() => handleRowClick(stock)}
                sx={{
                  cursor: "pointer",
                  "&:hover": {
                    backgroundColor: "action.hover",
                  },
                }}
              >
                <TableCell>
                  <Typography variant="h4" sx={{ fontWeight: 700 }}>
                    {stock.symbol}
                  </Typography>
                </TableCell>

                <TableCell align="right">
                  {currencySymbol(stock.symbol)}
                  {formatNumber(stock.current_price)}
                </TableCell>

                <TableCell align="right">
                  {stock.overall_score ?? "-"}
                </TableCell>

                <TableCell>
                  <Chip
                    label={stock.overall_classification ?? "UNKNOWN"}
                    color={getClassificationColor(
                      stock.overall_classification
                    )}
                    size="small"
                  />
                </TableCell>

                <TableCell>
                  <Chip
                    label={stock.action}
                    color={getActionColor(stock.action)}
                    size="small"
                    variant="outlined"
                  />
                </TableCell>

                <TableCell>
                  {stock.risk_reward_quality ?? "-"}
                </TableCell>

                <TableCell align="right">
                  {formatNumber(stock.rr_1)}
                </TableCell>

                <TableCell align="right">
                  {formatNumber(stock.rr_2)}
                </TableCell>

                <TableCell>
                  <Chip
                    label={stock.actionable ? "YES" : "NO"}
                    color={stock.actionable ? "success" : "default"}
                    size="small"
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <RecommendationDetails
        stock={selectedStock}
        open={selectedStock !== null}
        onClose={handleClose}
      />
    </>
  );
}

export default RecommendationTable;