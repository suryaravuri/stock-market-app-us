from sqlalchemy.orm import Session

from app.analysis import calculate_opportunity_score
from app.schemas.market import MarketTimeframe
from app.services.analysis_service import AnalysisService


class OpportunityService:

    @staticmethod
    def get_opportunity(
        db: Session,
        symbol: str,
        timeframe: MarketTimeframe,
    ) -> dict:

        symbol = symbol.strip().upper()

        summary = AnalysisService.get_summary(
            db=db,
            symbol=symbol,
            timeframe=timeframe,
        )

        indicators = summary["indicators"]
        support = summary["support"]
        resistance = summary["resistance"]

        nearest_support_level = support.get("nearest_level")
        nearest_resistance_level = resistance.get("nearest_level")

        result = calculate_opportunity_score(
            current_price=summary["current_price"],
            ema_9=indicators["ema_9"],
            ema_20=indicators["ema_20"],
            ema_50=indicators["ema_50"],
            rsi_14=indicators["rsi_14"],
            macd=indicators["macd"],
            macd_signal=indicators["macd_signal"],
            macd_histogram=indicators["macd_histogram"],
            session_vwap=indicators["session_vwap"],
            nearest_support=support["nearest"],
            nearest_resistance=resistance["nearest"],
            atr_14=indicators["atr_14"],
            nearest_support_strength=(
                nearest_support_level["strength"]
                if nearest_support_level
                else None
            ),
            nearest_resistance_strength=(
                nearest_resistance_level["strength"]
                if nearest_resistance_level
                else None
            ),
        )

        reasons = [
            {
                "code": reason.code,
                "description": reason.description,
                "score": reason.score,
            }
            for reason in result.reasons
        ]

        return {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "timestamp": summary["timestamp"],
            "current_price": summary["current_price"],

            "score": result.score,
            "classification": result.classification,

            "nearest_support": support["nearest"],
            "nearest_resistance": resistance["nearest"],

            "reasons": reasons,
        }