"""Candle-by-candle breakout diagnostics (pure, no database).

Re-runs the SAME rule the strategy uses (confirm_long_breakout) for each of
the most recent candles, each against its own preceding `lookback` eligible
candles, so you can see exactly which gate (price, volume, candle quality)
passed or failed on every candle.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.strategies.breakout_confirmation import confirm_long_breakout


@dataclass(frozen=True)
class Thresholds:
    lookback: int = 20
    atr_buffer: float = 0.05
    min_volume_ratio: float = 1.20
    min_body_ratio: float = 0.50
    min_close_location: float = 0.70
    max_upper_wick_ratio: float = 0.30


def diagnose(
    candles: list[dict],
    atr: list[float | None],
    *,
    rows: int = 30,
    thresholds: Thresholds = Thresholds(),
) -> list[dict]:
    """candles: oldest -> newest, ONLY eligible regular-session candles, each a
    dict with time/open/high/low/close/volume. atr: same length as candles."""
    if len(atr) != len(candles):
        raise ValueError("atr must have one value per candle")

    results: list[dict] = []
    start = max(thresholds.lookback, len(candles) - rows)
    for i in range(start, len(candles)):
        candle = candles[i]
        prior = candles[i - thresholds.lookback:i]
        prior_volumes = [float(c["volume"]) for c in prior]
        positive = [v for v in prior_volumes if v > 0]
        average_volume = sum(positive) / len(positive) if positive else None

        result = confirm_long_breakout(
            latest_close=float(candle["close"]),
            latest_open=float(candle["open"]),
            latest_high=float(candle["high"]),
            latest_low=float(candle["low"]),
            latest_volume=float(candle["volume"]),
            prior_highs=[float(c["high"]) for c in prior],
            prior_volumes=prior_volumes,
            atr_14=atr[i],
            lookback=thresholds.lookback,
            atr_buffer=thresholds.atr_buffer,
            min_volume_ratio=thresholds.min_volume_ratio,
            min_body_ratio=thresholds.min_body_ratio,
            min_close_location=thresholds.min_close_location,
            max_upper_wick_ratio=thresholds.max_upper_wick_ratio,
        )
        results.append({
            "time": candle["time"],
            "open": float(candle["open"]),
            "high": float(candle["high"]),
            "low": float(candle["low"]),
            "close": float(candle["close"]),
            "volume": float(candle["volume"]),
            "average_prior_volume": round(average_volume, 2) if average_volume else None,
            "volume_ratio": round(result.volume_ratio, 3) if result.volume_ratio is not None else None,
            "breakout_level": result.breakout_level,
            "confirmation_price": (
                round(result.confirmation_price, 4) if result.confirmation_price is not None else None
            ),
            "atr_14": round(atr[i], 4) if atr[i] is not None else None,
            "price_ok": result.price_confirmed,
            "volume_ok": result.volume_confirmed,
            "candle_ok": result.candle_quality_confirmed,
            "body_ratio": round(result.body_ratio, 3) if result.body_ratio is not None else None,
            "close_location": round(result.close_location, 3) if result.close_location is not None else None,
            "upper_wick_ratio": (
                round(result.upper_wick_ratio, 3) if result.upper_wick_ratio is not None else None
            ),
            "status": result.status,
        })
    return results


def summarize(rows: list[dict], thresholds: Thresholds = Thresholds()) -> dict:
    """Plain-language patterns across the diagnosed candles."""
    price_breaks = [r for r in rows if r["price_ok"]]
    low_volume_breaks = [r for r in price_breaks if not r["volume_ok"]]
    weak_candle_breaks = [r for r in price_breaks if r["volume_ok"] and not r["candle_ok"]]
    confirmed = [r for r in rows if r["status"] == "BREAKOUT_CONFIRMED"]

    notes: list[str] = []
    if len(price_breaks) >= 3 and len(low_volume_breaks) >= len(price_breaks) * 0.6:
        notes.append(
            "Price kept making new 20-candle highs but volume stayed under "
            f"{thresholds.min_volume_ratio:.2f}x the prior average. In a steady trend the "
            "breakout level rises with every candle and the average volume is already "
            "elevated, so this rule rarely confirms: it is built for breakouts out of a "
            "quiet range, not for entering an ongoing run."
        )
    if weak_candle_breaks:
        notes.append(
            f"{len(weak_candle_breaks)} candle(s) broke out with enough volume but failed the "
            "candle-quality check (small body, weak close or large upper wick)."
        )
    if not price_breaks:
        notes.append("No candle closed above its breakout confirmation price in this window.")

    return {
        "candles_checked": len(rows),
        "price_breakouts": len(price_breaks),
        "blocked_by_volume": len(low_volume_breaks),
        "blocked_by_candle_quality": len(weak_candle_breaks),
        "confirmed_breakouts": len(confirmed),
        "notes": notes,
    }
