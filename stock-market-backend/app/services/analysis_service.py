from sqlalchemy.orm import Session

from app.schemas.market import MarketTimeframe
from app.services.indicator_service import IndicatorService
from app.services.support_resistance_service import (
    SupportResistanceService,
)


class AnalysisService:

    @staticmethod
    def get_summary(
        db: Session,
        symbol: str,
        timeframe: MarketTimeframe,
    ) -> dict:

        symbol = symbol.strip().upper()

        indicators = IndicatorService.get_indicators(
            db=db,
            symbol=symbol,
            timeframe=timeframe,
        )

        levels = SupportResistanceService.get_levels(
            db=db,
            symbol=symbol,
            timeframe=timeframe,
        )

        supports = levels["supports"]
        resistances = levels["resistances"]

        nearest_support_level = (
            supports[0]
            if supports
            else None
        )

        nearest_support = (
            nearest_support_level["price"]
            if nearest_support_level
            else None
        )

        next_support = (
            supports[1]["price"]
            if len(supports) > 1
            else None
        )

        nearest_resistance_level = (
            resistances[0]
            if resistances
            else None
        )

        nearest_resistance = (
            nearest_resistance_level["price"]
            if nearest_resistance_level
            else None
        )

        next_resistance = (
            resistances[1]["price"]
            if len(resistances) > 1
            else None
        )

        strongest_resistance = (
            max(
                resistances,
                key=lambda level: level["strength"],
            )["price"]
            if resistances
            else None
        )

        strongest_support = (
            max(
                supports,
                key=lambda level: level["strength"],
            )["price"]
            if supports
            else None
        )

        return {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "timestamp": indicators["timestamp"],
            "current_price": indicators["close"],

            "indicators": {
                "ema_9": indicators["ema_9"],
                "ema_20": indicators["ema_20"],
                "ema_50": indicators["ema_50"],
                "rsi_14": indicators["rsi_14"],
                "macd": indicators["macd"],
                "macd_signal": indicators["macd_signal"],
                "macd_histogram":
                    indicators["macd_histogram"],
                "atr_14": indicators["atr_14"],
                "session_vwap":
                    indicators["session_vwap"],
            },

            "support": {
                "nearest": nearest_support,
                "next": next_support,
                "strongest": strongest_support,
                "nearest_level": nearest_support_level,
            },

            "resistance": {
                "nearest": nearest_resistance,
                "next": next_resistance,
                "strongest": strongest_resistance,
                "nearest_level": nearest_resistance_level,
            },

            "candle_count": indicators["candle_count"],
        }