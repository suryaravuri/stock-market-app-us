from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.validation_market_data import (
    ValidationMarketDataSymbolResult,
)


class MonitorStatusResponse(BaseModel):
    watchlist_id: int
    watchlist_name: str
    timeframe: str

    execution_mode: str
    data_status: str

    symbols_checked: int
    symbols_passed: int
    symbols_degraded: int
    symbols_failed: int

    eligible_for_signal_analysis: int
    blocked_stocks: int

    expected_latest_completed_candle: datetime | None = None
    latest_available_candle: datetime | None = None

    session_timezone: str
    evaluated_at: datetime

    broker_order_submitted: bool = False
    database_mutated: bool = False
    production_position_tables_mutated: bool = False

    results: list[ValidationMarketDataSymbolResult]