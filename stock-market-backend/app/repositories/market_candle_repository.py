from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.market_candle import MarketCandle


class MarketCandleRepository:

    @staticmethod
    def upsert_all(
        db: Session,
        candles: list[dict],
    ) -> int:

        if not candles:
            return 0

        stmt = insert(MarketCandle).values(candles)

        stmt = stmt.on_conflict_do_update(
            index_elements=[
                MarketCandle.stock_id,
                MarketCandle.timeframe,
                MarketCandle.candle_time,
            ],
            set_={
                "open_price": stmt.excluded.open_price,
                "high_price": stmt.excluded.high_price,
                "low_price": stmt.excluded.low_price,
                "close_price": stmt.excluded.close_price,
                "volume": stmt.excluded.volume,
                "trade_count": stmt.excluded.trade_count,
                "vwap": stmt.excluded.vwap,
                "source": stmt.excluded.source,
            },
        )

        db.execute(stmt)
        db.commit()

        return len(candles)

    @staticmethod
    def find_by_range(
        db: Session,
        stock_id: int,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[MarketCandle]:

        stmt = (
            select(MarketCandle)
            .where(
                MarketCandle.stock_id == stock_id,
                MarketCandle.timeframe == timeframe,
                MarketCandle.candle_time >= start,
                MarketCandle.candle_time <= end,
            )
            .order_by(MarketCandle.candle_time.asc())
        )

        return list(
            db.scalars(stmt).all()
        )

    @staticmethod
    def find_latest(
        db: Session,
        stock_id: int,
        timeframe: str,
    ) -> MarketCandle | None:

        stmt = (
            select(MarketCandle)
            .where(
                MarketCandle.stock_id == stock_id,
                MarketCandle.timeframe == timeframe,
            )
            .order_by(
                MarketCandle.candle_time.desc()
            )
            .limit(1)
        )

        return db.scalar(stmt)