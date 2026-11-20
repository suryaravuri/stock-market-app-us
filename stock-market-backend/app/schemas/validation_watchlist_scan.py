from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class ValidationWatchlistScanStock(BaseModel):
    stock_id: int
    symbol: str
    company_name: str | None = None
    exchange: str | None = None
    priority: int

    market_data_status: str
    eligible_for_signal_analysis: bool
    scan_status: str

    current_price: float | None = None
    overall_score: int | None = None
    overall_classification: str | None = None
    risk_reward_quality: str | None = None
    rr_1: float | None = None
    rr_2: float | None = None
    entry: float | None = None
    stop_loss: float | None = None
    target_1: float | None = None
    target_2: float | None = None

    action: str
    actionable: bool
    decision_reasons: list[str]

    breakout_status: str | None = None
    breakout_confirmed: bool = False
    signal_state: str | None = None
    signal_previous_state: str | None = None
    signal_event: str | None = None
    signal_state_changed: bool = False
    signal_cycle_number: int | None = None
    signal_candle_time: datetime | None = None

    # #16C-1 completed-candle enforcement diagnostics.
    # These fields are intentionally part of the response model so FastAPI
    # does not strip the service-level guard evidence during serialization.
    analysis_as_of: datetime | None = None
    latest_stored_candle: datetime | None = None
    completed_candle_enforcement: bool = False
    used_incomplete_candle: bool = False

    position_state: str | None = None
    position_opening_gate_passed: bool = False
    position_database_mutated: bool = False

    # Auto paper execution outcome (reason explains why no order was sent).
    paper_execution: dict | None = None
    support_bounce: dict | None = None
    # outcome / blocker / would_buy_if_enabled (see services/decision_log.py)
    decision: dict | None = None

    error: str | None = None


class ValidationWatchlistScanResponse(BaseModel):
    validation_run_id: int
    strategy_version: str
    validation_phase: str
    execution_mode: str
    baseline_status: str
    watchlist_id: int
    watchlist_name: str
    timeframe: str

    scan_status: str
    symbols_checked: int
    symbols_eligible: int
    symbols_scanned: int
    symbols_blocked_by_data_quality: int
    symbols_failed_analysis: int
    actionable_count: int
    entry_confirmed_count: int

    evaluated_at: datetime
    stocks: list[ValidationWatchlistScanStock]

    signal_state_mutations: int
    position_state_mutations: int
    database_mutated: bool
    production_position_tables_mutated: bool
    paper_execution_enabled: bool = False
    paper_execution_attempts: int = 0
    paper_orders_submitted: int = 0
    broker_order_submitted: bool = False
