from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import AppUser
from app.models.watchlist import Watchlist, WatchlistStock
from app.repositories.watchlist_repository import WatchlistRepository
from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistStockCreate,
    WatchlistStockUpdate,
    WatchlistUpdate,
)


class WatchlistService:

    # ============================================================
    # Watchlist CRUD
    # ============================================================

    @staticmethod
    def create_watchlist(
        db: Session,
        watchlist_create: WatchlistCreate,
        current_user: AppUser,
    ) -> Watchlist:

        return WatchlistRepository.create(
            db=db,
            watchlist_create=watchlist_create,
            user_id=current_user.id,
        )

    @staticmethod
    def get_watchlist(
        db: Session,
        watchlist_id: int,
        current_user: AppUser,
    ) -> Watchlist:

        watchlist = WatchlistRepository.find_by_id(
            db=db,
            watchlist_id=watchlist_id,
            user_id=current_user.id,
        )

        if watchlist is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found",
            )

        return watchlist

    @staticmethod
    def get_watchlists(
        db: Session,
        current_user: AppUser,
    ) -> list[Watchlist]:

        return WatchlistRepository.find_all(
            db=db,
            user_id=current_user.id,
        )

    @staticmethod
    def update_watchlist(
        db: Session,
        watchlist_id: int,
        watchlist_update: WatchlistUpdate,
        current_user: AppUser,
    ) -> Watchlist:

        watchlist = WatchlistService.get_watchlist(
            db=db,
            watchlist_id=watchlist_id,
            current_user=current_user,
        )

        return WatchlistRepository.update(
            db=db,
            watchlist=watchlist,
            watchlist_update=watchlist_update,
        )

    @staticmethod
    def delete_watchlist(
        db: Session,
        watchlist_id: int,
        current_user: AppUser,
    ) -> None:

        watchlist = WatchlistService.get_watchlist(
            db=db,
            watchlist_id=watchlist_id,
            current_user=current_user,
        )

        WatchlistRepository.delete(
            db=db,
            watchlist=watchlist,
        )

    # ============================================================
    # Watchlist Stock CRUD
    # ============================================================

    @staticmethod
    def add_stock(
        db: Session,
        watchlist_id: int,
        stock_create: WatchlistStockCreate,
        current_user: AppUser,
    ) -> WatchlistStock:

        # Security boundary:
        # verify that this watchlist belongs to current_user.
        WatchlistService.get_watchlist(
            db=db,
            watchlist_id=watchlist_id,
            current_user=current_user,
        )

        existing = WatchlistRepository.find_stock(
            db=db,
            watchlist_id=watchlist_id,
            stock_id=stock_create.stock_id,
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Stock already exists in watchlist",
            )

        return WatchlistRepository.add_stock(
            db=db,
            watchlist_id=watchlist_id,
            stock_create=stock_create,
        )

    @staticmethod
    def get_watchlist_stocks(
        db: Session,
        watchlist_id: int,
        current_user: AppUser,
    ) -> list[WatchlistStock]:

        # Do not query watchlist_stock until ownership is verified.
        WatchlistService.get_watchlist(
            db=db,
            watchlist_id=watchlist_id,
            current_user=current_user,
        )

        return WatchlistRepository.find_stocks(
            db=db,
            watchlist_id=watchlist_id,
        )

    @staticmethod
    def update_watchlist_stock(
        db: Session,
        watchlist_id: int,
        stock_id: int,
        stock_update: WatchlistStockUpdate,
        current_user: AppUser,
    ) -> WatchlistStock:

        # Verify ownership first.
        WatchlistService.get_watchlist(
            db=db,
            watchlist_id=watchlist_id,
            current_user=current_user,
        )

        watchlist_stock = WatchlistRepository.find_stock(
            db=db,
            watchlist_id=watchlist_id,
            stock_id=stock_id,
        )

        if watchlist_stock is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist stock not found",
            )

        return WatchlistRepository.update_stock(
            db=db,
            watchlist_stock=watchlist_stock,
            stock_update=stock_update,
        )

    @staticmethod
    def remove_stock(
        db: Session,
        watchlist_id: int,
        stock_id: int,
        current_user: AppUser,
    ) -> None:

        # Verify ownership first.
        WatchlistService.get_watchlist(
            db=db,
            watchlist_id=watchlist_id,
            current_user=current_user,
        )

        watchlist_stock = WatchlistRepository.find_stock(
            db=db,
            watchlist_id=watchlist_id,
            stock_id=stock_id,
        )

        if watchlist_stock is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist stock not found",
            )

        WatchlistRepository.remove_stock(
            db=db,
            watchlist_stock=watchlist_stock,
        )