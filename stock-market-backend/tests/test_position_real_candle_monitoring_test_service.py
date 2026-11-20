from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models.position_test_state import PositionTestStateRecord
from app.schemas.position_lifecycle import PersistentRealCandleMonitorStartRequest
from app.services.position_lifecycle_real_candle_test_service import PositionLifecycleRealCandleTestService


def candle(ts, o=100.0, h=101.0, l=99.0, c=100.5):
    return SimpleNamespace(
        candle_time=ts,
        open_price=o,
        high_price=h,
        low_price=l,
        close_price=c,
    )


def make_record():
    return PositionTestStateRecord(
        position_test_state_id=1,
        test_run_id="run-1",
        stock_id=6,
        symbol="PLTR",
        timeframe="15Min",
        state="POSITION_OPEN",
        previous_state=None,
        last_event="TEST_POSITION_OPENED",
        reason="test",
        entry_price=100.0,
        initial_stop=90.0,
        active_stop=90.0,
        target_1=120.0,
        target_2=130.0,
        initial_risk_per_share=10.0,
        target_1_hit=False,
        target_2_hit=False,
        opened_at=datetime(2026, 8, 28, 13, 30, tzinfo=timezone.utc),
        last_evaluated_candle_time=datetime(2026, 8, 28, 13, 30, tzinfo=timezone.utc),
        version=1,
    )


def test_second_run_does_not_reapply_last_consumed_candle():
    db = MagicMock()
    stock = SimpleNamespace(stock_id=6)
    rec = make_record()
    c1 = candle(datetime(2026, 8, 28, 13, 45, tzinfo=timezone.utc))
    latest = c1

    with patch("app.services.position_lifecycle_real_candle_test_service.StockRepository.find_by_symbol", return_value=stock), \
         patch("app.services.position_lifecycle_real_candle_test_service.MarketCandleRepository.find_latest", return_value=latest), \
         patch("app.services.position_lifecycle_real_candle_test_service.MarketCandleRepository.find_by_range", side_effect=[[c1], [c1]]):
        first = PositionLifecycleRealCandleTestService._monitor(
            db, rec, trigger="CREATE_AND_MONITOR", now_utc=datetime(2026, 8, 28, 14, 30, tzinfo=timezone.utc), created_this_call=True
        )
        second = PositionLifecycleRealCandleTestService._monitor(
            db, rec, trigger="REMONITOR", now_utc=datetime(2026, 8, 28, 14, 30, tzinfo=timezone.utc), created_this_call=False
        )

    assert first["processed_candles"] == 1
    assert first["last_evaluated_candle_time"] == c1.candle_time
    assert second["processed_candles"] == 0
    assert second["duplicate_candles_skipped"] == 1
    assert second["test_database_mutated"] is False


def test_incomplete_candle_is_not_consumed_and_can_be_processed_later():
    db = MagicMock()
    stock = SimpleNamespace(stock_id=6)
    rec = make_record()
    c1 = candle(datetime(2026, 8, 28, 14, 15, tzinfo=timezone.utc))

    with patch("app.services.position_lifecycle_real_candle_test_service.StockRepository.find_by_symbol", return_value=stock), \
         patch("app.services.position_lifecycle_real_candle_test_service.MarketCandleRepository.find_latest", return_value=c1), \
         patch("app.services.position_lifecycle_real_candle_test_service.MarketCandleRepository.find_by_range", side_effect=[[c1], [c1]]):
        before_close = PositionLifecycleRealCandleTestService._monitor(
            db, rec, trigger="CREATE_AND_MONITOR", now_utc=datetime(2026, 8, 28, 14, 20, tzinfo=timezone.utc), created_this_call=True
        )
        cursor_after_incomplete = rec.last_evaluated_candle_time
        after_close = PositionLifecycleRealCandleTestService._monitor(
            db, rec, trigger="REMONITOR", now_utc=datetime(2026, 8, 28, 14, 31, tzinfo=timezone.utc), created_this_call=False
        )

    assert before_close["ignored_incomplete_candles"] == 1
    assert cursor_after_incomplete == datetime(2026, 8, 28, 13, 30, tzinfo=timezone.utc)
    assert after_close["processed_candles"] == 1
    assert rec.last_evaluated_candle_time == c1.candle_time


def test_start_request_validation_rejects_invalid_long_risk():
    request = PersistentRealCandleMonitorStartRequest(
        timeframe="15Min",
        entry_price=100,
        initial_stop=101,
        target_1=120,
        target_2=130,
        opened_at=datetime(2026, 8, 28, 13, 30, tzinfo=timezone.utc),
    )
    try:
        PositionLifecycleRealCandleTestService._validate_start(request)
    except ValueError as exc:
        assert "initial_stop" in str(exc)
    else:
        raise AssertionError("Expected invalid long risk to be rejected")
