from fastapi import (
    APIRouter,
    Depends,
    File,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.stock import (
    StockBulkCreate,
    StockBulkResponse,
    StockCreate,
    StockResponse,
    StockUpdate,
)
from app.services.stock_service import StockService
from app.core.auth_dependencies import get_current_user, require_admin
import csv
import io

from pydantic import ValidationError

import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/stocks",
    tags=["Stocks"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "",
    response_model=StockResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_stock(
        stock_create: StockCreate,
        db: Session = Depends(get_db),
        _admin=Depends(require_admin),
):
    return StockService.create_stock(
        db,
        stock_create,
    )


@router.get(
    "",
    response_model=list[StockResponse],
)
def get_stocks(
        db: Session = Depends(get_db),
):
    return StockService.get_stocks(db)


@router.get(
    "/{symbol}",
    response_model=StockResponse,
)
def get_stock(
        symbol: str,
        db: Session = Depends(get_db),
):
    return StockService.get_stock(
        db,
        symbol,
    )


@router.put(
    "/{symbol}",
    response_model=StockResponse,
)
def update_stock(
        symbol: str,
        stock_update: StockUpdate,
        db: Session = Depends(get_db),
        _admin=Depends(require_admin),
):
    return StockService.update_stock(
        db,
        symbol,
        stock_update,
    )


@router.delete(
    "/{symbol}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_stock(
        symbol: str,
        db: Session = Depends(get_db),
        _admin=Depends(require_admin),
) -> None:
    StockService.deactivate_stock(
        db,
        symbol,
    )


@router.post(
    "/bulk",
    response_model=StockBulkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_stocks_bulk(
        bulk_create: StockBulkCreate,
        db: Session = Depends(get_db),
        _admin=Depends(require_admin),
):
    return StockService.create_stocks_bulk(
        db,
        bulk_create.stocks,
    )


@router.post(
    "/bulk-upload",
    response_model=StockBulkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def bulk_upload_stocks(
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        _admin=Depends(require_admin),
):
    logger.info(
        "Stock bulk upload started: filename=%s",
        file.filename,
    )

    if not file.filename:
        return StockBulkResponse(
            total=0,
            inserted=0,
            already_exists=0,
            failed=1,
            errors=[
                {
                    "row": 0,
                    "symbol": None,
                    "message": "CSV file name is missing",
                }
            ],
        )

    if not file.filename.lower().endswith(".csv"):
        return StockBulkResponse(
            total=0,
            inserted=0,
            already_exists=0,
            failed=1,
            errors=[
                {
                    "row": 0,
                    "symbol": None,
                    "message": "Only CSV files are supported",
                }
            ],
        )

    contents = await file.read()

    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        return StockBulkResponse(
            total=0,
            inserted=0,
            already_exists=0,
            failed=1,
            errors=[
                {
                    "row": 0,
                    "symbol": None,
                    "message": "CSV file must use UTF-8 encoding",
                }
            ],
        )

    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        return StockBulkResponse(
            total=0,
            inserted=0,
            already_exists=0,
            failed=1,
            errors=[
                {
                    "row": 1,
                    "symbol": None,
                    "message": "CSV header is missing",
                }
            ],
        )

    headers = {
        header.strip().lower()
        for header in reader.fieldnames
        if header
    }



    required_headers = {
        "symbol",
        "company_name",
        "exchange",
        "asset_type",
        "sector",
        "industry",
    }

    missing_headers = required_headers - headers

    if missing_headers:
        return StockBulkResponse(
            total=0,
            inserted=0,
            already_exists=0,
            failed=1,
            errors=[
                {
                    "row": 1,
                    "symbol": None,
                    "message": (
                            "Missing required CSV columns: "
                            + ", ".join(sorted(missing_headers))
                    ),
                }
            ],
        )

    valid_stocks: list[StockCreate] = []
    parsing_errors = []

    for row_number, row in enumerate(reader, start=2):
        try:
            stock = StockCreate(
                symbol=(row.get("symbol") or "").strip(),
                company_name=(
                                     row.get("company_name") or ""
                             ).strip() or None,
                exchange=(
                                 row.get("exchange") or ""
                         ).strip() or None,
                asset_type=(
                        row.get("asset_type") or "STOCK"
                ).strip(),
                sector=(
                               row.get("sector") or ""
                       ).strip() or None,
                industry=(
                                 row.get("industry") or ""
                         ).strip() or None,
                tradable=False,
                active=True,
            )

            valid_stocks.append(stock)

        except ValidationError as exc:
            symbol = (
                             row.get("symbol") or ""
                     ).strip().upper() or None

            message = "; ".join(
                error["msg"]
                for error in exc.errors()
            )

            parsing_errors.append(
                {
                    "row": row_number,
                    "symbol": symbol,
                    "message": message,
                }
            )

    result = StockService.create_stocks_bulk(
        db,
        valid_stocks,
    )

    result.total += len(parsing_errors)
    result.failed += len(parsing_errors)

    logger.info(
        "Stock bulk upload parsed: filename=%s valid_rows=%d parsing_errors=%d",
        file.filename,
        len(valid_stocks),
        len(parsing_errors),
    )

    for error in parsing_errors:
        result.errors.append(error)

    logger.info(
        "Stock bulk upload completed: filename=%s total=%d inserted=%d "
        "already_exists=%d failed=%d",
        file.filename,
        result.total,
        result.inserted,
        result.already_exists,
        result.failed,
    )

    return result
