"""Which market this deployment serves.

The US and India apps live in separate repositories with separate databases.
APP_MARKET makes each one behave as a single-market app:

  US   - Alpaca only: NSE/BSE stocks are never synced, scanned or traded,
         and the Zerodha API routes are not loaded.
  IN   - Zerodha only (India repository).
  ALL  - old combined behaviour.
"""
from __future__ import annotations

from app.core.config import settings
from app.market.sessions import is_indian_exchange


def app_market() -> str:
    value = (getattr(settings, "app_market", "US") or "US").strip().upper()
    return value if value in ("US", "IN", "ALL") else "US"


def enabled_markets() -> set[str]:
    market = app_market()
    return {"US", "IN"} if market == "ALL" else {market}


def exchange_allowed(exchange: str | None) -> bool:
    """True if a stock on this exchange belongs to this deployment."""
    market = app_market()
    if market == "ALL":
        return True
    indian = is_indian_exchange(exchange)
    return indian if market == "IN" else not indian
