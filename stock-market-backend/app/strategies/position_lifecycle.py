from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PositionState(StrEnum):
    POSITION_OPEN = "POSITION_OPEN"
    TARGET_1_HIT = "TARGET_1_HIT"
    TRAILING = "TRAILING"
    STOP_HIT = "STOP_HIT"
    TARGET_2_HIT = "TARGET_2_HIT"


TERMINAL_POSITION_STATES = {PositionState.STOP_HIT, PositionState.TARGET_2_HIT}


@dataclass(frozen=True)
class PositionObservation:
    state: PositionState
    event: str
    changed: bool
    reason: str
    active_stop: float
    target_1_hit: bool
    target_2_hit: bool
    exit_price: float | None = None
    exit_reason: str | None = None


def evaluate_long_position_candle(
    *,
    state: PositionState,
    candle_high: float,
    candle_low: float,
    candle_close: float,
    entry_price: float,
    initial_stop: float,
    active_stop: float,
    target_1: float | None,
    target_2: float | None,
    target_1_hit: bool,
    initial_risk_per_share: float,
) -> PositionObservation:
    """Evaluate one *completed candle after entry* for an analysis-only long position.

    Conservative ambiguity rule: when one candle spans both an active stop and a
    target, the stop is assumed to have occurred first. This prevents optimistic
    backtest-style fills when intrabar ordering is unknowable from OHLC data.
    """
    if state in TERMINAL_POSITION_STATES:
        return PositionObservation(
            state=state,
            event="NO_STATE_CHANGE",
            changed=False,
            reason="Analytical position is already terminal",
            active_stop=active_stop,
            target_1_hit=target_1_hit,
            target_2_hit=(state is PositionState.TARGET_2_HIT),
        )

    # Always test the stop that existed before this candle. A new trailing stop
    # calculated from this candle's close cannot be used against the same candle.
    if candle_low <= active_stop:
        reason = "TRAILING_STOP" if state is PositionState.TRAILING else (
            "BREAKEVEN_STOP" if target_1_hit and active_stop >= entry_price else "STOP_LOSS"
        )
        return PositionObservation(
            state=PositionState.STOP_HIT,
            event="POSITION_STOP_HIT",
            changed=True,
            reason=f"Completed candle low {candle_low:.4f} touched active stop {active_stop:.4f}",
            active_stop=active_stop,
            target_1_hit=target_1_hit,
            target_2_hit=False,
            exit_price=active_stop,
            exit_reason=reason,
        )

    if target_2 is not None and candle_high >= target_2:
        return PositionObservation(
            state=PositionState.TARGET_2_HIT,
            event="TARGET_2_HIT",
            changed=True,
            reason=f"Completed candle high {candle_high:.4f} reached target 2 {target_2:.4f}",
            active_stop=active_stop,
            target_1_hit=True if target_1 is not None else target_1_hit,
            target_2_hit=True,
            exit_price=target_2,
            exit_reason="TARGET_2",
        )

    if not target_1_hit and target_1 is not None and candle_high >= target_1:
        return PositionObservation(
            state=PositionState.TARGET_1_HIT,
            event="TARGET_1_HIT",
            changed=True,
            reason=f"Completed candle high {candle_high:.4f} reached target 1 {target_1:.4f}; analytical stop moves to breakeven for subsequent candles",
            active_stop=max(active_stop, entry_price),
            target_1_hit=True,
            target_2_hit=False,
        )

    if target_1_hit:
        # Improvement #15 uses a simple, deterministic 1R close-based trail.
        # It is analysis-only and intentionally does not submit/modify broker orders.
        new_stop = max(active_stop, entry_price, candle_close - initial_risk_per_share)
        changed = state is not PositionState.TRAILING or new_stop > active_stop
        return PositionObservation(
            state=PositionState.TRAILING,
            event="TRAILING_STOP_ADVANCED" if new_stop > active_stop else "TRAILING_ACTIVE",
            changed=changed,
            reason=f"Target 1 was reached; trailing analytical stop is {new_stop:.4f}",
            active_stop=new_stop,
            target_1_hit=True,
            target_2_hit=False,
        )

    return PositionObservation(
        state=PositionState.POSITION_OPEN,
        event="NO_STATE_CHANGE",
        changed=False,
        reason="Position remains between active stop and target 1",
        active_stop=active_stop,
        target_1_hit=False,
        target_2_hit=False,
    )
