from datetime import datetime

from pydantic import BaseModel


class OpportunityReasonResponse(BaseModel):
    code: str
    description: str
    score: int


class OpportunityResponse(BaseModel):
    symbol: str
    timeframe: str
    timestamp: datetime

    current_price: float

    score: int
    classification: str

    nearest_support: float | None
    nearest_resistance: float | None

    reasons: list[OpportunityReasonResponse]