"""Endpoints called by Cloud Scheduler, not by users.

Protected by a shared secret in the X-Job-Token header (JOB_TRIGGER_TOKEN,
stored in Secret Manager). If the token isn't configured, the endpoint is
disabled entirely.
"""
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.trading_cycle_service import TradingCycleService

router = APIRouter(prefix="/jobs", tags=["Scheduled Jobs"])


def require_job_token(x_job_token: str | None = Header(default=None)) -> None:
    expected = settings.job_trigger_token
    if not expected:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Scheduled jobs are disabled")
    if not x_job_token or not hmac.compare_digest(x_job_token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid job token")


@router.post("/trading-cycle", dependencies=[Depends(require_job_token)])
def trading_cycle(
    market: str | None = Query(default=None, pattern="^(US|IN)$"),
    force: bool = Query(default=False, description="Run even if the market is closed (testing)"),
    db: Session = Depends(get_db),
):
    return TradingCycleService.run(db=db, market=market, force=force)
