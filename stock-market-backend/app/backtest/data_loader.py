"""Fetch historical bars from Alpaca into the BACKTEST database.

No files are uploaded anywhere: bars go straight from Alpaca's API into the
backtest database, in one-year windows, with split-adjusted prices so a stock
split doesn't look like a crash.

US stocks only for now (NSE/BSE history would come from Zerodha's historical
API, which needs a daily login and possibly a paid add-on).
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone

from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.market.sessions import is_indian_exchange
from app.models.stock import Stock
from app.repositories.market_candle_repository import MarketCandleRepository
from app.schemas.market import MarketTimeframe
from app.services.market_service import MarketService

logger = logging.getLogger(__name__)

# Extra history before the start date so indicators (EMA50 on daily bars,
# ATR, support/resistance) are warmed up on day one of the test.
WARMUP_DAYS = {
    MarketTimeframe.FIFTEEN_MINUTES: 90,
    MarketTimeframe.ONE_HOUR: 180,
    MarketTimeframe.ONE_DAY: 400,
}

UPSERT_BATCH = 5_000
PAUSE_BETWEEN_REQUESTS_SECONDS = 0.4  # stay well under Alpaca's rate limit


def ensure_stock(
    bt_db: Session,
    app_db: Session,
    symbol: str,
    allow_indian: bool = False,
) -> Stock:
    """Copy the stock master row from the app DB into the backtest DB.

    allow_indian=True is used for CSV uploads, where the data comes from the
    file instead of Alpaca.
    """
    symbol = symbol.strip().upper()
    existing = bt_db.scalar(select(Stock).where(Stock.symbol == symbol))
    if existing is not None:
        if is_indian_exchange(existing.exchange) and not allow_indian:
            raise ValueError(f"{symbol}: Indian stocks need an uploaded CSV")
        return existing

    source = app_db.scalar(select(Stock).where(Stock.symbol == symbol))
    if source is not None:
        exchange = source.exchange
    elif symbol.endswith(".NS"):
        exchange = "NSE"
    elif symbol.endswith(".BO"):
        exchange = "BSE"
    else:
        exchange = "NASDAQ"

    stock = Stock(
        symbol=symbol,
        company_name=source.company_name if source else None,
        exchange=exchange,
        asset_type=source.asset_type if source else "STOCK",
        tradable=True,
        active=True,
    )
    if is_indian_exchange(stock.exchange) and not allow_indian:
        raise ValueError(f"{symbol}: Indian stocks need an uploaded CSV")
    bt_db.add(stock)
    bt_db.commit()
    bt_db.refresh(stock)
    return stock


def _year_windows(start: datetime, end: datetime):
    cursor = start
    while cursor < end:
        window_end = min(cursor + timedelta(days=365), end)
        yield cursor, window_end
        cursor = window_end


def load_history(
    bt_db: Session,
    stock: Stock,
    start: date,
    end: date,
    progress: callable | None = None,
) -> dict[str, int]:
    client = StockHistoricalDataClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
    )
    feed = DataFeed(settings.backtest_data_feed.lower())
    end_dt = datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc)
    # Alpaca's free plan can't serve the most recent 15 minutes of SIP data.
    end_dt = min(end_dt, datetime.now(timezone.utc) - timedelta(minutes=20))

    counts: dict[str, int] = {}
    for timeframe, warmup in WARMUP_DAYS.items():
        start_dt = datetime.combine(start - timedelta(days=warmup), datetime.min.time(), tzinfo=timezone.utc)
        total = 0
        for window_start, window_end in _year_windows(start_dt, end_dt):
            request = StockBarsRequest(
                symbol_or_symbols=stock.symbol,
                timeframe=MarketService._get_alpaca_timeframe(timeframe),
                start=window_start,
                end=window_end,
                feed=feed,
                adjustment=Adjustment.SPLIT,
            )
            bars = client.get_stock_bars(request).data.get(stock.symbol, [])
            rows = [
                {
                    "stock_id": stock.stock_id,
                    "timeframe": timeframe.value,
                    "candle_time": bar.timestamp,
                    "open_price": bar.open,
                    "high_price": bar.high,
                    "low_price": bar.low,
                    "close_price": bar.close,
                    "volume": bar.volume,
                    "trade_count": bar.trade_count,
                    "vwap": bar.vwap,
                    "source": f"ALPACA_{feed.value.upper()}_BACKTEST",
                }
                for bar in bars
            ]
            for i in range(0, len(rows), UPSERT_BATCH):
                MarketCandleRepository.upsert_all(bt_db, rows[i : i + UPSERT_BATCH])
            total += len(rows)
            if progress:
                progress(f"{stock.symbol} {timeframe.value}: {total} bars loaded")
            time.sleep(PAUSE_BETWEEN_REQUESTS_SECONDS)
        counts[timeframe.value] = total
        logger.info("Loaded %d %s bars for %s", total, timeframe.value, stock.symbol)
    return counts
