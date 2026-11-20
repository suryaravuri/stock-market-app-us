from typing import Literal

from pydantic import BaseModel, Field


class ZerodhaOrderRequest(BaseModel):
    exchange: Literal["NSE", "BSE"] = "NSE"
    tradingsymbol: str = Field(..., min_length=1, max_length=40, examples=["INFY"])
    side: Literal["BUY", "SELL"]
    quantity: int = Field(..., gt=0)
    limit_price: float = Field(..., gt=0)
    product: Literal["CNC", "MIS"] = "CNC"
