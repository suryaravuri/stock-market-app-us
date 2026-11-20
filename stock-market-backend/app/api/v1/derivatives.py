"""Read-only Options and Futures screens. No orders are placed here."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from kiteconnect import exceptions as kite_exceptions
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.models.user import AppUser
from app.services.futures_watch_service import FuturesWatchService
from app.services.options_explorer_service import OptionsExplorerService

router = APIRouter(tags=["Options & Futures (analysis only)"])


@router.get("/options/analysis/{symbol}")
def options_analysis(
    symbol: str,
    option_type: str = Query(default="CALL", pattern="^(CALL|PUT|call|put)$"),
    min_dte: int = Query(default=7, ge=0, le=365),
    max_dte: int = Query(default=45, ge=1, le=730),
    strike_range_percent: float = Query(default=10.0, gt=0, le=50),
    db: Session = Depends(get_db),
    _user: AppUser = Depends(get_current_user),
):
    try:
        return OptionsExplorerService.analyze(
            db,
            symbol,
            option_type=option_type,
            min_dte=min_dte,
            max_dte=max_dte,
            strike_range_percent=strike_range_percent,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/futures/watch")
def futures_watch(
    underlyings: str = Query(default="NIFTY,BANKNIFTY,GOLDM,CRUDEOILM",
                             description="Comma-separated, e.g. NIFTY,BANKNIFTY,GOLDM"),
    contracts: int = Query(default=2, ge=1, le=3),
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    try:
        return FuturesWatchService.watch(db, user, underlyings.split(","), contracts)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    except kite_exceptions.TokenException as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Zerodha login expired: {exc}")
    except kite_exceptions.KiteException as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Zerodha error: {exc}")
