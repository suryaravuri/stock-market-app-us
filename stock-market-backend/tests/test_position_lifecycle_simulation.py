from datetime import datetime, timezone

import pytest

from app.schemas.position_lifecycle import PositionLifecycleSimulationRequest, PositionSimulationCandle
from app.services.position_lifecycle_simulation_service import PositionLifecycleSimulationService


def candle(minute: int, o: float, h: float, l: float, c: float) -> PositionSimulationCandle:
    return PositionSimulationCandle(
        timestamp=datetime(2026, 8, 28, 14, minute, tzinfo=timezone.utc),
        open=o,
        high=h,
        low=l,
        close=c,
    )


def request(candles, target_1=104.0, target_2=106.0):
    return PositionLifecycleSimulationRequest(
        timeframe="15Min",
        entry_price=100.0,
        initial_stop=98.0,
        target_1=target_1,
        target_2=target_2,
        candles=candles,
    )


def test_simulation_is_explicitly_stateless_and_analysis_only():
    result = PositionLifecycleSimulationService.simulate(
        "PLTR", request([candle(0, 100.0, 102.0, 99.0, 101.0)])
    )
    assert result["simulation_mode"] == "STATELESS_VALIDATION"
    assert result["execution_mode"] == "ANALYSIS_ONLY"
    assert result["broker_order_submitted"] is False
    assert result["database_mutated"] is False
    assert result["final_state"] == "POSITION_OPEN"


def test_full_target_one_trailing_then_stop_path():
    result = PositionLifecycleSimulationService.simulate(
        "PLTR",
        request(
            [
                candle(0, 100.0, 102.0, 99.2, 101.0),
                candle(15, 101.0, 104.2, 100.5, 103.8),
                candle(30, 103.8, 105.0, 100.5, 104.5),
                candle(45, 104.5, 104.8, 102.4, 102.7),
            ]
        ),
    )
    assert [x["to_state"] for x in result["observations"]] == [
        "POSITION_OPEN",
        "TARGET_1_HIT",
        "TRAILING",
        "STOP_HIT",
    ]
    assert result["final_state"] == "STOP_HIT"
    assert result["terminal"] is True
    assert result["active_stop"] == 102.5
    assert result["observations"][-1]["exit_reason"] == "TRAILING_STOP"


def test_target_two_terminal_stops_evaluating_later_candles():
    result = PositionLifecycleSimulationService.simulate(
        "PLTR",
        request(
            [
                candle(0, 100.0, 106.2, 99.0, 105.8),
                candle(15, 105.8, 110.0, 105.0, 109.0),
            ]
        ),
    )
    assert result["final_state"] == "TARGET_2_HIT"
    assert result["candles_received"] == 2
    assert result["candles_evaluated"] == 1
    assert result["observations"][0]["exit_reason"] == "TARGET_2"


def test_conservative_stop_priority_in_ambiguous_candle():
    result = PositionLifecycleSimulationService.simulate(
        "PLTR", request([candle(0, 100.0, 105.0, 97.5, 104.0)])
    )
    assert result["final_state"] == "STOP_HIT"
    assert result["observations"][0]["exit_reason"] == "STOP_LOSS"
    assert result["observations"][0]["exit_price"] == 98.0


def test_rejects_invalid_long_risk():
    bad = PositionLifecycleSimulationRequest(
        entry_price=100.0,
        initial_stop=100.0,
        target_1=104.0,
        candles=[candle(0, 100.0, 101.0, 99.0, 100.5)],
    )
    with pytest.raises(ValueError, match="initial_stop must be below"):
        PositionLifecycleSimulationService.simulate("PLTR", bad)


def test_rejects_unsorted_candles():
    bad = request(
        [
            candle(15, 100.0, 101.0, 99.0, 100.5),
            candle(0, 100.0, 101.0, 99.0, 100.5),
        ]
    )
    with pytest.raises(ValueError, match="strictly increasing"):
        PositionLifecycleSimulationService.simulate("PLTR", bad)
