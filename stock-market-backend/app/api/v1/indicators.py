from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.indicator import IndicatorResponse
from app.schemas.market import MarketTimeframe
from app.services.indicator_service import IndicatorService
from app.core.auth_dependencies import get_current_user

router = APIRouter(
    prefix="/indicators",
    tags=["Indicators"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/{symbol}",
    response_model=IndicatorResponse,
    responses={
        404: {
            "description": "Stock or candle data not found"
        }
    },
)
def get_indicators(
    symbol: str,
    timeframe: MarketTimeframe = Query(
        default=MarketTimeframe.FIFTEEN_MINUTES
    ),
    db: Session = Depends(get_db),
):
    try:
        return IndicatorService.get_indicators(
            db=db,
            symbol=symbol,
            timeframe=timeframe,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc