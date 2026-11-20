from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.market.sessions import (
    INDIA_SESSION,
    US_SESSION,
    broker_symbol,
    session_for_stock,
    validate_indian_symbol,
)
from app.schemas.market import MarketTimeframe
from app.strategies.position_persistence import (
    classify_monitoring_candle,
    is_completed_candle,
    is_regular_session_candle,
)
from app.strategies.signal_lifecycle import SignalState
from app.strategies.signal_rearm import evaluate_signal_rearm
from app.strategies.signal_staleness import evaluate_signal_staleness

IST = ZoneInfo("Asia/Kolkata")
ET = ZoneInfo("America/New_York")


def test_session_selection_by_exchange():
    assert session_for_stock(SimpleNamespace(exchange="NSE")) is INDIA_SESSION
    assert session_for_stock(SimpleNamespace(exchange="bse")) is INDIA_SESSION
    assert session_for_stock(SimpleNamespace(exchange="NASDAQ")) is US_SESSION
    assert session_for_stock(SimpleNamespace(exchange=None)) is US_SESSION


def test_india_regular_hours():
    assert is_regular_session_candle(datetime(2026, 11, 2, 9, 15, tzinfo=IST), INDIA_SESSION)
    assert is_regular_session_candle(datetime(2026, 11, 2, 15, 15, tzinfo=IST), INDIA_SESSION)
    assert not is_regular_session_candle(datetime(2026, 11, 2, 9, 0, tzinfo=IST), INDIA_SESSION)
    assert not is_regular_session_candle(datetime(2026, 11, 2, 15, 30, tzinfo=IST), INDIA_SESSION)
    # 10:00 IST is midnight-ish in New York: out of the US session, inside India's.
    candle = datetime(2026, 11, 2, 10, 0, tzinfo=IST)
    assert not is_regular_session_candle(candle)
    assert is_regular_session_candle(candle, INDIA_SESSION)


def test_india_daily_candle_completes_at_1530_ist():
    day_bar = datetime(2026, 11, 2, 0, 0, tzinfo=IST)  # Kite day candle timestamp
    assert not is_completed_candle(day_bar, "1Day", datetime(2026, 11, 2, 15, 29, tzinfo=IST), INDIA_SESSION)
    assert is_completed_candle(day_bar, "1Day", datetime(2026, 11, 2, 15, 30, tzinfo=IST), INDIA_SESSION)


def test_classify_monitoring_candle_india():
    now = datetime(2026, 11, 2, 12, 0, tzinfo=IST)
    eligible = classify_monitoring_candle(
        datetime(2026, 11, 2, 11, 30, tzinfo=IST),
        last_evaluated_candle_time=None,
        timeframe="15Min",
        now=now,
        session=INDIA_SESSION,
    )
    assert eligible == "ELIGIBLE"


def test_staleness_session_end_uses_exchange_close():
    candle = datetime(2026, 11, 2, 15, 0, tzinfo=IST)
    # 15:40 IST: India closed, so a same-day pending signal has expired.
    india = evaluate_signal_staleness(
        state="BREAKOUT_PENDING",
        timeframe=MarketTimeframe.FIFTEEN_MINUTES,
        signal_candle_time=candle,
        now=datetime(2026, 11, 2, 15, 40, tzinfo=IST),
        session=INDIA_SESSION,
    )
    assert india.expired and india.status == "SESSION_ENDED"


def test_staleness_india_fresh_inside_session():
    candle = datetime(2026, 11, 2, 11, 0, tzinfo=IST)
    result = evaluate_signal_staleness(
        state="BREAKOUT_PENDING",
        timeframe=MarketTimeframe.FIFTEEN_MINUTES,
        signal_candle_time=candle,
        now=datetime(2026, 11, 2, 11, 20, tzinfo=IST),
        session=INDIA_SESSION,
    )
    assert not result.expired
    # The same instants judged on New York dates would cross midnight ET
    # (11:00 IST on Nov 2 is 01:30 ET), which is why the session matters.


def test_rearm_uses_exchange_calendar_date():
    # 09:30 and 14:00 IST on the same Indian trading day straddle midnight
    # Eastern time, so US dates would wrongly call them different sessions.
    previous = datetime(2026, 11, 2, 9, 30, tzinfo=IST)
    candidate = datetime(2026, 11, 2, 14, 0, tzinfo=IST)
    assert previous.astimezone(ET).date() != candidate.astimezone(ET).date()

    india = evaluate_signal_rearm(
        previous_state=SignalState.EXPIRED,
        previous_signal_candle_time=previous,
        candidate_signal_candle_time=candidate,
        desired_state=SignalState.WATCHING,
        candidate_is_fresh=True,
        session=INDIA_SESSION,
    )
    assert not india.allowed and india.status == "SAME_SESSION"


def test_broker_symbol_and_validation():
    assert broker_symbol("RELIANCE.NS") == "RELIANCE"
    assert broker_symbol("bajaj-auto.bo") == "BAJAJ-AUTO"
    assert broker_symbol("AAPL") == "AAPL"
    assert validate_indian_symbol("RELIANCE.NS", "NSE") is None
    assert validate_indian_symbol("AAPL", "NASDAQ") is None
    assert validate_indian_symbol("RELIANCE", "NSE") is not None
    assert validate_indian_symbol("RELIANCE.NS", "BSE") is not None
