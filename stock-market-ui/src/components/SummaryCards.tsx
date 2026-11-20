import {
  Card,
  CardContent,
  Grid,
  Typography,
} from "@mui/material";

interface SummaryCardsProps {
  totalStocks: number;
  actionableCount: number;
  strongCount: number;
  watchCount: number;
  avoidCount: number;
}

function SummaryCards({
  totalStocks,
  actionableCount,
  strongCount,
  watchCount,
  avoidCount,
}: SummaryCardsProps) {
  const cards = [
    { label: "Stocks Monitored", value: totalStocks },
    { label: "Actionable", value: actionableCount },
    { label: "Strong", value: strongCount },
    { label: "Watch", value: watchCount },
    { label: "Avoid", value: avoidCount },
  ];

  return (
    <Grid container spacing={2}>
      {cards.map((card) => (
        <Grid key={card.label} size={{ xs: 12, sm: 6, md: 2.4 }}>
          <Card variant="outlined">
            <CardContent>
              <Typography
                variant="body2"
                color="text.secondary"
                gutterBottom
              >
                {card.label}
              </Typography>

              <Typography variant="h4" sx={{ fontWeight: 700 }}>
                {card.value}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      ))}
    </Grid>
  );
}

export default SummaryCards;