import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import AppLayout from "./components/AppLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import RecommendationDashboard from "./pages/RecommendationDashboard";
import StockAnalysisPage from "./pages/StockAnalysisPage";
import SignalsPage from "./pages/SignalsPage";
import RiskPositionsPage from "./pages/RiskPositionsPage";
import MarketDataPage from "./pages/MarketDataPage";
import ValidationStatisticsPage from "./pages/ValidationStatisticsPage";
import WatchlistPage from "./pages/WatchlistPage";
import UserEnrollmentPage from "./pages/UserEnrollmentPage";
import { WatchlistProvider } from "./context/WatchlistContext";
import { MarketProvider } from "./context/MarketContext";
import AdminRoute from "./components/AdminRoute";
import StockMasterPage from "./pages/StockMasterPage";
import TradesPnLPage from "./pages/TradesPnLPage";
import BacktestsPage from "./pages/BacktestsPage";
import OptionsPage from "./pages/OptionsPage";
import FuturesPage from "./pages/FuturesPage";
import SectorHeatmapPage from "./pages/SectorHeatmapPage";
import PaperPnlPage from "./pages/PaperPnlPage";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route
            element={
              <ProtectedRoute>
                <WatchlistProvider>
                  <MarketProvider>
                    <AppLayout />
                  </MarketProvider>
                </WatchlistProvider>
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<RecommendationDashboard />} />
            <Route path="/watchlist" element={<WatchlistPage />} />
            <Route path="/analysis" element={<StockAnalysisPage />} />
            <Route path="/signals" element={<SignalsPage />} />
            <Route path="/risk" element={<RiskPositionsPage />} />
            <Route path="/market-data" element={<MarketDataPage />} />
            <Route path="/validation" element={<ValidationStatisticsPage />} />
            <Route path="/trades" element={<TradesPnLPage />} />
            <Route path="/heatmap" element={<SectorHeatmapPage />} />
            <Route path="/paper-pnl" element={<PaperPnlPage />} />
            <Route path="/backtests" element={<BacktestsPage />} />
            <Route path="/options" element={<OptionsPage />} />
            <Route path="/futures" element={<FuturesPage />} />


            <Route
              path="/user-enrollment"
              element={
                <AdminRoute>
                  <UserEnrollmentPage />
                </AdminRoute>
              }
            />

            <Route
              path="/stock-master"
              element={
                <AdminRoute>
                  <StockMasterPage />
                </AdminRoute>
              }
            />

            <Route
              path="/change-password"
              element={<ChangePasswordPage />}
            />

            {/* <Route
              path="/user-enrollment"
              element={
                <AdminRoute>
                  <UserEnrollmentPage />
                </AdminRoute>
              }
            /> */}
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;