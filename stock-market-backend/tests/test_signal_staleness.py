from datetime import datetime, timezone

from app.schemas.market import MarketTimeframe
from app.strategies.signal_staleness import evaluate_signal_staleness


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_fresh_15_minute_signal():
    result = evaluate_signal_staleness(
        state="WATCHING",
        timeframe=MarketTimeframe.FIFTEEN_MINUTES,
        signal_candle_time=dt("2026-08-28T14:00:00Z"),
        now=dt("2026-08-28T14:30:00Z"),
    )
    assert result.expired is False
    assert result.status == "FRESH"


def test_prior_session_expires():
    result = evaluate_signal_staleness(
        state="WATCHING",
        timeframe=MarketTimeframe.FIFTEEN_MINUTES,
        signal_candle_time=dt("2026-08-27T19:45:00Z"),
        now=dt("2026-08-28T14:30:00Z"),
    )
    assert result.expired is True
    assert result.status == "SESSION_ENDED"


def test_pending_signal_expires_after_four_candles():
    result = evaluate_signal_staleness(
        state="BREAKOUT_PENDING",
        timeframe=MarketTimeframe.FIFTEEN_MINUTES,
        signal_candle_time=dt("2026-08-28T14:00:00Z"),
        pending_candles=4,
        max_pending_candles=4,
        now=dt("2026-08-28T14:30:00Z"),
    )
    assert result.expired is True
    assert result.status == "PENDING_TIMEOUT"


def test_entry_confirmed_not_expired_by_signal_freshness_layer():
    result = evaluate_signal_staleness(
        state="ENTRY_CONFIRMED",
        timeframe=MarketTimeframe.FIFTEEN_MINUTES,
        signal_candle_time=dt("2026-08-27T19:45:00Z"),
        now=dt("2026-08-28T14:30:00Z"),
    )
    assert result.expired is False
    assert result.status == "NOT_APPLICABLE"
