from datetime import datetime, timezone
from types import SimpleNamespace

from app.schemas.market import MarketTimeframe
from app.services.position_pnl_analytics_service import PositionPnLAnalyticsService


def dt(hour, minute):
    return datetime(2026, 8, 28, hour, minute, tzinfo=timezone.utc)


def candle(t, high, low, close):
    return SimpleNamespace(candle_time=t, high_price=high, low_price=low, close_price=close)


def test_open_position_calculates_unrealized_mfe_mae(monkeypatch):
    stock = SimpleNamespace(stock_id=6)
    record = SimpleNamespace(
        timeframe="15Min", state="POSITION_OPEN", entry_price=100, initial_risk_per_share=2,
        opened_at=dt(13, 30), last_evaluated_candle_time=dt(14, 15), exit_price=None,
        exit_reason=None, closed_at=None,
    )
    rows = [
        candle(dt(13, 30), 101, 99, 100),
        candle(dt(13, 45), 103, 99.5, 102),
        candle(dt(14, 0), 104, 98.5, 103),
        candle(dt(14, 15), 103.5, 100, 102.5),
    ]
    monkeypatch.setattr("app.services.position_pnl_analytics_service.StockRepository.find_by_symbol", lambda db, s: stock)
    monkeypatch.setattr("app.services.position_pnl_analytics_service.PositionStateRepository.find_latest", lambda db, sid, tf: record)
    monkeypatch.setattr("app.services.position_pnl_analytics_service.MarketCandleRepository.find_by_range", lambda *a: rows)
    monkeypatch.setattr("app.services.position_pnl_analytics_service.MarketCandleRepository.find_latest", lambda *a: rows[-1])
    monkeypatch.setattr("app.services.position_pnl_analytics_service.is_regular_session_candle", lambda t, session=None: True)

    result = PositionPnLAnalyticsService.for_persistent_position(None, "PLTR", MarketTimeframe.FIFTEEN_MINUTES)
    assert result["analytics_status"] == "OPEN"
    assert result["analytics_candle_source"] == "MARKET_CANDLE"
    assert result["source_data_status"] == "AVAILABLE"
    assert result["unrealized_per_share"] == 2.5
    assert result["unrealized_r"] == 1.25
    assert result["mfe_per_share"] == 4
    assert result["mfe_r"] == 2
    assert result["mae_per_share"] == -1.5
    assert result["mae_r"] == -0.75
    assert result["candles_analyzed"] == 3
    assert result["holding_minutes"] == 45


def test_closed_synthetic_position_uses_persisted_synthetic_observations(monkeypatch):
    record = SimpleNamespace(
        stock_id=6, symbol="PLTR", timeframe="15Min", state="STOP_HIT", entry_price=100,
        initial_risk_per_share=2, opened_at=dt(13, 30), last_evaluated_candle_time=dt(14, 15),
        exit_price=102.5, exit_reason="TRAILING_STOP", closed_at=dt(14, 15),
        analytics_candle_source="SYNTHETIC_PERSISTED_CANDLES",
    )
    rows = [candle(dt(13, 45), 104, 99, 103), candle(dt(14, 15), 105, 102.4, 102.7)]
    monkeypatch.setattr("app.services.position_pnl_analytics_service.PositionTestStateRepository.find", lambda db, rid: record)
    monkeypatch.setattr("app.services.position_pnl_analytics_service.PositionTestStateRepository.observations", lambda db, rid: rows)

    result = PositionPnLAnalyticsService.for_test_run(None, "PLTR", "run-1")
    assert result["analytics_status"] == "CLOSED"
    assert result["analytics_candle_source"] == "SYNTHETIC_PERSISTED_CANDLES"
    assert result["source_data_status"] == "AVAILABLE"
    assert result["current_price"] == 102.7
    assert result["realized_per_share"] == 2.5
    assert result["realized_r"] == 1.25
    assert result["mfe_per_share"] == 5
    assert result["mae_per_share"] == -1
    assert result["giveback_from_mfe_per_share"] == 2.5
    assert result["exit_efficiency_pct"] == 50.0
    assert result["unrealized_per_share"] is None
    assert result["exit_reason"] == "TRAILING_STOP"


def test_old_synthetic_run_suppresses_excursion_metrics(monkeypatch):
    record = SimpleNamespace(
        stock_id=6, symbol="PLTR", timeframe="15Min", state="STOP_HIT", entry_price=100,
        initial_risk_per_share=2, opened_at=dt(13, 45), last_evaluated_candle_time=dt(14, 45),
        exit_price=102.5, exit_reason="TRAILING_STOP", closed_at=dt(14, 45),
        analytics_candle_source="SYNTHETIC_UNRECORDED",
    )
    monkeypatch.setattr("app.services.position_pnl_analytics_service.PositionTestStateRepository.find", lambda db, rid: record)

    result = PositionPnLAnalyticsService.for_test_run(None, "PLTR", "old-run")
    assert result["source_data_status"] == "UNAVAILABLE"
    assert result["realized_per_share"] == 2.5
    assert result["realized_r"] == 1.25
    assert result["mfe_per_share"] is None
    assert result["mae_per_share"] is None
    assert result["exit_efficiency_pct"] is None
    assert "suppressed" in result["summary"]


def test_no_persistent_position_is_safe(monkeypatch):
    stock = SimpleNamespace(stock_id=6)
    monkeypatch.setattr("app.services.position_pnl_analytics_service.StockRepository.find_by_symbol", lambda db, s: stock)
    monkeypatch.setattr("app.services.position_pnl_analytics_service.PositionStateRepository.find_latest", lambda db, sid, tf: None)
    result = PositionPnLAnalyticsService.for_persistent_position(None, "PLTR", MarketTimeframe.FIFTEEN_MINUTES)
    assert result["analytics_status"] == "NO_POSITION"
    assert result["source_data_status"] == "NOT_APPLICABLE"
    assert result["broker_order_submitted"] is False
    assert result["production_position_tables_mutated"] is False
