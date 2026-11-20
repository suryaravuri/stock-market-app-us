from datetime import datetime
from pydantic import BaseModel


class TradeJournalEntry(BaseModel):
    source: str
    position_id: str
    test_run_id: str | None = None
    symbol: str
    timeframe: str
    state: str
    outcome: str
    entry_price: float
    exit_price: float
    realized_per_share: float
    realized_r: float | None = None
    opened_at: datetime
    closed_at: datetime
    holding_minutes: float
    exit_reason: str | None = None
    signal_cycle_number: int | None = None
    analytics_candle_source: str | None = None


class TradeJournalResponse(BaseModel):
    journal_mode: str
    execution_mode: str
    scope: str
    broker_order_submitted: bool
    production_position_tables_mutated: bool
    symbol_filter: str | None = None
    timeframe_filter: str | None = None
    total_completed_trades: int
    returned_trades: int
    entries: list[TradeJournalEntry]


class PerformanceBucket(BaseModel):
    key: str
    trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate_pct: float
    average_r: float | None = None
    expectancy_r: float | None = None
    profit_factor: float | None = None
    average_holding_minutes: float | None = None


class TradePerformanceResponse(BaseModel):
    statistics_mode: str
    execution_mode: str
    scope: str
    broker_order_submitted: bool
    production_position_tables_mutated: bool
    symbol_filter: str | None = None
    timeframe_filter: str | None = None
    total_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate_pct: float
    loss_rate_pct: float
    average_r: float | None = None
    median_r: float | None = None
    expectancy_r: float | None = None
    gross_profit_per_share: float
    gross_loss_per_share: float
    net_realized_per_share: float
    profit_factor: float | None = None
    average_winner_r: float | None = None
    average_loser_r: float | None = None
    average_holding_minutes: float | None = None
    stop_hit_exits: int
    target_2_hit_exits: int
    trailing_stop_exits: int
    best_trade: TradeJournalEntry | None = None
    worst_trade: TradeJournalEntry | None = None
    by_symbol: list[PerformanceBucket]
    by_timeframe: list[PerformanceBucket]
    summary: str
