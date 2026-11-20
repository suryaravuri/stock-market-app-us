from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import detect_support_resistance
from app.indicators import calculate_atr
from app.models.market_candle import MarketCandle
from app.models.stock import Stock
from app.schemas.market import MarketTimeframe


class SupportResistanceService:

    @staticmethod
    def get_levels(
        db: Session,
        symbol: str,
        timeframe: MarketTimeframe,
    ) -> dict:

        symbol = symbol.strip().upper()

        # 1. Find stock
        stock_stmt = select(Stock).where(
            Stock.symbol == symbol
        )

        stock = db.scalar(stock_stmt)

        if stock is None:
            raise ValueError(
                f"Stock '{symbol}' not found"
            )

        # 2. Load candles
        candle_stmt = (
            select(MarketCandle)
            .where(
                MarketCandle.stock_id == stock.stock_id,
                MarketCandle.timeframe == timeframe.value,
            )
            .order_by(
                MarketCandle.candle_time.desc()
            )
            .limit(250)
        )

        candles = list(
            db.scalars(candle_stmt).all()
        )

        if not candles:
            raise ValueError(
                f"No candle data found for "
                f"{symbol} / {timeframe.value}"
            )

        # Indicators need chronological order
        candles.reverse()

        # 3. Extract data
        highs = [
            float(candle.high_price)
            for candle in candles
        ]

        lows = [
            float(candle.low_price)
            for candle in candles
        ]

        closes = [
            float(candle.close_price)
            for candle in candles
        ]

        # 4. ATR
        atr_values = calculate_atr(
            highs=highs,
            lows=lows,
            closes=closes,
            period=14,
        )

        latest_atr = atr_values[-1]

        # 5. Detect levels
        levels = detect_support_resistance(
            highs=highs,
            lows=lows,
            closes=closes,
            atr=latest_atr,
            swing_window=3,
            cluster_threshold_atr=0.35,
            max_levels=5,
        )

        latest_candle = candles[-1]

        # 6. Convert dataclasses to API-friendly dictionaries
        supports = [
            {
                "price": level.price,
                "level_type": level.level_type,
                "strength": level.strength,
                "touches": level.touches,
                "distance_from_price": level.distance_from_price,
            }
            for level in levels["supports"]
        ]

        resistances = [
            {
                "price": level.price,
                "level_type": level.level_type,
                "strength": level.strength,
                "touches": level.touches,
                "distance_from_price": level.distance_from_price,
            }
            for level in levels["resistances"]
        ]

        return {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "timestamp": latest_candle.candle_time,
            "current_price": float(
                latest_candle.close_price
            ),
            "atr_14": (
                round(latest_atr, 4)
                if latest_atr is not None
                else None
            ),
            "supports": supports,
            "resistances": resistances,
            "candle_count": len(candles),
        }