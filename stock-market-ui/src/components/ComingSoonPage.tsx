import { Box, Paper, Typography } from "@mui/material";

interface ComingSoonPageProps {
  title: string;
  description: string;
}

function ComingSoonPage({
  title,
  description,
}: ComingSoonPageProps) {
  return (
    <Box sx={{ p: 4 }}>
      <Paper
        variant="outlined"
        sx={{
          p: 4,
          minHeight: 250,
        }}
      >
        <Typography
          variant="h4"
          sx={{ fontWeight: 700, mb: 1 }}
        >
          {title}
        </Typography>

        <Typography color="text.secondary">
          {description}
        </Typography>
      </Paper>
    </Box>
  );
}

export default ComingSoonPage;