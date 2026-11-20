from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.market.sessions import session_for_stock
from app.indicators import (
    calculate_atr,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_session_vwap,
)
from app.models.market_candle import MarketCandle
from app.models.stock import Stock
from app.schemas.market import MarketTimeframe


class IndicatorService:

    @staticmethod
    def get_indicators(
        db: Session,
        symbol: str,
        timeframe: MarketTimeframe,
    ) -> dict:

        symbol = symbol.strip().upper()

        # ---------------------------------
        # 1. Find Stock
        # ---------------------------------

        stock_stmt = select(Stock).where(
            Stock.symbol == symbol
        )

        stock = db.scalar(stock_stmt)

        if stock is None:
            raise ValueError(
                f"Stock '{symbol}' not found"
            )

        # ---------------------------------
        # 2. Load latest candles
        # ---------------------------------

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

        # Database query returns newest -> oldest.
        # Indicator calculations require oldest -> newest.
        candles.reverse()

        # ---------------------------------
        # 3. Extract candle series
        # ---------------------------------

        closes = [
            float(candle.close_price)
            for candle in candles
        ]

        highs = [
            float(candle.high_price)
            for candle in candles
        ]

        lows = [
            float(candle.low_price)
            for candle in candles
        ]

        volumes = [
            float(candle.volume or 0)
            for candle in candles
        ]

        # Session VWAP resets on the exchange's local calendar day.
        market_tz = session_for_stock(stock).tz
        timestamps = [
            candle.candle_time.astimezone(market_tz)
            for candle in candles
        ]

        # ---------------------------------
        # 4. Calculate indicators
        # ---------------------------------

        ema_9 = calculate_ema(
            closes,
            9,
        )

        ema_20 = calculate_ema(
            closes,
            20,
        )

        ema_50 = calculate_ema(
            closes,
            50,
        )

        rsi_14 = calculate_rsi(
            closes,
            14,
        )

        (
            macd_line,
            macd_signal,
            macd_histogram,
        ) = calculate_macd(
            closes
        )

        atr_14 = calculate_atr(
            highs=highs,
            lows=lows,
            closes=closes,
            period=14,
        )

        session_vwap = calculate_session_vwap(
            timestamps=timestamps,
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
        )

        # ---------------------------------
        # 5. Latest values
        # ---------------------------------

        latest_candle = candles[-1]

        return {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "timestamp": latest_candle.candle_time,

            "close": float(
                latest_candle.close_price
            ),

            "ema_9": IndicatorService._round_value(
                ema_9[-1]
            ),

            "ema_20": IndicatorService._round_value(
                ema_20[-1]
            ),

            "ema_50": IndicatorService._round_value(
                ema_50[-1]
            ),

            "rsi_14": IndicatorService._round_value(
                rsi_14[-1]
            ),

            "macd": IndicatorService._round_value(
                macd_line[-1]
            ),

            "macd_signal": IndicatorService._round_value(
                macd_signal[-1]
            ),

            "macd_histogram": IndicatorService._round_value(
                macd_histogram[-1]
            ),

            "atr_14": IndicatorService._round_value(
                atr_14[-1]
            ),

            "session_vwap": IndicatorService._round_value(
                session_vwap[-1]
            ),

            "candle_count": len(candles),
        }

    @staticmethod
    def _round_value(
        value: float | None,
        digits: int = 4,
    ) -> float | None:

        if value is None:
            return None

        return round(value, digits)