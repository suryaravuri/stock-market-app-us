from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.validation_run import ValidationRunCreateRequest, ValidationRunResponse, ValidationProgressResponse
from app.schemas.market import MarketTimeframe
from app.schemas.validation_market_data import ValidationMarketDataResponse
from app.schemas.validation_watchlist_scan import ValidationWatchlistScanResponse
from app.services.validation_run_service import ValidationRunService
from app.services.validation_market_data_service import ValidationMarketDataService
from app.services.validation_watchlist_scan_service import ValidationWatchlistScanService
from app.core.auth_dependencies import get_current_user

router = APIRouter(
    prefix="/analysis/validation-runs",
    tags=["Analysis Validation"],
    dependencies=[Depends(get_current_user)],
)


def _call(fn):
    try:
        return fn()
    except ValueError as exc:
        message = str(exc)
        is_conflict = any(
            token in message.upper()
            for token in ("ACTIVE", "ALREADY", "BASELINE", "MISMATCH")
        )

        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
                if is_conflict
                else status.HTTP_404_NOT_FOUND
            ),
            detail=message,
        )


@router.post("", response_model=ValidationRunResponse, status_code=status.HTTP_201_CREATED)
def create_validation_run(req: ValidationRunCreateRequest, db: Session = Depends(get_db)):
    return _call(lambda: ValidationRunService.create(db, req.strategy_version))


@router.get("/active", response_model=ValidationRunResponse)
def active_validation_run(db: Session = Depends(get_db)):
    return _call(lambda: ValidationRunService.get_active(db))


@router.get("/{validation_run_id}", response_model=ValidationRunResponse)
def get_validation_run(validation_run_id: int, db: Session = Depends(get_db)):
    return _call(lambda: ValidationRunService.get(db, validation_run_id))


@router.get("/{validation_run_id}/progress", response_model=ValidationProgressResponse)
def validation_progress(validation_run_id: int, db: Session = Depends(get_db)):
    return _call(lambda: ValidationRunService.progress(db, validation_run_id))


@router.get("/{validation_run_id}/market-data-validation", response_model=ValidationMarketDataResponse)
def validation_market_data(
        validation_run_id: int,
        watchlist_id: int = Query(..., gt=0),
        timeframe: MarketTimeframe = MarketTimeframe.FIFTEEN_MINUTES,
        db: Session = Depends(get_db),
):
    return _call(
        lambda: ValidationMarketDataService.validate_watchlist(
            db=db,
            validation_run_id=validation_run_id,
            watchlist_id=watchlist_id,
            timeframe=timeframe,
        )
    )


@router.post("/{validation_run_id}/watchlist-scan", response_model=ValidationWatchlistScanResponse)
def validation_watchlist_scan(
        validation_run_id: int,
        watchlist_id: int = 1,
        timeframe: MarketTimeframe = MarketTimeframe.FIFTEEN_MINUTES,
        db: Session = Depends(get_db),
):
    return _call(
        lambda: ValidationWatchlistScanService.scan(
            db=db,
            validation_run_id=validation_run_id,
            watchlist_id=watchlist_id,
            timeframe=timeframe,
        )
    )


@router.post("/{validation_run_id}/complete", response_model=ValidationRunResponse)
def complete_validation_run(validation_run_id: int, db: Session = Depends(get_db)):
    return _call(lambda: ValidationRunService.complete(db, validation_run_id))
