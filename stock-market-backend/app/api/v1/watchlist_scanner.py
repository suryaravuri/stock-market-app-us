from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.models.user import AppUser
from app.schemas.watchlist_scanner import WatchlistScanResponse
from app.services.watchlist_scanner_service import WatchlistScannerService


router = APIRouter(
    prefix="/watchlists",
    tags=["Watchlist Scanner"],
)


@router.get(
    "/{watchlist_id}/scan",
    response_model=WatchlistScanResponse,
)
def scan_watchlist(
    watchlist_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return WatchlistScannerService.scan(
        db=db,
        watchlist_id=watchlist_id,
        current_user=current_user,
    )