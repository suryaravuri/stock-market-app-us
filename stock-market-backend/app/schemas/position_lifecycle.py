from datetime import datetime
from pydantic import BaseModel


class PositionLifecycleResponse(BaseModel):
    symbol: str
    timeframe: str
    execution_mode: str
    persistence_mode: str = "PERSISTENT_ANALYTICAL"
    broker_order_submitted: bool
    database_mutated: bool = False
    opening_gate_passed: bool = False
    opening_gate_reason: str | None = None
    processed_candles: int = 0
    ignored_out_of_session_candles: int = 0
    ignored_incomplete_candles: int = 0
    monitoring_mode: str | None = None
    monitoring_trigger: str | None = None
    monitoring_status: str | None = None
    new_candles_found: int = 0
    duplicate_candles_skipped: int = 0
    state: str
    previous_state: str | None = None
    last_event: str
    state_changed: bool
    reason: str
    signal_cycle_number: int
    entry_price: float | None = None
    quantity: int = 0
    initial_stop: float | None = None
    active_stop: float | None = None
    target_1: float | None = None
    target_2: float | None = None
    initial_risk_per_share: float | None = None
    target_1_hit: bool = False
    target_2_hit: bool = False
    opened_at: datetime | None = None
    last_evaluated_candle_time: datetime | None = None
    current_price: float | None = None
    unrealized_per_share: float | None = None
    unrealized_r: float | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    closed_at: datetime | None = None
    version: int | None = None


class PositionLifecycleHistoryItem(BaseModel):
    from_state: str | None
    to_state: str
    event: str
    reason: str
    candle_time: datetime | None
    observed_price: float | None
    active_stop: float | None
    signal_cycle_number: int
    created_at: datetime


class PositionLifecycleHistoryResponse(BaseModel):
    symbol: str
    timeframe: str
    execution_mode: str = "ANALYSIS_ONLY"
    persistence_mode: str = "PERSISTENT_ANALYTICAL"
    broker_order_submitted: bool = False
    transitions: list[PositionLifecycleHistoryItem]


class PositionSimulationCandle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float


class PositionLifecycleSimulationRequest(BaseModel):
    timeframe: str = "15Min"
    entry_price: float
    initial_stop: float
    target_1: float | None = None
    target_2: float | None = None
    candles: list[PositionSimulationCandle]


class PositionSimulationObservation(BaseModel):
    timestamp: datetime
    from_state: str
    to_state: str
    event: str
    changed: bool
    reason: str
    candle_open: float
    candle_high: float
    candle_low: float
    candle_close: float
    active_stop_before: float
    active_stop_after: float
    target_1_hit: bool
    target_2_hit: bool
    exit_price: float | None = None
    exit_reason: str | None = None


class PositionLifecycleSimulationResponse(BaseModel):
    symbol: str
    timeframe: str
    simulation_mode: str
    execution_mode: str
    broker_order_submitted: bool
    database_mutated: bool
    initial_state: str
    final_state: str
    entry_price: float
    initial_stop: float
    active_stop: float
    target_1: float | None = None
    target_2: float | None = None
    initial_risk_per_share: float
    target_1_hit: bool
    target_2_hit: bool
    terminal: bool
    candles_received: int
    candles_evaluated: int
    validation_status: str
    observations: list[PositionSimulationObservation]


class PersistentPositionTestRequest(BaseModel):
    timeframe: str = "15Min"
    entry_price: float
    initial_stop: float
    target_1: float | None = None
    target_2: float | None = None
    opened_at: datetime
    candles: list[PositionSimulationCandle]


class PersistentPositionTestResponse(BaseModel):
    symbol: str
    timeframe: str
    test_run_id: str
    test_mode: str
    execution_mode: str
    persistence_mode: str
    broker_order_submitted: bool
    production_position_tables_mutated: bool
    test_database_mutated: bool
    initial_state: str
    final_state: str
    entry_price: float
    initial_stop: float
    active_stop: float
    target_1: float | None = None
    target_2: float | None = None
    initial_risk_per_share: float
    target_1_hit: bool
    target_2_hit: bool
    terminal: bool
    candles_received: int
    candles_evaluated: int
    version: int
    validation_status: str
    observations: list[PositionSimulationObservation]


class PersistentPositionTestHistoryResponse(BaseModel):
    symbol: str
    test_run_id: str
    test_mode: str
    execution_mode: str
    broker_order_submitted: bool
    production_position_tables_mutated: bool
    transitions: list[PositionLifecycleHistoryItem]


class PersistentPositionTestDeleteResponse(BaseModel):
    test_run_id: str
    deleted: bool
    production_position_tables_mutated: bool = False


class PersistentRealCandleMonitorStartRequest(BaseModel):
    timeframe: str = "15Min"
    entry_price: float
    initial_stop: float
    target_1: float | None = None
    target_2: float | None = None
    opened_at: datetime


class PersistentRealCandleMonitorResponse(BaseModel):
    symbol: str
    timeframe: str
    test_run_id: str
    test_mode: str
    execution_mode: str
    persistence_mode: str
    monitoring_mode: str
    monitoring_trigger: str
    monitoring_status: str
    broker_order_submitted: bool
    production_position_tables_mutated: bool
    test_database_mutated: bool
    state: str
    previous_state: str | None = None
    last_event: str
    reason: str
    entry_price: float
    initial_stop: float
    active_stop: float
    target_1: float | None = None
    target_2: float | None = None
    initial_risk_per_share: float
    target_1_hit: bool
    target_2_hit: bool
    terminal: bool
    opened_at: datetime
    last_evaluated_candle_time: datetime
    exit_price: float | None = None
    exit_reason: str | None = None
    closed_at: datetime | None = None
    current_price: float | None = None
    unrealized_per_share: float | None = None
    unrealized_r: float | None = None
    rows_scanned: int
    new_candles_found: int
    processed_candles: int
    duplicate_candles_skipped: int
    ignored_out_of_session_candles: int
    ignored_incomplete_candles: int
    version: int
    validation_status: str

class PositionPnLAnalyticsResponse(BaseModel):
    symbol: str
    timeframe: str
    analytics_mode: str
    analytics_scope: str
    analytics_candle_source: str
    source_data_status: str
    source_data_note: str | None = None
    execution_mode: str
    persistence_mode: str
    broker_order_submitted: bool
    production_position_tables_mutated: bool
    test_run_id: str | None = None
    analytics_status: str
    state: str
    terminal: bool
    pnl_basis: str
    entry_price: float | None = None
    current_price: float | None = None
    exit_price: float | None = None
    initial_risk_per_share: float | None = None
    unrealized_per_share: float | None = None
    unrealized_r: float | None = None
    realized_per_share: float | None = None
    realized_r: float | None = None
    mfe_per_share: float | None = None
    mfe_r: float | None = None
    mae_per_share: float | None = None
    mae_r: float | None = None
    best_price: float | None = None
    worst_price: float | None = None
    giveback_from_mfe_per_share: float | None = None
    exit_efficiency_pct: float | None = None
    holding_minutes: float | None = None
    opened_at: datetime | None = None
    analysis_end_at: datetime | None = None
    closed_at: datetime | None = None
    exit_reason: str | None = None
    candles_analyzed: int
    ignored_out_of_session_candles: int
    summary: str
