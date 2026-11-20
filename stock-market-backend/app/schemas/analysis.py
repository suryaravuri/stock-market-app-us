from datetime import datetime

from pydantic import BaseModel


class AnalysisIndicators(BaseModel):
    ema_9: float | None
    ema_20: float | None
    ema_50: float | None

    rsi_14: float | None

    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None

    atr_14: float | None
    session_vwap: float | None


class AnalysisPriceLevel(BaseModel):
    price: float
    level_type: str
    strength: float
    touches: int
    distance_from_price: float


class AnalysisSupport(BaseModel):
    nearest: float | None
    next: float | None
    strongest: float | None
    nearest_level: AnalysisPriceLevel | None = None


class AnalysisResistance(BaseModel):
    nearest: float | None
    next: float | None
    strongest: float | None
    nearest_level: AnalysisPriceLevel | None = None


class AnalysisSummaryResponse(BaseModel):
    symbol: str
    timeframe: str
    timestamp: datetime
    current_price: float

    indicators: AnalysisIndicators

    support: AnalysisSupport
    resistance: AnalysisResistance

    candle_count: int