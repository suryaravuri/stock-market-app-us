"""Market data diagnostic.

Run from stock-market-backend/:
    python -m app.scripts.check_market_data            (default symbol AAPL)
    python -m app.scripts.check_market_data NVDA

It answers three questions:
  1. Can we reach Alpaca with the configured keys?
  2. Does Alpaca return recent 15-min bars (IEX feed)?
  3. What is the newest candle stored in the database?
Then it runs one real sync for the symbol and shows the DB again.
"""
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.market_candle import MarketCandle
from app.models.stock import Stock


def _mask(value: str | None) -> str:
    if not value:
        return "<EMPTY>"
    return f"{value[:4]}...{value[-2:]} (len {len(value)})"


def _latest_in_db(symbol: str) -> None:
    with SessionLocal() as db:
        stock = db.scalar(select(Stock).where(Stock.symbol == symbol))
        if stock is None:
            print(f"   {symbol} is not in the stock table")
            return
        rows = db.execute(
            select(MarketCandle.timeframe, func.max(MarketCandle.candle_time))
            .where(MarketCandle.stock_id == stock.stock_id)
            .group_by(MarketCandle.timeframe)
        ).all()
        for timeframe, latest in rows:
            print(f"   {timeframe:>6}: newest candle {latest}")


def main() -> None:
    symbol = (sys.argv[1] if len(sys.argv) > 1 else "AAPL").upper()
    print(f"Now (UTC): {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}")
    print(f"ALPACA_API_KEY:    {_mask(settings.alpaca_api_key)}")
    print(f"ALPACA_SECRET_KEY: {_mask(settings.alpaca_secret_key)}")
    print(f"Database:          {settings.database_host}:{settings.database_port}/{settings.database_name}")

    print("\n1) Alpaca trading API (keys + market clock)")
    try:
        from app.brokers.alpaca.trading_client import AlpacaPaperTradingClient
        clock = AlpacaPaperTradingClient().client.get_clock()
        print(f"   OK  market open={clock.is_open}  next_open={clock.next_open}  next_close={clock.next_close}")
    except Exception as exc:  # noqa: BLE001
        print(f"   FAILED: {type(exc).__name__}: {exc}")
        print("   -> Keys are wrong/expired (paper account reset regenerates them).")

    print(f"\n2) Alpaca market data: 15Min IEX bars for {symbol}, last 5 days")
    try:
        from app.brokers.alpaca.historical_data import AlpacaHistoricalDataClient
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        end = datetime.now(timezone.utc)
        bars = AlpacaHistoricalDataClient().get_stock_bars(
            symbol, end - timedelta(days=5), end, TimeFrame(15, TimeFrameUnit.Minute)
        ).data.get(symbol, [])
        if bars:
            print(f"   OK  {len(bars)} bars, newest {bars[-1].timestamp}")
        else:
            print("   RETURNED 0 BARS (symbol/feed problem)")
    except Exception as exc:  # noqa: BLE001
        print(f"   FAILED: {type(exc).__name__}: {exc}")

    print(f"\n3) Database BEFORE sync ({symbol})")
    _latest_in_db(symbol)

    print(f"\n4) Running one real sync for {symbol} ...")
    try:
        from app.schemas.market import MarketTimeframe
        from app.services.market_service import MarketService
        with SessionLocal() as db:
            result = MarketService().sync_bars(
                db=db, symbol=symbol,
                timeframe=MarketTimeframe.FIFTEEN_MINUTES, days=15,
            )
        print(f"   OK  fetched={result['fetched']} persisted={result['persisted']}")
    except Exception as exc:  # noqa: BLE001
        print(f"   FAILED: {type(exc).__name__}: {exc}")

    print(f"\n5) Database AFTER sync ({symbol})")
    _latest_in_db(symbol)


if __name__ == "__main__":
    main()
