from datetime import datetime
from pydantic import BaseModel


class BreakoutConfirmationResponse(BaseModel):
    symbol: str
    timeframe: str
    timestamp: datetime
    status: str
    confirmed: bool
    breakout_level: float | None
    confirmation_price: float | None
    buffer_price: float | None
    volume_ratio: float | None
    lookback_candles: int
    min_volume_ratio: float
    min_body_ratio: float = 0.50
    min_close_location: float = 0.70
    max_upper_wick_ratio: float = 0.30
    price_confirmed: bool = False
    volume_confirmed: bool = False
    candle_quality_confirmed: bool = False
    # Improvement #10: breakout detection is separated from final entry confirmation.
    breakout_detected: bool = False
    follow_through_required: bool = True
    follow_through_confirmed: bool = False
    retest_confirmed: bool = False
    follow_through_status: str | None = None
    breakout_candle_timestamp: datetime | None = None
    follow_through_candle_timestamp: datetime | None = None
    follow_through_close: float | None = None
    follow_through_low: float | None = None
    failed_quality_checks: list[str] = []
    candle_range: float | None = None
    body_ratio: float | None = None
    close_location: float | None = None
    upper_wick_ratio: float | None = None
    ignored_zero_volume_candles: int = 0
    ignored_invalid_candles: int = 0
    ignored_out_of_session_candles: int = 0
    ignored_low_liquidity_candles: int = 0
    ignored_zero_range_candles: int = 0
    ignored_low_trade_count_candles: int = 0
    session: str = "REGULAR"
    session_timezone: str = "America/New_York"
    min_liquidity_ratio: float = 0.10
    min_trade_count: int = 10
    latest_volume: float | None = None
    average_prior_volume: float | None = None
    volume_ratio_raw: float | None = None
    data_quality_note: str | None = None
    reasons: list[str]
