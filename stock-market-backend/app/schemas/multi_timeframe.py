from pydantic import BaseModel


class TimeframeOpportunityResponse(BaseModel):
    score: int
    classification: str
    current_price: float
    nearest_support: float | None
    nearest_resistance: float | None


class MultiTimeframeResponse(BaseModel):
    symbol: str
    timeframes: dict[
        str,
        TimeframeOpportunityResponse,
    ]

    overall_score: int
    overall_classification: str