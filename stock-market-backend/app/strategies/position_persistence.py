from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.market.sessions import US_SESSION, MarketSession

# US defaults kept for backward compatibility; pass `session` for other markets.
SESSION_TZ = ZoneInfo("America/New_York")
REGULAR_SESSION_OPEN = time(9, 30)
REGULAR_SESSION_CLOSE = time(16, 0)
TIMEFRAME_MINUTES = {
    "1Min": 1,
    "5Min": 5,
    "15Min": 15,
    "30Min": 30,
    "1Hour": 60,
}


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_regular_session_candle(
    candle_time: datetime,
    session: MarketSession = US_SESSION,
) -> bool:
    return session.is_regular(aware_utc(candle_time))


def is_completed_candle(
    candle_time: datetime,
    timeframe: str,
    now: datetime | None = None,
    session: MarketSession = US_SESSION,
) -> bool:
    now_utc = aware_utc(now or datetime.now(timezone.utc))
    start_utc = aware_utc(candle_time)
    minutes = TIMEFRAME_MINUTES.get(timeframe)
    if minutes is not None:
        return start_utc + timedelta(minutes=minutes) <= now_utc
    if timeframe == "1Day":
        market_date = start_utc.astimezone(session.tz).date()
        close_local = datetime.combine(market_date, session.close, tzinfo=session.tz)
        return close_local.astimezone(timezone.utc) <= now_utc
    return False


def evaluate_persistent_opening_gate(
    signal_lifecycle: dict,
    risk_reward: dict,
    breakout: dict,
) -> tuple[bool, str]:
    signal_state = str(signal_lifecycle.get("state") or "")
    if signal_state != "ENTRY_CONFIRMED":
        return False, f"Signal lifecycle is {signal_state or 'UNKNOWN'}; analytical position opens only after ENTRY_CONFIRMED"
    if not bool(breakout.get("confirmed")) or str(breakout.get("status") or "") != "ENTRY_CONFIRMED":
        return False, "Signal says ENTRY_CONFIRMED but breakout confirmation is not ENTRY_CONFIRMED"
    if breakout.get("follow_through_candle_timestamp") is None:
        return False, "ENTRY_CONFIRMED is missing the follow-through candle timestamp"
    if not bool(risk_reward.get("recalculated_after_breakout")):
        return False, "Confirmed entry requires post-breakout risk/stop/target recalculation before opening a persistent position"

    entry = risk_reward.get("entry")
    stop = risk_reward.get("stop_loss")
    risk = risk_reward.get("risk_per_share")
    if entry is None or stop is None or risk is None:
        return False, "Confirmed entry is missing required risk parameters"
    entry = float(entry)
    stop = float(stop)
    risk = float(risk)
    if risk <= 0 or stop >= entry:
        return False, "Confirmed signal has invalid long risk parameters; analytical position was not opened"
    return True, "ENTRY_CONFIRMED and recalculated risk parameters passed the persistent opening gate"


def classify_monitoring_candle(
    candle_time: datetime,
    *,
    last_evaluated_candle_time: datetime | None,
    timeframe: str,
    now: datetime | None = None,
    session: MarketSession = US_SESSION,
) -> str:
    """Classify a stored candle before persistent position monitoring.

    The cursor check is deliberately first so a previously consumed candle can
    never be re-applied to the position state machine.
    """
    if last_evaluated_candle_time is not None:
        if aware_utc(candle_time) <= aware_utc(last_evaluated_candle_time):
            return "DUPLICATE_OR_ALREADY_EVALUATED"
    if not is_regular_session_candle(candle_time, session):
        return "OUT_OF_SESSION"
    if not is_completed_candle(candle_time, timeframe, now, session):
        return "INCOMPLETE"
    return "ELIGIBLE"
