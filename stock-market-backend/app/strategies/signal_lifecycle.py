from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SignalState(StrEnum):
    WATCHING = "WATCHING"
    BREAKOUT_PENDING = "BREAKOUT_PENDING"
    FOLLOW_THROUGH_PENDING = "FOLLOW_THROUGH_PENDING"
    ENTRY_CONFIRMED = "ENTRY_CONFIRMED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class SignalTransition:
    previous_state: SignalState | None
    state: SignalState
    event: str
    changed: bool
    reason: str


_BREAKOUT_PENDING_STATUSES = {
    "PRICE_BREAKOUT_LOW_VOLUME",
    "PRICE_BREAKOUT_WEAK_CANDLE",
    "PRICE_BREAKOUT_WEAK_BODY",
    "PRICE_BREAKOUT_UPPER_WICK",
}


def desired_signal_state(
    *,
    overall_score: int,
    decision_action: str,
    breakout_status: str | None,
    breakout_detected: bool,
    breakout_confirmed: bool,
) -> tuple[SignalState, str, str]:
    """Map the latest analytical observation to a desired lifecycle state.

    This function intentionally has no persistence concerns so the transition
    policy can be unit tested independently of the database.
    """
    status = (breakout_status or "").upper()
    action = decision_action.upper()

    if action == "AVOID" or overall_score <= -30 or status == "FOLLOW_THROUGH_FAILED":
        return (
            SignalState.INVALIDATED,
            "SIGNAL_INVALIDATED",
            "Trend/setup invalidated or breakout follow-through failed",
        )

    if breakout_confirmed or status == "ENTRY_CONFIRMED":
        return (
            SignalState.ENTRY_CONFIRMED,
            "ENTRY_GATE_CONFIRMED",
            "Breakout plus follow-through/retest confirmation passed",
        )

    if status == "BREAKOUT_DETECTED_PENDING_FOLLOW_THROUGH" or (
        breakout_detected and not breakout_confirmed
    ):
        return (
            SignalState.FOLLOW_THROUGH_PENDING,
            "BREAKOUT_DETECTED",
            "Qualified breakout detected; waiting for follow-through/retest",
        )

    if status in _BREAKOUT_PENDING_STATUSES:
        return (
            SignalState.BREAKOUT_PENDING,
            "BREAKOUT_ATTEMPT",
            f"Price attempted a breakout but confirmation is incomplete ({status})",
        )

    return (
        SignalState.WATCHING,
        "SETUP_WATCHING",
        "Setup is being watched for a qualified breakout",
    )


def transition_signal_state(
    *,
    previous_state: SignalState | None,
    desired_state: SignalState,
    desired_event: str,
    desired_reason: str,
) -> SignalTransition:
    """Apply lifecycle guardrails so repeated API reads do not regress a signal.

    ENTRY_CONFIRMED is sticky until an explicit invalidation is observed.
    INVALIDATED is terminal for the current signal cycle. A future improvement
    can introduce a new signal-cycle identifier when a fresh setup forms.
    """
    if previous_state in {SignalState.INVALIDATED, SignalState.EXPIRED}:
        return SignalTransition(
            previous_state=previous_state,
            state=previous_state,
            event="NO_STATE_CHANGE",
            changed=False,
            reason=f"Signal cycle is already {previous_state.value.lower()}",
        )

    if previous_state is SignalState.ENTRY_CONFIRMED and desired_state is not SignalState.INVALIDATED:
        return SignalTransition(
            previous_state=previous_state,
            state=SignalState.ENTRY_CONFIRMED,
            event="NO_STATE_CHANGE",
            changed=False,
            reason="Entry confirmation is retained until an invalidation is observed",
        )

    if previous_state == desired_state:
        return SignalTransition(
            previous_state=previous_state,
            state=desired_state,
            event="NO_STATE_CHANGE",
            changed=False,
            reason=desired_reason,
        )

    return SignalTransition(
        previous_state=previous_state,
        state=desired_state,
        event=desired_event,
        changed=True,
        reason=desired_reason,
    )


def should_refresh_signal_candle_time(
    *,
    state: SignalState,
    transition_changed: bool,
) -> bool:
    """Return whether the lifecycle cycle should adopt the latest observed candle.

    Active cycles keep moving with fresh completed observations. A transition
    into a terminal state records the candle that caused that transition. Once
    a cycle is already terminal (EXPIRED/INVALIDATED) and no new cycle is
    created, later observations must not rewrite the cycle's signal timestamp.
    """
    if transition_changed:
        return True
    return state not in {SignalState.EXPIRED, SignalState.INVALIDATED}
