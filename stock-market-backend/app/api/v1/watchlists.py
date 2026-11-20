from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.database import get_db
from app.models.user import AppUser
from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistResponse,
    WatchlistUpdate,
)
from app.services.watchlist_service import WatchlistService


router = APIRouter(
    prefix="/watchlists",
    tags=["Watchlists"],
)


@router.post(
    "",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_watchlist(
    request: WatchlistCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return WatchlistService.create_watchlist(
        db,
        request,
        current_user,
    )


@router.get(
    "",
    response_model=list[WatchlistResponse],
)
def get_watchlists(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return WatchlistService.get_watchlists(
        db,
        current_user,
    )


@router.get(
    "/{watchlist_id}",
    response_model=WatchlistResponse,
)
def get_watchlist(
    watchlist_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return WatchlistService.get_watchlist(
        db,
        watchlist_id,
        current_user,
    )


@router.put(
    "/{watchlist_id}",
    response_model=WatchlistResponse,
)
def update_watchlist(
    watchlist_id: int,
    request: WatchlistUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return WatchlistService.update_watchlist(
        db,
        watchlist_id,
        request,
        current_user,
    )


@router.delete(
    "/{watchlist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_watchlist(
    watchlist_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    WatchlistService.delete_watchlist(
        db,
        watchlist_id,
        current_user,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )