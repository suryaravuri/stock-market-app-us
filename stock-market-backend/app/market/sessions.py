"""Exchange trading sessions.

Every place that asks "is this candle inside regular trading hours?" or
"which calendar day does this candle belong to?" must use the session of the
stock's own exchange. US stocks keep the original New York session; NSE/BSE
stocks use Indian Standard Time.

Indian stocks are stored with a Yahoo-style suffix so they can never collide
with a US ticker of the same name (INFY on NYSE is the Infosys ADR):
    RELIANCE.NS  -> exchange NSE, broker symbol RELIANCE
    RELIANCE.BO  -> exchange BSE, broker symbol RELIANCE
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class MarketSession:
    code: str
    timezone_name: str
    open: time
    close: time
    calendar_code: str

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    def local(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(self.tz)

    def is_regular(self, value: datetime) -> bool:
        """Candle START time is inside Mon-Fri regular hours (close exclusive)."""
        local = self.local(value)
        clock = local.time().replace(tzinfo=None)
        return local.weekday() < 5 and self.open <= clock < self.close

    def is_session_day(self, day: date) -> bool:
        """Exchange calendar check (weekends and published holidays)."""
        return _calendar(self.calendar_code).is_session(day.isoformat())

    def close_time_on(self, day: date) -> time:
        """Actual local close for a session day.

        Normally self.close, but earlier on half days (US: day after
        Thanksgiving, Christmas Eve). Falls back to self.close if the
        calendar can't answer.
        """
        try:
            close_utc = _calendar(self.calendar_code).session_close(day.isoformat())
            return close_utc.tz_convert(self.timezone_name).time().replace(tzinfo=None)
        except Exception:  # noqa: BLE001
            return self.close


@lru_cache(maxsize=None)
def _calendar(code: str):
    import exchange_calendars as xcals

    return xcals.get_calendar(code)


US_SESSION = MarketSession(
    code="US",
    timezone_name="America/New_York",
    open=time(9, 30),
    close=time(16, 0),
    calendar_code="XNYS",
)

INDIA_SESSION = MarketSession(
    code="IN",
    timezone_name="Asia/Kolkata",
    open=time(9, 15),
    close=time(15, 30),
    # exchange_calendars models BSE; NSE observes the same equity holidays.
    calendar_code="XBOM",
)

INDIAN_EXCHANGES = {"NSE", "BSE"}
INDIAN_SUFFIXES = {".NS": "NSE", ".BO": "BSE"}


def is_indian_exchange(exchange: str | None) -> bool:
    return (exchange or "").strip().upper() in INDIAN_EXCHANGES


def session_for_exchange(exchange: str | None) -> MarketSession:
    return INDIA_SESSION if is_indian_exchange(exchange) else US_SESSION


def session_for_stock(stock) -> MarketSession:
    return session_for_exchange(getattr(stock, "exchange", None))


def broker_symbol(symbol: str) -> str:
    """App symbol -> exchange trading symbol (RELIANCE.NS -> RELIANCE)."""
    value = symbol.strip().upper()
    for suffix in INDIAN_SUFFIXES:
        if value.endswith(suffix):
            return value[: -len(suffix)]
    return value


def validate_indian_symbol(symbol: str, exchange: str | None) -> str | None:
    """Return an error message when an Indian stock's symbol/exchange disagree."""
    value = symbol.strip().upper()
    suffix_exchange = next(
        (ex for sfx, ex in INDIAN_SUFFIXES.items() if value.endswith(sfx)), None
    )
    exchange = (exchange or "").strip().upper()
    if suffix_exchange is None and exchange in INDIAN_EXCHANGES:
        expected = ".NS" if exchange == "NSE" else ".BO"
        return f"Indian stocks need the {expected} suffix, e.g. {value}{expected}"
    if suffix_exchange is not None and exchange != suffix_exchange:
        return f"Symbol {value} must use exchange {suffix_exchange}"
    return None


# ---------------------------------------------------------------------------
# Market tabs (US / India)
# ---------------------------------------------------------------------------

MARKET_SESSIONS: dict[str, MarketSession] = {"US": US_SESSION, "IN": INDIA_SESSION}


def session_for_code(code: str) -> MarketSession:
    try:
        return MARKET_SESSIONS[code.strip().upper()]
    except KeyError:
        raise ValueError(f"Unknown market '{code}'. Use US or IN.") from None


def stock_in_market(stock, market: str | None) -> bool:
    """True when no market filter is given, or the stock trades in that market."""
    if not market:
        return True
    return session_for_stock(stock).code == market.strip().upper()


def market_status(session: MarketSession, now: datetime | None = None) -> dict:
    """Open/closed state plus today's hours and the next open, for the UI badge."""
    from datetime import timedelta

    now_utc = now or datetime.now(timezone.utc)
    local = session.local(now_utc)
    today = local.date()

    session_today = session.is_session_day(today)
    opens_at = closes_at = None
    is_open = False
    if session_today:
        opens_at = datetime.combine(today, session.open, tzinfo=session.tz)
        closes_at = datetime.combine(today, session.close_time_on(today), tzinfo=session.tz)
        is_open = opens_at <= local < closes_at

    # Next open: later today if before the open, otherwise the next session day.
    next_open = None
    if session_today and opens_at is not None and local < opens_at:
        next_open = opens_at
    else:
        day = today
        for _ in range(14):
            day += timedelta(days=1)
            if session.is_session_day(day):
                next_open = datetime.combine(day, session.open, tzinfo=session.tz)
                break

    return {
        "market": session.code,
        "timezone": session.timezone_name,
        "is_open": is_open,
        "is_session_day": session_today,
        "local_time": local,
        "opens_at": opens_at,
        "closes_at": closes_at,
        "next_open": next_open if not is_open else None,
        "early_close": bool(closes_at and closes_at.time() < session.close),
    }