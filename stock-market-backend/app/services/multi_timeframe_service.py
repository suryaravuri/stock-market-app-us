from sqlalchemy.orm import Session

from app.schemas.market import MarketTimeframe
from app.services.opportunity_service import OpportunityService


class MultiTimeframeService:

    WEIGHTS = {
        MarketTimeframe.FIFTEEN_MINUTES: 0.30,
        MarketTimeframe.ONE_HOUR: 0.40,
        MarketTimeframe.ONE_DAY: 0.30,
    }

    @staticmethod
    def get_analysis(
        db: Session,
        symbol: str,
    ) -> dict:

        symbol = symbol.strip().upper()

        results = {}

        weighted_score = 0.0

        for timeframe, weight in MultiTimeframeService.WEIGHTS.items():

            opportunity = OpportunityService.get_opportunity(
                db=db,
                symbol=symbol,
                timeframe=timeframe,
            )

            results[timeframe.value] = {
                "score": opportunity["score"],
                "classification": opportunity["classification"],
                "current_price": opportunity["current_price"],
                "nearest_support": opportunity["nearest_support"],
                "nearest_resistance": opportunity["nearest_resistance"],
            }

            weighted_score += (
                opportunity["score"] * weight
            )

        overall_score = round(
            weighted_score
        )

        overall_classification = (
            MultiTimeframeService._classify(
                overall_score
            )
        )

        return {
            "symbol": symbol,
            "timeframes": results,
            "overall_score": overall_score,
            "overall_classification": overall_classification,
        }

    @staticmethod
    def _classify(
        score: int,
    ) -> str:

        if score >= 60:
            return "STRONG"

        if score >= 30:
            return "WATCH"

        if score > -30:
            return "NEUTRAL"

        return "AVOID"