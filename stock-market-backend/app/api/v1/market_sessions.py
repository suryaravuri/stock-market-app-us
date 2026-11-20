"""Market open/closed status for the US and India tabs."""
from fastapi import APIRouter, Depends

from app.core.auth_dependencies import get_current_user
from app.market.sessions import MARKET_SESSIONS, market_status

router = APIRouter(
    prefix="/markets",
    tags=["Market Sessions"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/status")
def markets_status():
    """Both markets in one call: {"US": {...}, "IN": {...}}."""
    return {code: market_status(session) for code, session in MARKET_SESSIONS.items()}