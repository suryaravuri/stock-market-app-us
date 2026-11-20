from datetime import datetime

from pydantic import BaseModel


class CandleQualityDetail(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    trade_count: int | None = None
    vwap: float | None = None
    source: str
    valid: bool
    issues: list[str]


class VolumeDiagnostics(BaseModel):
    latest_volume: float
    valid_prior_volume_count: int
    average_prior_volume: float | None
    volume_ratio_raw: float | None


class MarketDataQualityResponse(BaseModel):
    symbol: str
    timeframe: str
    status: str
    usable_for_breakout: bool
    candles_checked: int
    valid_candles: int
    invalid_candles: int
    zero_volume_candles: int
    invalid_ohlc_candles: int
    issue_counts: dict[str, int]
    latest_candle: CandleQualityDetail
    volume_diagnostics: VolumeDiagnostics
    notes: list[str]
