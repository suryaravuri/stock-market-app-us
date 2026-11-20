from pydantic import BaseModel


class WatchlistScanStockResponse(BaseModel):
    stock_id: int
    symbol: str

    company_name: str | None
    exchange: str | None

    priority: int

    current_price: float | None

    overall_score: int | None
    overall_classification: str

    risk_reward_quality: str

    rr_1: float | None
    rr_2: float | None

    entry: float | None
    stop_loss: float | None
    target_1: float | None
    target_2: float | None

    action: str
    decision_reasons: list[str]
    actionable: bool

    error: str | None


class WatchlistScanResponse(BaseModel):
    watchlist_id: int
    watchlist_name: str

    total_stocks: int
    actionable_count: int

    stocks: list[WatchlistScanStockResponse]