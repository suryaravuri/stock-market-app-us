from datetime import datetime, timezone

import pytest

from app.schemas.position_lifecycle import PersistentPositionTestRequest, PositionSimulationCandle
from app.services.position_lifecycle_persistent_test_service import PositionLifecyclePersistentTestService


def candle(minute, o, h, l, c):
    return PositionSimulationCandle(timestamp=datetime(2026, 8, 28, 14, minute, tzinfo=timezone.utc), open=o, high=h, low=l, close=c)


def request():
    return PersistentPositionTestRequest(
        timeframe="15Min",
        entry_price=100.0,
        initial_stop=98.0,
        target_1=104.0,
        target_2=106.0,
        opened_at=datetime(2026, 8, 28, 13, 45, tzinfo=timezone.utc),
        candles=[
            candle(0, 100.0, 102.0, 99.2, 101.0),
            candle(15, 101.0, 104.2, 100.5, 103.8),
            candle(30, 103.8, 105.0, 100.5, 104.5),
            candle(45, 104.5, 104.8, 102.4, 102.7),
        ],
    )


def test_controlled_test_validation_accepts_valid_scenario():
    PositionLifecyclePersistentTestService._validate(request())


def test_controlled_test_rejects_candle_not_after_opened_at():
    r = request()
    r.candles[0].timestamp = r.opened_at
    with pytest.raises(ValueError, match="strictly increasing"):
        PositionLifecyclePersistentTestService._validate(r)


def test_controlled_test_rejects_bad_targets():
    r = request(); r.target_2 = 103.0
    with pytest.raises(ValueError, match="target_2 must be above target_1"):
        PositionLifecyclePersistentTestService._validate(r)
