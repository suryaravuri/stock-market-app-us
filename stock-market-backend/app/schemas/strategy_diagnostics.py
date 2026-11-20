from pydantic import BaseModel


class StrategyDiagnosticMetrics(BaseModel):
    trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate_pct: float
    average_r: float | None = None
    profit_factor_r: float | None = None
    stop_exit_rate_pct: float
    target_2_exit_rate_pct: float
    trailing_stop_exit_rate_pct: float
    average_holding_minutes: float | None = None


class StrategyDiagnosticIssue(BaseModel):
    priority: int
    severity: str
    code: str
    title: str
    evidence: str
    recommendation: str


class StrategyDiagnosticBucket(StrategyDiagnosticMetrics):
    key: str


class StrategyDiagnosticsResponse(BaseModel):
    diagnostics_mode: str
    execution_mode: str
    scope_requested: str
    diagnostic_scope: str
    broker_order_submitted: bool
    database_mutated: bool
    production_position_tables_mutated: bool
    symbol_filter: str | None = None
    timeframe_filter: str | None = None
    diagnostic_status: str
    real_market_trade_count: int
    isolated_test_trade_count: int
    unknown_source_trade_count: int
    test_trades_excluded_from_diagnostics: int
    metrics: StrategyDiagnosticMetrics
    weakness_count: int
    weaknesses: list[StrategyDiagnosticIssue]
    strengths: list[str]
    by_symbol: list[StrategyDiagnosticBucket]
    by_timeframe: list[StrategyDiagnosticBucket]
    summary: str


class StrategyDiagnosticsSimulationTrade(BaseModel):
    """One hypothetical completed analytical trade used only by #15H-5."""

    realized_r: float
    symbol: str = "SIMULATION"
    timeframe: str = "15Min"
    state: str | None = None
    exit_reason: str | None = None
    holding_minutes: float = 60.0


class StrategyDiagnosticsSimulationRequest(BaseModel):
    """#15H-5 stateless diagnostics validation input."""

    trades: list[StrategyDiagnosticsSimulationTrade]


class StrategyDiagnosticsSimulationResponse(BaseModel):
    simulation_mode: str
    diagnostics_mode: str
    execution_mode: str
    persistence_mode: str
    diagnostic_scope: str
    broker_order_submitted: bool
    database_mutated: bool
    production_position_tables_mutated: bool
    trades_received: int
    diagnostic_status: str
    real_market_trade_count: int
    isolated_test_trade_count: int
    unknown_source_trade_count: int
    test_trades_excluded_from_diagnostics: int
    metrics: StrategyDiagnosticMetrics
    weakness_count: int
    weaknesses: list[StrategyDiagnosticIssue]
    strengths: list[str]
    by_symbol: list[StrategyDiagnosticBucket]
    by_timeframe: list[StrategyDiagnosticBucket]
    validation_status: str
    summary: str
