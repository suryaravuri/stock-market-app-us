"""Alerts list (for the UI) and the TradingView webhook receiver."""
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.models.user import AppUser
from app.services.market_alert_service import MarketAlertService

router = APIRouter(tags=["Alerts"])


@router.get("/alerts")
def list_alerts(
    limit: int = Query(default=50, ge=1, le=500),
    source: str | None = Query(default=None, pattern="^(EARLY_BREAKOUT|TRADINGVIEW)$"),
    db: Session = Depends(get_db),
    _user: AppUser = Depends(get_current_user),
):
    return MarketAlertService.list(db, limit, source)


@router.post("/webhooks/tradingview")
def tradingview_webhook(body: dict = Body(...), db: Session = Depends(get_db)):
    """Called by TradingView. TradingView can't send custom headers, so the
    shared secret travels in the JSON body ("secret")."""
    try:
        return MarketAlertService.record_tradingview(db, body)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
