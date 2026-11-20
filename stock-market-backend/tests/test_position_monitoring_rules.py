from datetime import datetime, timezone

from app.strategies.position_persistence import classify_monitoring_candle


def dt(hour: int, minute: int = 0):
    return datetime(2026, 8, 28, hour, minute, tzinfo=timezone.utc)


def test_monitoring_rejects_already_evaluated_candle_first():
    assert classify_monitoring_candle(
        dt(15, 0),
        last_evaluated_candle_time=dt(15, 0),
        timeframe="15Min",
        now=dt(16, 0),
    ) == "DUPLICATE_OR_ALREADY_EVALUATED"


def test_monitoring_accepts_new_completed_regular_session_candle():
    assert classify_monitoring_candle(
        dt(15, 15),
        last_evaluated_candle_time=dt(15, 0),
        timeframe="15Min",
        now=dt(15, 31),
    ) == "ELIGIBLE"


def test_monitoring_rejects_current_incomplete_candle():
    assert classify_monitoring_candle(
        dt(15, 15),
        last_evaluated_candle_time=dt(15, 0),
        timeframe="15Min",
        now=dt(15, 22),
    ) == "INCOMPLETE"


def test_monitoring_rejects_after_hours_candle():
    # 20:15 UTC = 16:15 EDT, after the regular session close.
    assert classify_monitoring_candle(
        dt(20, 15),
        last_evaluated_candle_time=dt(20, 0),
        timeframe="15Min",
        now=dt(21, 0),
    ) == "OUT_OF_SESSION"
