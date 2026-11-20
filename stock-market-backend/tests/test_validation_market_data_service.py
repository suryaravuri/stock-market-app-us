from datetime import datetime, timezone

from app.services.validation_market_data_service import ValidationMarketDataService



def test_labor_day_uses_previous_session():
    now = datetime(2026, 9, 8, 1, 43, tzinfo=timezone.utc)

    result = ValidationMarketDataService.expected_latest_completed_candle(
        "15Min",
        now,
    )

    assert result == datetime(
        2026, 9, 4, 19, 45,
        tzinfo=timezone.utc,
    )


def test_pre_market_after_holiday_uses_previous_session():
    now = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)

    result = ValidationMarketDataService.expected_latest_completed_candle(
        "15Min",
        now,
    )

    assert result == datetime(
        2026, 9, 4, 19, 45,
        tzinfo=timezone.utc,
    )


def test_session_distance_skips_labor_day():
    from datetime import date

    assert (
        ValidationMarketDataService._session_distance(
            date(2026, 9, 4),
            date(2026, 9, 7),
        )
        == 0
    )

    assert (
        ValidationMarketDataService._session_distance(
            date(2026, 9, 4),
            date(2026, 9, 8),
        )
        == 1
    )

def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_expected_15m_bar_during_session_uses_last_completed_bar():
    # 15:13 ET on Aug 28 2026 => 19:13 UTC. 15:00 bar is incomplete,
    # therefore 14:45 ET / 18:45 UTC is the expected latest completed start.
    result = ValidationMarketDataService.expected_latest_completed_candle(
        "15Min", dt("2026-08-28T19:13:00Z")
    )
    assert result == dt("2026-08-28T18:45:00Z")


def test_expected_15m_bar_after_close_does_not_become_stale_after_hours():
    result = ValidationMarketDataService.expected_latest_completed_candle(
        "15Min", dt("2026-08-28T21:30:00Z")
    )
    assert result == dt("2026-08-28T19:45:00Z")


def test_expected_15m_bar_before_open_uses_prior_session_close_bar():
    result = ValidationMarketDataService.expected_latest_completed_candle(
        "15Min", dt("2026-08-28T12:00:00Z")
    )
    assert result == dt("2026-08-27T19:45:00Z")


def test_expected_15m_bar_weekend_uses_friday_close_bar():
    result = ValidationMarketDataService.expected_latest_completed_candle(
        "15Min", dt("2026-08-30T16:00:00Z")
    )
    assert result == dt("2026-08-28T19:45:00Z")


def test_lag_zero_when_latest_matches_expected():
    assert ValidationMarketDataService._lag_bars(
        dt("2026-08-28T18:45:00Z"), dt("2026-08-28T18:45:00Z"), "15Min"
    ) == 0


def test_lag_one_for_one_missing_15m_bar():
    assert ValidationMarketDataService._lag_bars(
        dt("2026-08-28T18:30:00Z"), dt("2026-08-28T18:45:00Z"), "15Min"
    ) == 1


# ---- NSE/BSE (India) sessions -------------------------------------------

def test_india_intraday_expected_candle_during_session():
    from zoneinfo import ZoneInfo
    from app.market.sessions import INDIA_SESSION

    ist = ZoneInfo("Asia/Kolkata")
    now = datetime(2026, 11, 2, 11, 0, tzinfo=ist)  # Monday

    result = ValidationMarketDataService.expected_latest_completed_candle(
        "15Min", now, INDIA_SESSION
    )

    # 09:15 open, 7 completed bars by 11:00 -> last completed bar starts 10:45 IST.
    assert result == datetime(2026, 11, 2, 10, 45, tzinfo=ist)


def test_india_pre_open_uses_previous_session_last_bar():
    from zoneinfo import ZoneInfo
    from app.market.sessions import INDIA_SESSION

    ist = ZoneInfo("Asia/Kolkata")
    now = datetime(2026, 11, 3, 8, 0, tzinfo=ist)  # Tuesday before the open

    result = ValidationMarketDataService.expected_latest_completed_candle(
        "15Min", now, INDIA_SESSION
    )

    # 15:30 close -> last 15-minute bar of Monday starts 15:15 IST.
    assert result == datetime(2026, 11, 2, 15, 15, tzinfo=ist)
