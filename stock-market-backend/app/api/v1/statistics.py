from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.performance_statistics import (
    PerformanceStatisticsResponse,
)
from app.services.performance_statistics_service import (
    PerformanceStatisticsService,
)

from app.models.user import AppUser
from app.services.watchlist_service import WatchlistService

from app.core.auth_dependencies import get_current_user

router = APIRouter(
    prefix="/statistics",
    tags=["Statistics"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/performance",
    response_model=PerformanceStatisticsResponse,
)
def get_performance_statistics(
    start_date: date = Query(...),
    end_date: date = Query(...),
    watchlist_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        if watchlist_id is not None:
            WatchlistService.get_watchlist(
                db=db,
                watchlist_id=watchlist_id,
                current_user=current_user,
            )

        return PerformanceStatisticsService.get_performance(
            db=db,
            start_date=start_date,
            end_date=end_date,
            watchlist_id=watchlist_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )(exc)