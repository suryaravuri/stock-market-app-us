from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.trading_safety_service import TradingSafetyService
from app.services.paper_trading_service import PaperTradingService
from app.services.trailing_stop_service import TrailingStopService
from app.core.auth_dependencies import get_current_user, require_admin

router = APIRouter(
    prefix="/trading",
    tags=["Trading"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/trailing-stops/sync",
)
def sync_trailing_stops(
    dry_run: bool = Query(
        default=True,
        description="true = only report what would change",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Raise Alpaca stops for open paper positions (profit protection).
    Call with dry_run=false from Cloud Scheduler on Cloud Run."""
    return TrailingStopService.sync(db, dry_run=dry_run)


@router.get(
    "/{symbol}/safety-check",
)
def safety_check(
    symbol: str,
    account_size: float = Query(
        ...,
        gt=0,
    ),
    risk_percent: float = Query(
        default=1.0,
        gt=0,
        le=5,
    ),
    current_daily_pnl: float = Query(
        default=0.0,
    ),
    max_daily_loss_percent: float = Query(
        default=2.0,
        gt=0,
        le=10,
    ),
    mode: str = Query(
        default="PAPER",
    ),
    db: Session = Depends(get_db),
):
    return TradingSafetyService.evaluate(
        db=db,
        symbol=symbol,
        account_size=account_size,
        risk_percent=risk_percent,
        current_daily_pnl=current_daily_pnl,
        max_daily_loss_percent=max_daily_loss_percent,
        mode=mode,
    )

@router.get(
    "/{symbol}/paper-order/preview",
)
def preview_paper_order(
    symbol: str,
    account_size: float = Query(..., gt=0),
    risk_percent: float = Query(default=1.0, gt=0, le=5),
    current_daily_pnl: float = Query(default=0.0),
    max_daily_loss_percent: float = Query(
        default=2.0,
        gt=0,
        le=10,
    ),
    db: Session = Depends(get_db),
):
    return PaperTradingService.preview_order(
        db=db,
        symbol=symbol,
        account_size=account_size,
        risk_percent=risk_percent,
        current_daily_pnl=current_daily_pnl,
        max_daily_loss_percent=max_daily_loss_percent,
    )


@router.post(
    "/{symbol}/paper-order",
)
def submit_paper_order(
    symbol: str,
    account_size: float = Query(..., gt=0),
    risk_percent: float = Query(default=1.0, gt=0, le=5),
    current_daily_pnl: float = Query(default=0.0),
    max_daily_loss_percent: float = Query(default=2.0, gt=0, le=10),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    if current_user.role.upper() != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="ADMIN access required for paper order submission",
        )

    return PaperTradingService.submit_order(
        db=db,
        symbol=symbol,
        account_size=account_size,
        risk_percent=risk_percent,
        current_daily_pnl=current_daily_pnl,
        max_daily_loss_percent=max_daily_loss_percent,
    )