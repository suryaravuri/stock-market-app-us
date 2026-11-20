from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from kiteconnect import exceptions as kite_exceptions
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import AppUser
from app.schemas.zerodha import ZerodhaOrderRequest
from app.services.zerodha_auth_service import ZerodhaAuthService
from app.services.zerodha_order_service import ZerodhaOrderService
from app.services.zerodha_statistics_service import ZerodhaStatisticsService

router = APIRouter(prefix="/zerodha", tags=["Zerodha (real money)"])


def _call(fn):
    try:
        return fn()
    except kite_exceptions.TokenException as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Zerodha login expired: {exc}")
    except kite_exceptions.KiteException as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Zerodha error: {exc}")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/login-url")
def login_url(user: AppUser = Depends(get_current_user)):
    return {"login_url": _call(lambda: ZerodhaAuthService.login_url(user))}


@router.get("/callback", include_in_schema=False)
def callback(
    request_token: str | None = None,
    status_: str | None = Query(default=None, alias="status"),
    state: str | None = None,
    db: Session = Depends(get_db),
):
    target = settings.zerodha_post_login_redirect_url
    if status_ != "success" or not request_token or not state:
        return RedirectResponse(f"{target}?zerodha=failed")
    try:
        ZerodhaAuthService.complete_login(db, request_token, state)
    except (ValueError, kite_exceptions.KiteException):
        return RedirectResponse(f"{target}?zerodha=failed")
    return RedirectResponse(f"{target}?zerodha=connected")


@router.get("/status")
def connection_status(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return ZerodhaAuthService.status(db, user)


@router.post("/disconnect")
def disconnect(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    ZerodhaAuthService.disconnect(db, user)
    return {"connected": False}


@router.post("/orders/preview")
def preview_order(
    req: ZerodhaOrderRequest,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _call(lambda: ZerodhaOrderService.preview(db, user, req.model_dump()))


@router.post("/orders")
def place_order(
    req: ZerodhaOrderRequest,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _call(lambda: ZerodhaOrderService.place(db, user, req.model_dump()))


@router.get("/orders")
def order_history(
    limit: int = Query(default=50, gt=0, le=500),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ZerodhaOrderService.history(db, user, limit)


@router.post("/orders/{kite_order_id}/cancel")
def cancel_order(
    kite_order_id: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _call(lambda: ZerodhaOrderService.cancel(db, user, kite_order_id))


@router.post("/trades/sync")
def sync_trades(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Copy today's fills and order statuses from Zerodha. Kite keeps only today's."""
    return _call(lambda: ZerodhaStatisticsService.sync(db, user))


@router.get("/statistics")
def trade_statistics(
    mode: str = Query(default="LIVE", pattern="^(LIVE|DRY_RUN)$"),
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _call(lambda: ZerodhaStatisticsService.statistics(db, user, mode))
