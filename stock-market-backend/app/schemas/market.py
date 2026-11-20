from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class MarketTimeframe(str, Enum):
    ONE_MINUTE = "1Min"
    FIVE_MINUTES = "5Min"
    FIFTEEN_MINUTES = "15Min"
    ONE_HOUR = "1Hour"
    ONE_DAY = "1Day"


class MarketBarResponse(BaseModel):
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    trade_count: int | None = None
    vwap: float | None = None

class MarketSyncResponse(BaseModel):
    symbol: str
    timeframe: MarketTimeframe
    fetched: int
    persisted: int
    position_monitoring: dict | None = None