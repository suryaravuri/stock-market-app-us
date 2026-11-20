import {
  AppBar,
  Box,
  Button,
  Container,
  Stack,
  Toolbar,
  Typography,
} from "@mui/material";

import DashboardIcon from "@mui/icons-material/Dashboard";
import PlaylistAddCheckIcon from "@mui/icons-material/PlaylistAddCheck";
import AnalyticsIcon from "@mui/icons-material/Analytics";
import SensorsIcon from "@mui/icons-material/Sensors";
import ShieldIcon from "@mui/icons-material/Shield";
import StorageIcon from "@mui/icons-material/Storage";
import AssessmentIcon from "@mui/icons-material/Assessment";
import LogoutIcon from "@mui/icons-material/Logout";
import LockResetIcon from "@mui/icons-material/LockReset";
import ShowChartIcon from "@mui/icons-material/ShowChart";
import ScienceIcon from "@mui/icons-material/Science";
import CandlestickChartIcon from "@mui/icons-material/CandlestickChart";
import TimelineIcon from "@mui/icons-material/Timeline";

import {
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import PersonAddAlt1Icon from "@mui/icons-material/PersonAddAlt1";
import Inventory2OutlinedIcon from "@mui/icons-material/Inventory2Outlined";
import GridViewIcon from "@mui/icons-material/GridView";
import AccountBalanceWalletIcon from "@mui/icons-material/AccountBalanceWallet";

const navigationItems = [
  {
    label: "Dashboard",
    path: "/",
    icon: <DashboardIcon fontSize="small" />,
  },
  {
    label: "Watchlist",
    path: "/watchlist",
    icon: <PlaylistAddCheckIcon fontSize="small" />,
  },
  {
    label: "Stock Analysis",
    path: "/analysis",
    icon: <AnalyticsIcon fontSize="small" />,
  },
  {
    label: "Signals",
    path: "/signals",
    icon: <SensorsIcon fontSize="small" />,
  },
  {
    label: "Risk & Positions",
    path: "/risk",
    icon: <ShieldIcon fontSize="small" />,
  },
  {
    label: "Market Data",
    path: "/market-data",
    icon: <StorageIcon fontSize="small" />,
  },
  {
    label: "Validation",
    path: "/validation",
    icon: <AssessmentIcon fontSize="small" />,
  },
  { label: "Options", path: "/options", icon: <ShowChartIcon fontSize="small" /> },
  { label: "Futures", path: "/futures", icon: <ShowChartIcon fontSize="small" /> },
  {
    label: "Trades & P&L",
    path: "/trades",
    icon: <ShowChartIcon fontSize="small" />,
  },
  {
  label: "Sector Heatmap",
  path: "/heatmap",
  icon: <GridViewIcon fontSize="small" />,
  },
  {
    label: "US Paper P&L",
    path: "/paper-pnl",
    icon: <AccountBalanceWalletIcon fontSize="small" />,
  },
  {
    label: "Backtests",
    path: "/backtests",
    icon: <ScienceIcon fontSize="small" />,
  },
];

function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "#fafafa",
      }}
    >
      <AppBar
        position="sticky"
        elevation={1}
        sx={{
          bgcolor: "#ffffff",
          color: "text.primary",
        }}
      >
        <Container maxWidth="xl">
          {/* Application title */}
          <Toolbar
            disableGutters
            sx={{
              minHeight: "52px !important",
            }}
          >
            <Typography
              variant="h6"
              sx={{
                fontWeight: 700,
                whiteSpace: "nowrap",
              }}
            >
              Stock Decision Engine
            </Typography>

            <Box sx={{ flexGrow: 1 }} />

              <Stack
                  direction="row"
                  spacing={1}
                  sx={{ alignItems: "center" }}
                >
              <Typography variant="body2" color="text.secondary" sx={{ display: { xs: "none", md: "block" } }}>
                {user?.full_name || user?.email}
              </Typography>
              <Button size="small" startIcon={<LockResetIcon />} onClick={() => navigate("/change-password")}>
                Change Password
              </Button>
              <Button size="small" startIcon={<LogoutIcon />} onClick={handleLogout}>
                Logout
              </Button>
            </Stack>
          </Toolbar>

          {/* Navigation */}
          <Box
            sx={{
              borderTop: 1,
              borderColor: "divider",
            }}
          >
            <Stack
              direction="row"
              spacing={0.5}
              sx={{
                alignItems: "center",
                flexWrap: "wrap",
              }}
            >

              {navigationItems.map((item) => {
                  const selected =
                    item.path === "/"
                      ? location.pathname === "/"
                      : location.pathname.startsWith(item.path);

                  return (
                    <Button
                      key={item.path}
                      startIcon={item.icon}
                      onClick={() => navigate(item.path)}
                      sx={{
                        px: 1.5,
                        py: 1.25,
                        minWidth: "auto",
                        whiteSpace: "nowrap",
                        color: selected
                          ? "primary.main"
                          : "text.secondary",
                        fontWeight: selected ? 700 : 500,
                        fontSize: "0.78rem",
                        borderBottom: selected
                          ? "3px solid"
                          : "3px solid transparent",
                        borderRadius: 0,
                        "& .MuiButton-startIcon": {
                          mr: 0.6,
                        },
                      }}
                    >
                      {item.label}
                    </Button>
                  );
                })}

                  {user?.role === "ADMIN" && (
                      <>
                        <Button
                          startIcon={
                            <Inventory2OutlinedIcon fontSize="small" />
                          }
                          onClick={() => navigate("/stock-master")}
                          sx={{
                            px: 1.5,
                            py: 1.25,
                            minWidth: "auto",
                            whiteSpace: "nowrap",
                            color: location.pathname.startsWith("/stock-master")
                              ? "primary.main"
                              : "text.secondary",
                            fontWeight: location.pathname.startsWith("/stock-master")
                              ? 700
                              : 500,
                            fontSize: "0.78rem",
                            borderBottom: location.pathname.startsWith("/stock-master")
                              ? "3px solid"
                              : "3px solid transparent",
                            borderRadius: 0,
                            "& .MuiButton-startIcon": {
                              mr: 0.6,
                            },
                          }}
                        >
                          Stock Master
                        </Button>

                        <Button
                          startIcon={
                            <PersonAddAlt1Icon fontSize="small" />
                          }
                    onClick={() => navigate("/user-enrollment")}
                    sx={{
                      px: 1.5,
                      py: 1.25,
                      minWidth: "auto",
                      whiteSpace: "nowrap",
                      color: location.pathname.startsWith("/user-enrollment")
                        ? "primary.main"
                        : "text.secondary",
                      fontWeight: location.pathname.startsWith("/user-enrollment")
                        ? 700
                        : 500,
                      fontSize: "0.78rem",
                      borderBottom: location.pathname.startsWith("/user-enrollment")
                        ? "3px solid"
                        : "3px solid transparent",
                      borderRadius: 0,
                      "& .MuiButton-startIcon": {
                        mr: 0.6,
                      },
                    }}
                  >
                    User Enrollment
                  </Button>
                </>
              )}

            </Stack>
          </Box>
        </Container>
      </AppBar>

      <Container
        maxWidth="xl"
        sx={{
          px: {
            xs: 1,
            sm: 2,
            md: 3,
          },
        }}
      >
        <Outlet />
      </Container>
    </Box>
  );
}

export default AppLayout;