from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user, require_admin


from app.schemas.market import (
    MarketBarResponse,
    MarketSyncResponse,
    MarketTimeframe,
)


from app.core.database import get_db

from app.services.market_service import MarketService
from app.services.zerodha_auth_service import ZerodhaAuthService



router = APIRouter(
    prefix="/market",
    tags=["Market Data"],
    dependencies=[Depends(get_current_user)],
)

@router.get(
    "/{symbol}/bars",
    response_model=list[MarketBarResponse],
)
def get_market_bars(
    symbol: str,
    timeframe: MarketTimeframe = Query(
        default=MarketTimeframe.ONE_DAY,
    ),
    days: int = Query(
        default=30,
        ge=1,
        le=365,
    ),
):
    service = MarketService()

    return service.get_bars(
        symbol=symbol,
        timeframe=timeframe,
        days=days,
    )

@router.post(
    "/{symbol}/bars/sync",
    response_model=MarketSyncResponse,
)
def sync_market_bars(
    symbol: str,
    timeframe: MarketTimeframe = Query(
        default=MarketTimeframe.ONE_DAY,
    ),
    days: int = Query(
        default=30,
        ge=1,
        le=365,
    ),
    db: Session = Depends(get_db),
    admin = Depends(require_admin),
):
    zerodha_client = None
    if ZerodhaAuthService.get_active_session(db, admin) is not None:
        zerodha_client, _ = ZerodhaAuthService.client_for(db, admin)

    service = MarketService(zerodha_client=zerodha_client)

    try:
        return service.sync_bars(
            db=db,
            symbol=symbol,
            timeframe=timeframe,
            days=days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))