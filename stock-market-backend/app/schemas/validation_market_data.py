from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ValidationMarketDataSymbolResult(BaseModel):
    stock_id: int
    symbol: str
    timeframe: str
    status: str
    eligible_for_signal_analysis: bool
    latest_regular_session_candle: datetime | None = None
    expected_latest_completed_candle: datetime | None = None
    freshness_lag_bars: int | None = None
    candles_examined: int
    valid_regular_completed_candles: int
    required_history_candles: int
    indicator_ready: bool
    duplicate_timestamp_count: int
    intraday_gap_count: int
    latest_candle_valid: bool | None = None
    latest_candle_issues: list[str]
    reasons: list[str]


class ValidationMarketDataResponse(BaseModel):
    validation_run_id: int
    strategy_version: str
    validation_phase: str
    execution_mode: str
    baseline_status: str
    watchlist_id: int
    watchlist_name: str
    timeframe: str
    validation_status: str
    symbols_checked: int
    symbols_passed: int
    symbols_degraded: int
    symbols_failed: int
    eligible_for_signal_analysis: int
    session_timezone: str
    evaluated_at: datetime
    results: list[ValidationMarketDataSymbolResult]
    broker_order_submitted: bool = False
    database_mutated: bool = False
    production_position_tables_mutated: bool = False
