from sqlalchemy import select

from sqlalchemy.orm import Session, selectinload

from app.models.watchlist import Watchlist, WatchlistStock
from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistStockCreate,
    WatchlistStockUpdate,
    WatchlistUpdate,
)


class WatchlistRepository:

    @staticmethod
    def create(
            db: Session,
            watchlist_create: WatchlistCreate,
            user_id: int,
    ) -> Watchlist:

        watchlist = Watchlist(
            user_id=user_id,
            **watchlist_create.model_dump(),
        )

        db.add(watchlist)
        db.commit()
        db.refresh(watchlist)

        return watchlist

    @staticmethod
    def find_by_id(
            db: Session,
            watchlist_id: int,
            user_id: int,
    ) -> Watchlist | None:

        stmt = select(Watchlist).where(
            Watchlist.watchlist_id == watchlist_id,
            Watchlist.user_id == user_id,
        )

        return db.scalar(stmt)

    @staticmethod
    def find_all(
            db: Session,
            user_id: int,
    ) -> list[Watchlist]:

        stmt = (
            select(Watchlist)
            .where(
                Watchlist.user_id == user_id
            )
            .order_by(
                Watchlist.name.asc()
            )
        )

        return list(
            db.scalars(stmt).all()
        )

    @staticmethod
    def update(
        db: Session,
        watchlist: Watchlist,
        watchlist_update: WatchlistUpdate,
    ) -> Watchlist:

        update_data = watchlist_update.model_dump(
            exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(watchlist, field, value)

        db.commit()
        db.refresh(watchlist)

        return watchlist

    @staticmethod
    def find_stock(
        db: Session,
        watchlist_id: int,
        stock_id: int,
    ) -> WatchlistStock | None:

        stmt = (
            select(WatchlistStock)
            .options(
                selectinload(WatchlistStock.stock)
            )
            .where(
                WatchlistStock.watchlist_id == watchlist_id,
                WatchlistStock.stock_id == stock_id,
            )
        )

        return db.scalar(stmt)

    @staticmethod
    def add_stock(
        db: Session,
        watchlist_id: int,
        stock_create: WatchlistStockCreate,
    ) -> WatchlistStock:

        watchlist_stock = WatchlistStock(
            watchlist_id=watchlist_id,
            **stock_create.model_dump(),
        )

        db.add(watchlist_stock)
        db.commit()
        db.refresh(watchlist_stock)

        return watchlist_stock

    @staticmethod
    def find_stocks(
        db: Session,
        watchlist_id: int,
    ) -> list[WatchlistStock]:

        stmt = (
            select(WatchlistStock)
            .options(
                selectinload(WatchlistStock.stock)
            )
            .where(
                WatchlistStock.watchlist_id == watchlist_id
            )
            .order_by(
                WatchlistStock.priority.desc()
            )
        )

        return list(
            db.scalars(stmt).all()
        )

    @staticmethod
    def update_stock(
        db: Session,
        watchlist_stock: WatchlistStock,
        stock_update: WatchlistStockUpdate,
    ) -> WatchlistStock:

        update_data = stock_update.model_dump(
            exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(watchlist_stock, field, value)

        db.commit()
        db.refresh(watchlist_stock)

        return watchlist_stock

    @staticmethod
    def remove_stock(
        db: Session,
        watchlist_stock: WatchlistStock,
    ) -> None:

        db.delete(watchlist_stock)
        db.commit()

    @staticmethod
    def delete(
        db: Session,
        watchlist: Watchlist,
    ) -> None:
        db.delete(watchlist)
        db.commit()