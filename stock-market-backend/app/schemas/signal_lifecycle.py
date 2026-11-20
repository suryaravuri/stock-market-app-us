from datetime import datetime

from pydantic import BaseModel


class SignalLifecycleResponse(BaseModel):
    symbol: str
    timeframe: str
    state: str
    previous_state: str | None
    last_event: str
    state_changed: bool
    reason: str
    observed_breakout_status: str | None
    breakout_level: float | None
    confirmation_price: float | None
    confirmed_entry_price: float | None
    signal_candle_time: datetime | None
    expired: bool = False
    staleness_status: str = "FRESH"
    expiration_reason: str | None = None
    signal_age_minutes: float | None = None
    max_signal_age_minutes: int = 45
    pending_candles: int = 0
    max_pending_candles: int = 4
    cycle_number: int = 1
    cycle_started_at: datetime | None = None
    rearmed: bool = False
    rearm_status: str = "NOT_APPLICABLE"
    rearm_reason: str | None = None
    version: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SignalLifecycleHistoryItem(BaseModel):
    from_state: str | None
    to_state: str
    event: str
    reason: str
    observed_breakout_status: str | None
    signal_candle_time: datetime | None
    cycle_number: int = 1
    created_at: datetime


class SignalLifecycleHistoryResponse(BaseModel):
    symbol: str
    timeframe: str
    transitions: list[SignalLifecycleHistoryItem]
