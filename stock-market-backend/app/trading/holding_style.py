"""Holding style: how long an automatic position may stay open.

Pure functions (no broker or database access) so they can be unit tested
with a fake session object.

    SWING    - no time limit (original behaviour): exit only by stop,
               target or trailing stop.
    INTRADAY - square off shortly before today's close.
    WEEKLY   - exit shortly before the close of the 5th trading session.
    MONTHLY  - exit shortly before the close of the 21st trading session.

The entry day counts as session 1.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from enum import StrEnum
from typing import Protocol


class HoldingStyle(StrEnum):
    SWING = "SWING"
    INTRADAY = "INTRADAY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


HOLDING_SESSIONS: dict[HoldingStyle, int | None] = {
    HoldingStyle.SWING: None,
    HoldingStyle.INTRADAY: 1,
    HoldingStyle.WEEKLY: 5,
    HoldingStyle.MONTHLY: 21,
}

# Never look further ahead than this many calendar days for sessions.
_MAX_CALENDAR_DAYS = 60


class SessionLike(Protocol):
    tz: object

    def is_session_day(self, day: date) -> bool: ...

    def close_time_on(self, day: date) -> time: ...


def parse_style(value: str | None) -> HoldingStyle:
    try:
        return HoldingStyle((value or HoldingStyle.SWING).upper())
    except ValueError:
        return HoldingStyle.SWING


def _close_on(session: SessionLike, day: date) -> datetime:
    return datetime.combine(day, session.close_time_on(day), tzinfo=session.tz)


def exit_deadline(
    style: HoldingStyle | str,
    entry_time: datetime,
    session: SessionLike,
    buffer_minutes: int = 15,
) -> datetime | None:
    """When a position opened at entry_time must be closed (None = no limit)."""
    style = parse_style(style)
    sessions_allowed = HOLDING_SESSIONS[style]
    if sessions_allowed is None:
        return None
    if entry_time.tzinfo is None:
        raise ValueError("entry_time must be timezone-aware")

    day = entry_time.astimezone(session.tz).date()
    counted = 0
    for _ in range(_MAX_CALENDAR_DAYS):
        if session.is_session_day(day):
            counted += 1
            if counted == sessions_allowed:
                return _close_on(session, day) - timedelta(minutes=buffer_minutes)
        day += timedelta(days=1)
    raise ValueError("Could not find enough trading sessions in the calendar")


def intraday_entry_allowed(
    now: datetime,
    session: SessionLike,
    cutoff_minutes: int = 45,
) -> bool:
    """INTRADAY entries are refused close to the close (too little time left)."""
    local_day = now.astimezone(session.tz).date()
    if not session.is_session_day(local_day):
        return False
    return now < _close_on(session, local_day) - timedelta(minutes=cutoff_minutes)


def exit_reason_for(style: HoldingStyle | str) -> str:
    return "SESSION_CLOSE" if parse_style(style) is HoldingStyle.INTRADAY else "TIME_EXIT"
