from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.models.user import AppUser
from app.services.performance_service import PerformanceService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/sector-heatmap")
def sector_heatmap(
    period: str = Query(default="1D", pattern="^(1D|1W|1M|3M|6M)$"),
    watchlist_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: AppUser = Depends(get_current_user),
):
    """% change per stock over the period, grouped by sector."""
    return PerformanceService.sector_heatmap(db, period, watchlist_id)


@router.get("/pnl")
def pnl_report(
    group: str = Query(default="day", pattern="^(day|week|month)$"),
    range: str = Query(default="3M", pattern="^(1M|3M|6M|1A)$"),  # noqa: A002
    _user: AppUser = Depends(get_current_user),
):
    """Alpaca paper P&L grouped by day / week / month."""
    try:
        return PerformanceService.pnl_report(group, range)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    except Exception as exc:  # noqa: BLE001 - broker errors
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Alpaca: {exc}")
