from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.models.user import AppUser
from app.schemas.market import MarketTimeframe
from app.schemas.monitor_status import MonitorStatusResponse
from app.services.validation_market_data_service import (
    ValidationMarketDataService,
)

router = APIRouter(
    prefix="/watchlists",
    tags=["Watchlist Monitor"],
)


@router.get(
    "/{watchlist_id}/monitor-status",
    response_model=MonitorStatusResponse,
)
def get_monitor_status(
    watchlist_id: int,
    timeframe: MarketTimeframe = MarketTimeframe.FIFTEEN_MINUTES,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        return ValidationMarketDataService.monitor_watchlist(
            db=db,
            watchlist_id=watchlist_id,
            timeframe=timeframe,
            current_user=current_user,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc