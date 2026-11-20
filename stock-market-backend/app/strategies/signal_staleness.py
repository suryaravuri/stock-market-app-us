from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from app.market.sessions import US_SESSION, MarketSession
from app.schemas.market import MarketTimeframe

MARKET_TZ = ZoneInfo("America/New_York")
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)


@dataclass(frozen=True)
class SignalStalenessResult:
    expired: bool
    status: str
    reason: str | None
    signal_age_minutes: float | None
    max_signal_age_minutes: int
    pending_candles: int
    max_pending_candles: int


def max_age_minutes_for(timeframe: MarketTimeframe) -> int:
    return {
        MarketTimeframe.ONE_MINUTE: 5,
        MarketTimeframe.FIVE_MINUTES: 15,
        MarketTimeframe.FIFTEEN_MINUTES: 45,
        MarketTimeframe.ONE_HOUR: 180,
        MarketTimeframe.ONE_DAY: 2880,
    }[timeframe]


def evaluate_signal_staleness(
    *,
    state: str | None,
    timeframe: MarketTimeframe,
    signal_candle_time: datetime | None,
    pending_candles: int = 0,
    max_pending_candles: int = 4,
    now: datetime | None = None,
    session: MarketSession = US_SESSION,
) -> SignalStalenessResult:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    max_age = max_age_minutes_for(timeframe)
    terminal_or_confirmed = state in {"ENTRY_CONFIRMED", "INVALIDATED", "EXPIRED"}

    if signal_candle_time is None:
        return SignalStalenessResult(
            expired=False,
            status="NO_SIGNAL_CANDLE",
            reason=None,
            signal_age_minutes=None,
            max_signal_age_minutes=max_age,
            pending_candles=pending_candles,
            max_pending_candles=max_pending_candles,
        )

    candle_time = signal_candle_time
    if candle_time.tzinfo is None:
        candle_time = candle_time.replace(tzinfo=timezone.utc)

    age_minutes = max(0.0, (now - candle_time).total_seconds() / 60.0)

    # Confirmed/terminal signals are not retroactively expired here. ENTRY_CONFIRMED
    # has its own downstream position-management lifecycle; INVALIDATED/EXPIRED are terminal.
    if terminal_or_confirmed:
        return SignalStalenessResult(
            expired=False,
            status="NOT_APPLICABLE",
            reason=None,
            signal_age_minutes=round(age_minutes, 2),
            max_signal_age_minutes=max_age,
            pending_candles=pending_candles,
            max_pending_candles=max_pending_candles,
        )

    now_et = now.astimezone(session.tz)
    candle_et = candle_time.astimezone(session.tz)

    # A setup from a prior market date must not silently remain armed overnight.
    if candle_et.date() < now_et.date():
        return SignalStalenessResult(
            expired=True,
            status="SESSION_ENDED",
            reason="Signal belongs to a prior market session",
            signal_age_minutes=round(age_minutes, 2),
            max_signal_age_minutes=max_age,
            pending_candles=pending_candles,
            max_pending_candles=max_pending_candles,
        )

    # Same-day setup becomes stale once the regular session closes.
    if now_et.weekday() < 5 and now_et.time() >= session.close:
        return SignalStalenessResult(
            expired=True,
            status="SESSION_ENDED",
            reason="Regular trading session ended before the signal progressed",
            signal_age_minutes=round(age_minutes, 2),
            max_signal_age_minutes=max_age,
            pending_candles=pending_candles,
            max_pending_candles=max_pending_candles,
        )

    if state in {"BREAKOUT_PENDING", "FOLLOW_THROUGH_PENDING"} and pending_candles >= max_pending_candles:
        return SignalStalenessResult(
            expired=True,
            status="PENDING_TIMEOUT",
            reason=f"Signal did not progress within {max_pending_candles} completed candles",
            signal_age_minutes=round(age_minutes, 2),
            max_signal_age_minutes=max_age,
            pending_candles=pending_candles,
            max_pending_candles=max_pending_candles,
        )

    if age_minutes > max_age:
        return SignalStalenessResult(
            expired=True,
            status="DATA_STALE",
            reason=f"Latest signal candle is older than the {max_age}-minute freshness limit",
            signal_age_minutes=round(age_minutes, 2),
            max_signal_age_minutes=max_age,
            pending_candles=pending_candles,
            max_pending_candles=max_pending_candles,
        )

    return SignalStalenessResult(
        expired=False,
        status="FRESH",
        reason=None,
        signal_age_minutes=round(age_minutes, 2),
        max_signal_age_minutes=max_age,
        pending_candles=pending_candles,
        max_pending_candles=max_pending_candles,
    )
