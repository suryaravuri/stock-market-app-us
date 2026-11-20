from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.stock import Stock
from app.repositories.stock_repository import StockRepository
from app.schemas.stock import (
    StockBulkError,
    StockBulkResponse,
    StockCreate,
    StockUpdate,
)


class StockService:

    @staticmethod
    def _check_market(stock_create: StockCreate) -> None:
        """Refuse stocks from the other market (APP_MARKET)."""
        from app.market.app_market import app_market, exchange_allowed

        if not exchange_allowed(getattr(stock_create, "exchange", None)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"'{stock_create.symbol}' ({stock_create.exchange}) belongs to the other "
                    f"market; this app serves {app_market()} only"
                ),
            )

    @staticmethod
    def create_stock(
        db: Session,
        stock_create: StockCreate,
    ) -> Stock:

        StockService._check_market(stock_create)

        existing_stock = StockRepository.find_by_symbol(
            db,
            stock_create.symbol,
        )

        if existing_stock:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock '{stock_create.symbol}' already exists",
            )

        return StockRepository.create(
            db,
            stock_create,
        )

    @staticmethod
    def get_stock(
        db: Session,
        symbol: str,
    ) -> Stock:

        symbol = symbol.strip().upper()

        stock = StockRepository.find_by_symbol(
            db,
            symbol,
        )

        if stock is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stock '{symbol}' not found",
            )

        return stock

    @staticmethod
    def get_stocks(
        db: Session,
    ) -> list[Stock]:

        return StockRepository.find_all(db)

    @staticmethod
    def update_stock(
        db: Session,
        symbol: str,
        stock_update: StockUpdate,
    ) -> Stock:

        stock = StockService.get_stock(
            db,
            symbol,
        )

        return StockRepository.update(
            db,
            stock,
            stock_update,
        )

    @staticmethod
    def deactivate_stock(
        db: Session,
        symbol: str,
    ) -> None:
        stock = StockService.get_stock(
            db,
            symbol,
        )

        stock.active = False

        db.commit()

    @staticmethod
    def create_stocks_bulk(
        db: Session,
        stock_creates: list[StockCreate],
    ) -> StockBulkResponse:

        total = len(stock_creates)

        if total == 0:
            return StockBulkResponse(
                total=0,
                inserted=0,
                already_exists=0,
                failed=0,
            )

        existing_symbols = StockRepository.find_existing_symbols(
            db,
            [stock.symbol for stock in stock_creates],
        )

        stocks_to_insert: list[StockCreate] = []

        inserted_symbols: list[str] = []
        skipped_existing_symbols: list[str] = []
        errors: list[StockBulkError] = []

        #
        # Prevent duplicates inside the uploaded file itself.
        #
        seen_symbols: set[str] = set()

        for row_number, stock_create in enumerate(
            stock_creates,
            start=2,
        ):
            symbol = stock_create.symbol.strip().upper()

            if symbol in existing_symbols:
                skipped_existing_symbols.append(symbol)
                continue

            if symbol in seen_symbols:
                errors.append(
                    StockBulkError(
                        row=row_number,
                        symbol=symbol,
                        message=(
                            "Duplicate symbol in bulk import"
                        ),
                    )
                )
                continue

            from app.market.app_market import app_market, exchange_allowed

            if not exchange_allowed(getattr(stock_create, "exchange", None)):
                errors.append(
                    StockBulkError(
                        row=row_number,
                        symbol=symbol,
                        message=f"Other market ({stock_create.exchange}); this app serves {app_market()} only",
                    )
                )
                continue

            seen_symbols.add(symbol)
            stocks_to_insert.append(stock_create)

        if stocks_to_insert:
            created_stocks = StockRepository.create_bulk(
                db,
                stocks_to_insert,
            )

            inserted_symbols = [
                stock.symbol
                for stock in created_stocks
            ]

        return StockBulkResponse(
            total=total,
            inserted=len(inserted_symbols),
            already_exists=len(skipped_existing_symbols),
            failed=len(errors),
            inserted_symbols=inserted_symbols,
            existing_symbols=skipped_existing_symbols,
            errors=errors,
        )