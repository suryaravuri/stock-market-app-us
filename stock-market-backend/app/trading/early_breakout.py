"""Early-warning breakout detection from live 1-minute bars (pure logic).

The strategy only judges COMPLETED 15-minute candles. This module watches the
15-minute candle while it is still forming (built from 1-minute bars) and
raises an early warning when:

  * price is already above the breakout confirmation price, and
  * the volume so far, projected to a full 15 minutes, is at least the
    required ratio of the prior 20-candle average, and
  * at least `min_elapsed_minutes` of the candle have passed (so one early
    spike can't trigger it), and
  * the close so far is in the upper part of the candle's range.

It is an ALERT only. Orders still wait for the completed-candle rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

CANDLE_MINUTES = 15


def bucket_start(ts: datetime, minutes: int = CANDLE_MINUTES) -> datetime:
    """Start of the 15-minute candle containing ts (aligned to :00/:15/:30/:45)."""
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    floored = ts.replace(second=0, microsecond=0)
    return floored - timedelta(minutes=floored.minute % minutes)


@dataclass
class FormingCandle:
    start: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    last_bar_start: datetime
    bars: int = 1

    @classmethod
    def from_bar(cls, start: datetime, bar_time: datetime, o, h, l, c, v) -> "FormingCandle":
        return cls(start, float(o), float(h), float(l), float(c), float(v), bar_time)

    def add(self, bar_time: datetime, o, h, l, c, v) -> None:
        if bar_time <= self.last_bar_start:
            return                          # duplicate / out-of-order bar
        self.high = max(self.high, float(h))
        self.low = min(self.low, float(l))
        self.close = float(c)
        self.volume += float(v)
        self.last_bar_start = bar_time
        self.bars += 1

    @property
    def elapsed_minutes(self) -> int:
        """Minutes covered so far (a 1-minute bar stamped 10:05 covers 10:05-10:06)."""
        return int((self.last_bar_start - self.start).total_seconds() // 60) + 1


@dataclass
class Baseline:
    """From the previous 20 COMPLETED 15-minute candles (database)."""
    confirmation_price: float
    average_volume: float
    last_completed_start: datetime


@dataclass(frozen=True)
class EarlyRules:
    min_volume_ratio: float = 1.20
    min_elapsed_minutes: int = 5
    min_close_location: float = 0.70


@dataclass
class EarlySignal:
    triggered: bool
    reasons: list[str] = field(default_factory=list)
    projected_volume_ratio: float | None = None
    close_location: float | None = None


def baseline_is_current(baseline: Baseline, forming_start: datetime) -> bool:
    """The stored candles must reach the candle right before the forming one,
    otherwise the breakout level is stale (sync hasn't run)."""
    return baseline.last_completed_start >= forming_start - timedelta(minutes=CANDLE_MINUTES)


def evaluate(candle: FormingCandle, baseline: Baseline, rules: EarlyRules = EarlyRules()) -> EarlySignal:
    reasons: list[str] = []
    if not baseline_is_current(baseline, candle.start):
        return EarlySignal(False, ["Baseline candles are stale; waiting for market-data sync"])

    elapsed = candle.elapsed_minutes
    if elapsed < rules.min_elapsed_minutes:
        return EarlySignal(False, [f"Only {elapsed} min into the candle"])

    projected = candle.volume * CANDLE_MINUTES / elapsed
    ratio = projected / baseline.average_volume if baseline.average_volume > 0 else 0.0
    candle_range = candle.high - candle.low
    close_location = (candle.close - candle.low) / candle_range if candle_range > 0 else 0.0

    price_ok = candle.close > baseline.confirmation_price
    volume_ok = ratio >= rules.min_volume_ratio
    strength_ok = candle.close > candle.open and close_location >= rules.min_close_location

    reasons.append(
        f"Price {candle.close:.2f} {'above' if price_ok else 'below'} breakout level "
        f"{baseline.confirmation_price:.2f}"
    )
    reasons.append(f"Projected volume {ratio:.2f}x the prior average after {elapsed} min")
    reasons.append(f"Close at {close_location:.0%} of the candle's range")

    return EarlySignal(
        triggered=price_ok and volume_ok and strength_ok,
        reasons=reasons,
        projected_volume_ratio=round(ratio, 3),
        close_location=round(close_location, 3),
    )
