import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.auth_dependencies import bearer_scheme, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import AppUser
from app.services.breakout_diagnostics_service import BreakoutDiagnosticsService
from app.services.decision_log import DecisionLog
from app.services.trading_readiness_service import TradingReadinessService

router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])


def user_or_job_token(
    x_job_token: str | None = Header(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> None:
    """Allow the UI (JWT) or PowerShell with the same X-Job-Token header
    used for /jobs/trading-cycle. Read-only endpoints only."""
    expected = settings.job_trigger_token
    if x_job_token and expected and hmac.compare_digest(x_job_token, expected):
        return None
    get_current_user(credentials=credentials, db=db)
    return None


@router.get("/breakout/{symbol}")
def breakout_diagnostics(
    symbol: str,
    rows: int = Query(default=30, ge=5, le=200),
    db: Session = Depends(get_db),
    _user: AppUser = Depends(get_current_user),
):
    try:
        return BreakoutDiagnosticsService.analyze(db, symbol, rows)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/trading-readiness")
def trading_readiness(
    check_broker: bool = Query(default=True),
    db: Session = Depends(get_db),
    _auth: None = Depends(user_or_job_token),
):
    """Every gate an automatic paper order must pass, with PASS/WARN/FAIL."""
    return TradingReadinessService.evaluate(db, check_broker=check_broker)


@router.post("/test-alert")
def test_alert(_auth: None = Depends(user_or_job_token)):
    """Send a test Telegram message (checks TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)."""
    from app.services import alert_service

    if not alert_service.enabled():
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Alerts are off: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env and restart")
    ok = alert_service.send("👋 Test alert from your trading bot", wait=True)
    if not ok:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Telegram refused the message - see logs/trading.log")
    return {"sent": True}


@router.get("/holdings-guard")
def holdings_guard_status(_auth: None = Depends(user_or_job_token)):
    """Which holdings are guarded and their state (guarding / waiting to buy back)."""
    from app.services.holdings_guard_service import HoldingsGuardService

    return HoldingsGuardService.status()


@router.get("/decisions")
def trading_decisions(
    symbol: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=3000),
    only_blocked: bool = Query(default=False),
    _auth: None = Depends(user_or_job_token),
):
    """Per-stock 'bought / why not' records from recent scans (newest first)."""
    items = DecisionLog.recent(symbol=symbol, limit=limit, only_blocked=only_blocked)
    return {
        "count": len(items),
        "blockers": DecisionLog.blocker_counts(items),
        "decisions": items,
    }
