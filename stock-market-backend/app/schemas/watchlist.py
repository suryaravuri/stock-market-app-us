from typing import Literal
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# SWING = no time limit; INTRADAY = squared off before the close;
# WEEKLY = 5 trading sessions; MONTHLY = 21 trading sessions.
HoldingStyleLiteral = Literal["SWING", "INTRADAY", "WEEKLY", "MONTHLY"]


class WatchlistBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    active: bool = True


class WatchlistCreate(WatchlistBase):
    pass


class WatchlistUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    active: bool | None = None


class WatchlistResponse(WatchlistBase):
    watchlist_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WatchlistStockCreate(BaseModel):
    stock_id: int
    priority: int = Field(default=0, ge=0)
    analysis_enabled: bool = True
    trading_enabled: bool = False

    profit_target_percent:float = Field(
        default=5.0,
        gt=0,
        le=100,
    )

    loss_limit_percent:float = Field(
        default=5.0,
        gt=0,
        le=100,
    )

    # How long an automatic position may stay open.
    holding_style: HoldingStyleLiteral = "SWING"


class WatchlistStockUpdate(BaseModel):
    priority: int | None = Field(default=None, ge=0)
    analysis_enabled: bool | None = None
    trading_enabled: bool | None = None

    profit_target_percent: float | None = Field(
        default=None,
        gt=0,
        le=100,
    )

    loss_limit_percent: float | None = Field(
        default=None,
        gt=0,
        le=100,
    )

    holding_style: HoldingStyleLiteral | None = None


class WatchlistStockInfo(BaseModel):
    stock_id: int
    symbol: str
    company_name: str | None
    exchange: str | None

    model_config = ConfigDict(from_attributes=True)


class WatchlistStockResponse(BaseModel):
    watchlist_id: int
    stock_id: int

    priority: int
    analysis_enabled: bool
    trading_enabled: bool

    profit_target_percent: float
    loss_limit_percent: float
    holding_style: str = "SWING"

    added_at: datetime

    stock: WatchlistStockInfo

    model_config = ConfigDict(from_attributes=True)