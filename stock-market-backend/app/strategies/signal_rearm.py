from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.market.sessions import US_SESSION, MarketSession
from app.strategies.signal_lifecycle import SignalState

MARKET_TZ = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class SignalRearmResult:
    allowed: bool
    status: str
    reason: str


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def evaluate_signal_rearm(
    *,
    previous_state: SignalState | None,
    previous_signal_candle_time: datetime | None,
    candidate_signal_candle_time: datetime | None,
    desired_state: SignalState,
    candidate_is_fresh: bool,
    session: MarketSession = US_SESSION,
) -> SignalRearmResult:
    """Decide whether a terminal pre-entry signal may start a new cycle.

    Automatic re-arming is deliberately conservative: only EXPIRED or
    INVALIDATED pre-entry cycles may re-arm, and only when the observed market
    candle belongs to a strictly newer regular-market date. This prevents a
    repeated API call over the same historical data from resurrecting a dead
    signal.
    """
    if previous_state not in {SignalState.EXPIRED, SignalState.INVALIDATED}:
        return SignalRearmResult(False, "NOT_TERMINAL", "Current signal cycle is not terminal")

    if desired_state is SignalState.INVALIDATED:
        return SignalRearmResult(False, "SETUP_NOT_QUALIFIED", "Fresh observation is still invalidated")

    if not candidate_is_fresh:
        return SignalRearmResult(False, "CANDIDATE_STALE", "Candidate signal candle is not fresh")

    previous_time = _aware(previous_signal_candle_time)
    candidate_time = _aware(candidate_signal_candle_time)
    if previous_time is None or candidate_time is None:
        return SignalRearmResult(False, "MISSING_CANDLE_TIME", "Cannot establish a new signal session")

    if candidate_time <= previous_time:
        return SignalRearmResult(False, "NO_NEW_CANDLE", "No newer signal candle is available")

    previous_date = previous_time.astimezone(session.tz).date()
    candidate_date = candidate_time.astimezone(session.tz).date()
    if candidate_date <= previous_date:
        return SignalRearmResult(
            False,
            "SAME_SESSION",
            "Terminal signal cannot automatically re-arm within the same market session",
        )

    return SignalRearmResult(
        True,
        "NEW_SESSION",
        f"Fresh qualified signal detected for new market session {candidate_date.isoformat()}",
    )
