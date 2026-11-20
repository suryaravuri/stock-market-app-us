from datetime import datetime

from pydantic import BaseModel


class IndicatorResponse(BaseModel):
    symbol: str
    timeframe: str
    timestamp: datetime

    close: float

    ema_9: float | None
    ema_20: float | None
    ema_50: float | None

    rsi_14: float | None

    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None

    atr_14: float | None
    session_vwap: float | None

    candle_count: int