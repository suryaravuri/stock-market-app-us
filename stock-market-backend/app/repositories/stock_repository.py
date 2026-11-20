from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.stock import Stock
from app.schemas.stock import StockCreate, StockUpdate


class StockRepository:

    @staticmethod
    def create(
            db: Session,
            stock_create: StockCreate
    ) -> Stock:

        stock = Stock(
            **stock_create.model_dump()
        )

        db.add(stock)
        db.commit()
        db.refresh(stock)

        return stock

    @staticmethod
    def find_by_symbol(
            db: Session,
            symbol: str
    ) -> Stock | None:

        stmt = select(Stock).where(
            Stock.symbol == symbol.upper()
        )

        return db.scalar(stmt)

    @staticmethod
    def find_all(
            db: Session
    ) -> list[Stock]:

        stmt = select(Stock).order_by(
            Stock.symbol.asc()
        )

        return list(
            db.scalars(stmt).all()
        )

    @staticmethod
    def update(
            db: Session,
            stock: Stock,
            stock_update: StockUpdate
    ) -> Stock:

        update_data = stock_update.model_dump(
            exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(stock, field, value)

        db.commit()
        db.refresh(stock)

        return stock

    @staticmethod
    def find_by_id(
            db: Session,
            stock_id: int,
    ) -> Stock | None:

        stmt = select(Stock).where(
            Stock.stock_id == stock_id
        )

        return db.scalar(stmt)

    @staticmethod
    def find_existing_symbols(
            db: Session,
            symbols: list[str],
    ) -> set[str]:

        if not symbols:
            return set()

        normalized_symbols = [
            symbol.strip().upper()
            for symbol in symbols
        ]

        stmt = select(Stock.symbol).where(
            Stock.symbol.in_(normalized_symbols)
        )

        return {
            symbol.upper()
            for symbol in db.scalars(stmt).all()
        }

    @staticmethod
    def create_bulk(
            db: Session,
            stock_creates: list[StockCreate],
    ) -> list[Stock]:

        stocks = [
            Stock(**stock_create.model_dump())
            for stock_create in stock_creates
        ]

        if not stocks:
            return []

        try:
            db.add_all(stocks)
            db.commit()

            for stock in stocks:
                db.refresh(stock)

            return stocks

        except Exception:
            db.rollback()
            raise
