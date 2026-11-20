"""Support-bounce entry: buy near support, sell at resistance (pure logic).

A long entry triggers on a COMPLETED 15-minute candle when:

  1. its low came down into a support zone (support +/- zone) without
     breaking far below it,
  2. it closed back ABOVE support as a green candle with a reasonable close
     (buyers defended the level),
  3. the bigger trend is not bearish (trend score >= minimum),
  4. the nearest resistance above gives at least `min_rr` reward per unit of
     risk, where risk = entry - (support - stop buffer).

Exit plan: take profit at the nearest resistance; stop below support, at
least `min_stop_atr` ATR under the entry (position size shrinks to match).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BounceRules:
    zone_atr: float = 0.5              # how close the low must come to support
    break_tolerance_atr: float = 0.25  # how far below support a wick may poke
    stop_buffer_atr: float = 0.25      # stop placed this far below support
    # ...but never closer than this to the entry. A stop only 0.25 ATR under
    # support gets hit by an ordinary re-test of the level (NXPI 2026-11-16:
    # stop 0.8 ATR from entry, wicked 0.3 ATR through support, stopped out).
    min_stop_atr: float = 1.0
    min_rr: float = 1.5
    min_trend_score: float = 0.0       # multi-timeframe score must not be bearish
    min_close_location: float = 0.5    # close in the upper half of the candle
    # Zone sized to the LEVEL timeframe too (daily levels for SWING): zone =
    # max(zone_atr x 15-min ATR, level_zone_atr x level ATR). 0 = off.
    # COST 2026-11-20: low 1100.29 vs support 1096.46 was outside a $2 zone.
    level_zone_atr: float = 0.0
    # >1 = the touch may happen up to (confirm_bars - 1) candles earlier and
    # the green close on this one (dip, hesitate, turn up). 1 = same candle.
    confirm_bars: int = 1


@dataclass
class BounceDecision:
    triggered: bool
    reasons: list[str] = field(default_factory=list)
    support: float | None = None
    resistance: float | None = None
    entry: float | None = None
    stop_loss: float | None = None
    target_1: float | None = None
    target_2: float | None = None
    rr_1: float | None = None


def evaluate_bounce(
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
    levels: list[float],
    atr: float | None,
    trend_score: float | None,
    rules: BounceRules = BounceRules(),
    level_atr: float | None = None,
    prev_lows: list[float] | None = None,
) -> BounceDecision:
    """`levels`: all support/resistance prices (any order); they are split
    into supports (below) and resistances (above) using this candle.
    `level_atr`: ATR of the timeframe the levels came from (for level_zone_atr).
    `prev_lows`: lows of the previous candles, most recent first (for confirm_bars>1)."""
    if not atr or atr <= 0:
        return BounceDecision(False, ["ATR unavailable"])

    zone = rules.zone_atr * atr
    if rules.level_zone_atr > 0 and level_atr:
        zone = max(zone, rules.level_zone_atr * level_atr)
    tolerance = rules.break_tolerance_atr * atr

    def in_zone(value: float | None, s: float) -> bool:
        return value is not None and s - tolerance <= value <= s + zone

    earlier = list(prev_lows or [])[: max(0, rules.confirm_bars - 1)]

    # Supports tested: this candle's low (or, with confirm_bars>1, a recent
    # candle's low) reached the zone, this candle held above the break
    # tolerance and closed back above support.
    tested = sorted(
        (
            s for s in levels
            if close > s and (
                in_zone(low, s)
                or (low >= s - tolerance and any(in_zone(x, s) for x in earlier))
            )
        ),
        reverse=True,
    )
    if not tested:
        below = [s for s in levels if s < close]
        if not below:
            return BounceDecision(False, ["Price is not bouncing off a support level (no support below price)"])
        nearest = max(below)
        gap = low - nearest
        where = "above" if gap >= 0 else "below (support broken)"
        return BounceDecision(False, [
            f"Price is not bouncing off a support level: nearest support {nearest:.2f}, "
            f"candle low {low:.2f} is {abs(gap):.2f} ({abs(gap) / atr:.1f} ATR, "
            f"{abs(gap) / close:.1%}) {where}; zone is {zone:.2f}"
        ], support=None)
    support = tested[0]

    decision = BounceDecision(False, support=support, entry=close)
    reasons = decision.reasons

    candle_range = high - low
    close_location = (close - low) / candle_range if candle_range > 0 else 0.0
    if close <= open_:
        reasons.append("Bounce candle is not green")
    if close_location < rules.min_close_location:
        reasons.append(f"Weak close ({close_location:.0%} of the candle's range)")
    if trend_score is not None and trend_score < rules.min_trend_score:
        reasons.append(f"Trend score {trend_score:.0f} is bearish")

    stop = min(
        support - rules.stop_buffer_atr * atr,
        close - rules.min_stop_atr * atr,
    )
    risk = close - stop
    decision.stop_loss = round(stop, 4)

    resistances = sorted(level for level in levels if level > close)
    if not resistances:
        reasons.append("No resistance above to sell at")
        return decision
    decision.resistance = resistances[0]
    decision.target_1 = resistances[0]
    decision.target_2 = resistances[1] if len(resistances) > 1 else None

    decision.rr_1 = round((resistances[0] - close) / risk, 2) if risk > 0 else None
    if decision.rr_1 is None or decision.rr_1 < rules.min_rr:
        reasons.append(
            f"Reward/risk {decision.rr_1} to resistance {resistances[0]:.2f} is below {rules.min_rr}"
        )

    if not reasons:
        decision.triggered = True
        reasons.append(
            f"Bounced off support {support:.2f}: buy {close:.2f}, stop {stop:.2f}, "
            f"sell at resistance {resistances[0]:.2f} (RR {decision.rr_1})"
        )
    return decision


def reprice_bounce(
    *,
    support: float,
    resistance: float | None,
    target_2: float | None,
    live_price: float,
    atr: float,
    rules: BounceRules = BounceRules(),
) -> BounceDecision:
    """Re-check a triggered bounce against the price right before ordering.

    The signal is judged on a completed candle, but the order fills at the
    live price a few minutes later (NXPI 2026-11-16: signal 260.45, fill
    259.61, support 259.54). Skip if price is already back at support;
    otherwise rebuild the stop and reward/risk from the live price.
    """
    decision = BounceDecision(False, support=support, resistance=resistance, entry=live_price)
    if live_price <= support:
        decision.reasons.append(
            f"Live price {live_price:.2f} is back at/below support {support:.2f}: "
            "bounce failed before the order"
        )
        return decision
    if resistance is None or live_price >= resistance:
        decision.reasons.append("Live price is already at resistance: nothing left to gain")
        return decision

    stop = min(support - rules.stop_buffer_atr * atr, live_price - rules.min_stop_atr * atr)
    risk = live_price - stop
    decision.stop_loss = round(stop, 4)
    decision.target_1 = resistance
    decision.target_2 = target_2
    decision.rr_1 = round((resistance - live_price) / risk, 2) if risk > 0 else None
    if decision.rr_1 is None or decision.rr_1 < rules.min_rr:
        decision.reasons.append(
            f"At live price {live_price:.2f} reward/risk {decision.rr_1} is below {rules.min_rr}"
        )
        return decision
    decision.triggered = True
    decision.reasons.append(
        f"Live re-check OK: buy {live_price:.2f}, stop {stop:.2f}, "
        f"sell at resistance {resistance:.2f} (RR {decision.rr_1})"
    )
    return decision
