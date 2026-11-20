from app.strategies.signal_lifecycle import (
    SignalState,
    desired_signal_state,
    transition_signal_state,
)


def test_waiting_for_price_maps_to_watching():
    state, event, _ = desired_signal_state(
        overall_score=58,
        decision_action="WAIT_FOR_BREAKOUT",
        breakout_status="WAITING_FOR_PRICE",
        breakout_detected=False,
        breakout_confirmed=False,
    )
    assert state == SignalState.WATCHING
    assert event == "SETUP_WATCHING"


def test_breakout_detection_maps_to_follow_through_pending():
    state, _, _ = desired_signal_state(
        overall_score=58,
        decision_action="WAIT_FOR_BREAKOUT",
        breakout_status="BREAKOUT_DETECTED_PENDING_FOLLOW_THROUGH",
        breakout_detected=True,
        breakout_confirmed=False,
    )
    assert state == SignalState.FOLLOW_THROUGH_PENDING


def test_entry_confirmed_is_sticky_without_invalidation():
    transition = transition_signal_state(
        previous_state=SignalState.ENTRY_CONFIRMED,
        desired_state=SignalState.WATCHING,
        desired_event="SETUP_WATCHING",
        desired_reason="latest observation is waiting",
    )
    assert transition.state == SignalState.ENTRY_CONFIRMED
    assert transition.changed is False


def test_follow_through_failure_invalidates():
    state, _, _ = desired_signal_state(
        overall_score=58,
        decision_action="WAIT_FOR_BREAKOUT",
        breakout_status="FOLLOW_THROUGH_FAILED",
        breakout_detected=True,
        breakout_confirmed=False,
    )
    assert state == SignalState.INVALIDATED
