from datetime import datetime, timedelta, timezone

from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from app.brokers.alpaca.historical_data import (
    AlpacaHistoricalDataClient,
)
from app.schemas.market import MarketTimeframe
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.market_candle_repository import (
    MarketCandleRepository,
)
from app.repositories.stock_repository import StockRepository
from app.services.position_monitoring_service import PositionMonitoringService

from sqlalchemy import select

from app.models.stock import Stock
from app.market.sessions import broker_symbol, is_indian_exchange
from app.brokers.zerodha.kite_client import ZerodhaClient
from app.trading.zerodha_order_rules import IST

class MarketService:

    # Kite historical-data interval names.
    KITE_INTERVALS = {
        MarketTimeframe.ONE_MINUTE: "minute",
        MarketTimeframe.FIVE_MINUTES: "5minute",
        MarketTimeframe.FIFTEEN_MINUTES: "15minute",
        MarketTimeframe.ONE_HOUR: "60minute",
        MarketTimeframe.ONE_DAY: "day",
    }

    def __init__(self, zerodha_client: "ZerodhaClient | None" = None) -> None:
        self.alpaca = AlpacaHistoricalDataClient()
        # Needed only for NSE/BSE stocks; tied to one user's daily Zerodha login.
        self.zerodha = zerodha_client

    def _get_zerodha_bars(
        self,
        db: Session,
        stock: Stock,
        timeframe: MarketTimeframe,
        days: int,
    ) -> list[dict]:
        if self.zerodha is None:
            raise ValueError(
                "Zerodha is not connected. Complete today's Zerodha login to sync NSE/BSE stocks."
            )

        exchange = (stock.exchange or "").strip().upper()
        tradingsymbol = broker_symbol(stock.symbol)

        if stock.instrument_token is None:
            token = self.zerodha.instrument_token(exchange, tradingsymbol)
            if token is None:
                raise ValueError(f"{tradingsymbol} was not found on {exchange} (equity segment)")
            stock.instrument_token = token
            db.commit()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

        rows = self.zerodha.historical(
            stock.instrument_token,
            start,
            end,
            self.KITE_INTERVALS[timeframe],
        )

        bars = []
        for row in rows:
            timestamp = row["date"]
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=IST)
            bars.append(
                {
                    "symbol": stock.symbol,
                    "timestamp": timestamp,
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row.get("volume"),
                    # Kite does not provide these; analysis treats None as unknown.
                    "trade_count": None,
                    "vwap": None,
                }
            )
        return bars

    @staticmethod
    def _get_alpaca_timeframe(
        timeframe: MarketTimeframe,
    ) -> TimeFrame:

        mapping = {
            MarketTimeframe.ONE_MINUTE:
                TimeFrame.Minute,

            MarketTimeframe.FIVE_MINUTES:
                TimeFrame(5, TimeFrameUnit.Minute),

            MarketTimeframe.FIFTEEN_MINUTES:
                TimeFrame(15, TimeFrameUnit.Minute),

            MarketTimeframe.ONE_HOUR:
                TimeFrame.Hour,

            MarketTimeframe.ONE_DAY:
                TimeFrame.Day,
        }

        return mapping[timeframe]

    def get_bars(
        self,
        symbol: str,
        timeframe: MarketTimeframe,
        days: int,
    ) -> list[dict]:

        symbol = symbol.upper()

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

        alpaca_timeframe = self._get_alpaca_timeframe(
            timeframe
        )

        result = self.alpaca.get_stock_bars(
            symbol=symbol,
            start=start,
            end=end,
            timeframe=alpaca_timeframe,
        )

        bars = result.data.get(symbol, [])

        return [
            {
                "symbol": symbol,
                "timestamp": bar.timestamp,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "trade_count": bar.trade_count,
                "vwap": bar.vwap,
            }
            for bar in bars
        ]

    def sync_bars(
        self,
        db: Session,
        symbol: str,
        timeframe: MarketTimeframe,
        days: int,
    ) -> dict:

        symbol = symbol.upper()

        # 1. Find stock master record
        stmt = select(Stock).where(
            Stock.symbol == symbol
        )

        stock = db.scalar(stmt)

        if stock is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stock '{symbol}' not found",
            )

        # 2. Get bars: Zerodha for NSE/BSE, Alpaca for everything else
        if is_indian_exchange(stock.exchange):
            source = "ZERODHA"
            bars = self._get_zerodha_bars(db, stock, timeframe, days)
        else:
            source = "ALPACA"
            bars = self.get_bars(
                symbol=symbol,
                timeframe=timeframe,
                days=days,
            )

        # 3. Convert API bars → database rows
        candles = [
            {
                "stock_id": stock.stock_id,
                "timeframe": timeframe.value,
                "candle_time": bar["timestamp"],
                "open_price": bar["open"],
                "high_price": bar["high"],
                "low_price": bar["low"],
                "close_price": bar["close"],
                "volume": bar["volume"],
                "trade_count": bar["trade_count"],
                "vwap": bar["vwap"],
                "source": source,
            }
            for bar in bars
        ]

        # 4. Batch UPSERT
        persisted = MarketCandleRepository.upsert_all(
            db,
            candles,
        )

        # 5. Improvement #15D: after fresh bars are stored, advance only an
        # already-existing persistent analytical position. The monitor cannot
        # create a position and cannot submit broker orders.
        position_monitoring = PositionMonitoringService.monitor_existing(
            db, symbol, timeframe, trigger="MARKET_SYNC"
        )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "fetched": len(bars),
            "persisted": persisted,
            "position_monitoring": position_monitoring,
        }