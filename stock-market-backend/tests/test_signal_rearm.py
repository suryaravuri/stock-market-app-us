from datetime import datetime

from app.strategies.signal_lifecycle import SignalState
from app.strategies.signal_rearm import evaluate_signal_rearm


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_expired_signal_rearms_on_new_session_fresh_candle():
    result = evaluate_signal_rearm(
        previous_state=SignalState.EXPIRED,
        previous_signal_candle_time=dt("2026-08-27T19:45:00Z"),
        candidate_signal_candle_time=dt("2026-08-28T14:00:00Z"),
        desired_state=SignalState.WATCHING,
        candidate_is_fresh=True,
    )
    assert result.allowed is True
    assert result.status == "NEW_SESSION"


def test_expired_signal_does_not_rearm_same_session():
    result = evaluate_signal_rearm(
        previous_state=SignalState.EXPIRED,
        previous_signal_candle_time=dt("2026-08-28T14:00:00Z"),
        candidate_signal_candle_time=dt("2026-08-28T15:00:00Z"),
        desired_state=SignalState.WATCHING,
        candidate_is_fresh=True,
    )
    assert result.allowed is False
    assert result.status == "SAME_SESSION"


def test_same_historical_candle_cannot_resurrect_expired_signal():
    result = evaluate_signal_rearm(
        previous_state=SignalState.EXPIRED,
        previous_signal_candle_time=dt("2026-08-27T19:45:00Z"),
        candidate_signal_candle_time=dt("2026-08-27T19:45:00Z"),
        desired_state=SignalState.WATCHING,
        candidate_is_fresh=True,
    )
    assert result.allowed is False
    assert result.status == "NO_NEW_CANDLE"


def test_stale_new_session_candidate_does_not_rearm():
    result = evaluate_signal_rearm(
        previous_state=SignalState.EXPIRED,
        previous_signal_candle_time=dt("2026-08-27T19:45:00Z"),
        candidate_signal_candle_time=dt("2026-08-28T14:00:00Z"),
        desired_state=SignalState.WATCHING,
        candidate_is_fresh=False,
    )
    assert result.allowed is False
    assert result.status == "CANDIDATE_STALE"


def test_invalidated_signal_can_rearm_only_with_new_session_qualified_setup():
    result = evaluate_signal_rearm(
        previous_state=SignalState.INVALIDATED,
        previous_signal_candle_time=dt("2026-08-27T19:45:00Z"),
        candidate_signal_candle_time=dt("2026-08-28T14:00:00Z"),
        desired_state=SignalState.BREAKOUT_PENDING,
        candidate_is_fresh=True,
    )
    assert result.allowed is True
