from pydantic import BaseModel


class StrategyQualityBucket(BaseModel):
    key: str
    real_trade_count: int
    wins: int
    losses: int
    breakeven: int
    win_rate_pct: float
    average_r: float | None = None
    profit_factor_r: float | None = None
    sample_size_score: float
    expectancy_score: float
    profit_factor_score: float
    win_rate_score: float
    quality_score: float
    quality_grade: str
    confidence: str
    minimum_real_trades_for_grade: int
    recommended_real_trades_for_confidence: int


class StrategyQualityResponse(BaseModel):
    quality_mode: str
    execution_mode: str
    scope_requested: str
    scoring_scope: str
    broker_order_submitted: bool
    production_position_tables_mutated: bool
    symbol_filter: str | None = None
    timeframe_filter: str | None = None
    assessment: str
    quality_note: str
    real_market_trade_count: int
    isolated_test_trade_count: int
    unknown_source_trade_count: int
    test_trades_excluded_from_score: int
    real_trade_count: int
    wins: int
    losses: int
    breakeven: int
    win_rate_pct: float
    average_r: float | None = None
    profit_factor_r: float | None = None
    sample_size_score: float
    expectancy_score: float
    profit_factor_score: float
    win_rate_score: float
    quality_score: float
    quality_grade: str
    confidence: str
    minimum_real_trades_for_grade: int
    recommended_real_trades_for_confidence: int
    by_symbol: list[StrategyQualityBucket]
    by_timeframe: list[StrategyQualityBucket]
    summary: str


class StrategyQualitySimulationRequest(BaseModel):
    """#15G-5 stateless validation input expressed only in R-multiples."""

    realized_r_values: list[float]


class StrategyQualitySimulationResponse(BaseModel):
    simulation_mode: str
    execution_mode: str
    persistence_mode: str
    broker_order_submitted: bool
    database_mutated: bool
    production_position_tables_mutated: bool
    trades_received: int
    assessment: str
    quality_note: str
    real_market_trade_count: int
    isolated_test_trade_count: int
    unknown_source_trade_count: int
    test_trades_excluded_from_score: int
    real_trade_count: int
    wins: int
    losses: int
    breakeven: int
    win_rate_pct: float
    average_r: float | None = None
    profit_factor_r: float | None = None
    sample_size_score: float
    expectancy_score: float
    profit_factor_score: float
    win_rate_score: float
    quality_score: float
    quality_grade: str
    confidence: str
    minimum_real_trades_for_grade: int
    recommended_real_trades_for_confidence: int
    validation_status: str
    summary: str
