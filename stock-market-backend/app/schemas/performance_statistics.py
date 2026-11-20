from datetime import date, datetime

from pydantic import BaseModel
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, Boolean, DateTime, String, func

class PerformancePeriod(BaseModel):
    start_date: date
    end_date: date


class PerformanceTrade(BaseModel):
    symbol: str
    timeframe: str
    signal_cycle_number: int

    quantity: int | None = None

    entry_price: float
    exit_price: float | None

    buy_value: float | None = None
    sell_value: float | None = None

    profit_loss_per_share: float | None
    profit_loss: float | None = None

    result: str

    opened_at: datetime
    closed_at: datetime | None
    exit_reason: str | None


class PerformanceStatisticsResponse(BaseModel):


    period: PerformancePeriod

    execution_mode: str

    stocks_bought: int
    stocks_sold: int

    shares_bought: int = 0
    shares_sold: int = 0

    positions_opened: int
    positions_closed: int
    positions_still_open: int

    winning_trades: int
    losing_trades: int
    breakeven_trades: int

    total_buy_value: float = 0.0
    total_sell_value: float = 0.0

    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit_loss: float = 0.0

    profit_loss_per_share: float

    win_rate_percent: float | None

    broker_orders_submitted: int

    trades: list[PerformanceTrade]