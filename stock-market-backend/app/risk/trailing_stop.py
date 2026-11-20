"""Proportional (percentage) trailing stop for long positions.

Pure function, no broker or DB access, so it is easy to unit test.

Rules
-----
1. The stop follows price at a fixed percentage below it:
       candidate = current_price * (1 - trail_percent / 100)
   so when price rises 10%, the stop rises 10% too.
2. Trailing starts only after the gain reaches `activation_percent`
   (0 = trail from the moment the position is in profit at all).
3. Once the gain reaches `breakeven_percent`, the stop is never below entry,
   so a winning trade cannot turn into a loss.
4. Ratchet: the stop only ever moves UP. A pullback never lowers it.
5. Small moves are ignored (`min_step_percent`) to avoid replacing the
   broker order on every cent.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class TrailingStopDecision:
    should_update: bool
    new_stop: float | None
    reason: str
    gain_percent: float


def _round_down_cents(value: float) -> float:
    # Round DOWN so the stop is never placed above the computed level.
    return math.floor(value * 100) / 100


def compute_trailing_stop(
    *,
    entry_price: float,
    current_price: float,
    current_stop: float | None,
    trail_percent: float,
    activation_percent: float = 0.0,
    breakeven_percent: float | None = None,
    min_step_percent: float = 0.25,
) -> TrailingStopDecision:
    if entry_price <= 0 or current_price <= 0:
        raise ValueError("entry_price and current_price must be positive")
    if not 0 < trail_percent < 100:
        raise ValueError("trail_percent must be between 0 and 100")

    gain = (current_price - entry_price) / entry_price * 100

    if gain < activation_percent:
        return TrailingStopDecision(
            False, None,
            f"NOT_ACTIVE: gain {gain:.2f}% < activation {activation_percent:.2f}%",
            gain,
        )

    candidate = current_price * (1 - trail_percent / 100)

    if breakeven_percent is not None and gain >= breakeven_percent:
        candidate = max(candidate, entry_price)

    # A sell stop must sit below the market or the broker rejects / fills it.
    candidate = min(candidate, current_price - 0.01)
    candidate = _round_down_cents(candidate)

    if current_stop is not None:
        threshold = current_stop * (1 + min_step_percent / 100)
        if candidate <= threshold:
            return TrailingStopDecision(
                False, None,
                f"NO_IMPROVEMENT: candidate {candidate:.2f} vs current {current_stop:.2f}",
                gain,
            )

    return TrailingStopDecision(
        True, candidate,
        f"RAISE_STOP: {current_stop} -> {candidate:.2f} (gain {gain:.2f}%)",
        gain,
    )
