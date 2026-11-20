from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.models.user import AppUser
from app.schemas.watchlist import (
    WatchlistStockCreate,
    WatchlistStockResponse,
    WatchlistStockUpdate,
)
from app.services.watchlist_service import WatchlistService


router = APIRouter(
    prefix="/watchlists/{watchlist_id}/stocks",
    tags=["Watchlist Stocks"],
)


@router.post(
    "",
    response_model=WatchlistStockResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_stock(
    watchlist_id: int,
    request: WatchlistStockCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return WatchlistService.add_stock(
        db,
        watchlist_id,
        request,
        current_user,
    )


@router.get(
    "",
    response_model=list[WatchlistStockResponse],
)
def get_stocks(
    watchlist_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return WatchlistService.get_watchlist_stocks(
        db,
        watchlist_id,
        current_user,
    )


@router.put(
    "/{stock_id}",
    response_model=WatchlistStockResponse,
)
def update_stock(
    watchlist_id: int,
    stock_id: int,
    request: WatchlistStockUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return WatchlistService.update_watchlist_stock(
        db,
        watchlist_id,
        stock_id,
        request,
        current_user,
    )


@router.delete(
    "/{stock_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_stock(
    watchlist_id: int,
    stock_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    WatchlistService.remove_stock(
        db,
        watchlist_id,
        stock_id,
        current_user,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )