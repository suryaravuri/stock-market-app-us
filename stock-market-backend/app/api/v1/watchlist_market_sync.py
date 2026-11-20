from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.models.user import AppUser
from app.services.watchlist_market_sync_service import (
    WatchlistMarketSyncService,
)


router = APIRouter(
    prefix="/watchlists",
    tags=["Watchlist Market Data"],
)


@router.post(
    "/{watchlist_id}/market-data/sync",
)
def sync_watchlist_market_data(
    watchlist_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return WatchlistMarketSyncService.sync(
        db=db,
        watchlist_id=watchlist_id,
        current_user=current_user,
    )