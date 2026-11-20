from dataclasses import dataclass


@dataclass
class BreakoutConfirmationResult:
    status: str
    confirmed: bool
    breakout_level: float | None
    confirmation_price: float | None
    buffer_price: float | None
    volume_ratio: float | None
    candle_range: float | None
    body_ratio: float | None
    close_location: float | None
    upper_wick_ratio: float | None
    price_confirmed: bool
    volume_confirmed: bool
    candle_quality_confirmed: bool
    reasons: list[str]


def confirm_long_breakout(
    *,
    latest_close: float,
    latest_open: float,
    latest_high: float,
    latest_low: float,
    latest_volume: float,
    prior_highs: list[float],
    prior_volumes: list[float],
    atr_14: float | None,
    lookback: int = 20,
    atr_buffer: float = 0.05,
    min_volume_ratio: float = 1.20,
    min_body_ratio: float = 0.50,
    min_close_location: float = 0.70,
    max_upper_wick_ratio: float = 0.30,
) -> BreakoutConfirmationResult:
    """Confirm a long breakout with price, volume, and candle-quality gates.

    Candle-quality protection rejects spike-like breakouts that close weakly,
    have too-small real bodies, or leave a large upper wick. This function
    evaluates a signal only; it never submits an order.
    """
    if atr_14 is None or atr_14 <= 0:
        return BreakoutConfirmationResult(
            status="INSUFFICIENT_DATA", confirmed=False,
            breakout_level=None, confirmation_price=None, buffer_price=None,
            volume_ratio=None, candle_range=None, body_ratio=None,
            close_location=None, upper_wick_ratio=None,
            price_confirmed=False, volume_confirmed=False,
            candle_quality_confirmed=False,
            reasons=["ATR is unavailable for breakout confirmation"],
        )

    highs = prior_highs[-lookback:]
    volumes = prior_volumes[-lookback:]
    valid_volumes = [volume for volume in volumes if volume > 0]
    if len(highs) < lookback or not valid_volumes:
        return BreakoutConfirmationResult(
            status="INSUFFICIENT_DATA", confirmed=False,
            breakout_level=None, confirmation_price=None, buffer_price=None,
            volume_ratio=None, candle_range=None, body_ratio=None,
            close_location=None, upper_wick_ratio=None,
            price_confirmed=False, volume_confirmed=False,
            candle_quality_confirmed=False,
            reasons=[f"At least {lookback} prior candles with volume are required"],
        )

    breakout_level = max(highs)
    buffer_price = atr_14 * atr_buffer
    confirmation_price = breakout_level + buffer_price
    average_volume = sum(valid_volumes) / len(valid_volumes)
    volume_ratio = latest_volume / average_volume if average_volume > 0 else 0.0

    candle_range = latest_high - latest_low
    bullish_candle = latest_close > latest_open
    if candle_range > 0:
        body_ratio = abs(latest_close - latest_open) / candle_range
        close_location = (latest_close - latest_low) / candle_range
        upper_wick = latest_high - max(latest_open, latest_close)
        upper_wick_ratio = max(0.0, upper_wick) / candle_range
    else:
        body_ratio = 0.0
        close_location = 0.0
        upper_wick_ratio = 1.0

    body_confirmed = bullish_candle and body_ratio >= min_body_ratio
    close_quality_confirmed = close_location >= min_close_location
    upper_wick_confirmed = upper_wick_ratio <= max_upper_wick_ratio
    candle_quality_confirmed = (
        body_confirmed and close_quality_confirmed and upper_wick_confirmed
    )

    price_confirmed = latest_close > confirmation_price
    volume_confirmed = volume_ratio >= min_volume_ratio

    reasons: list[str] = []
    if price_confirmed:
        reasons.append(
            f"Close {latest_close:.4f} cleared breakout confirmation price {confirmation_price:.4f}"
        )
    else:
        reasons.append(
            f"Close {latest_close:.4f} has not cleared breakout confirmation price {confirmation_price:.4f}"
        )
    reasons.append(f"Volume is {volume_ratio:.2f}x the prior {lookback}-candle average")
    reasons.append(
        f"Candle body is {body_ratio:.0%} of range; close is at {close_location:.0%} of range; "
        f"upper wick is {upper_wick_ratio:.0%} of range"
    )

    if not price_confirmed:
        status = "WAITING_FOR_PRICE"
    elif not volume_confirmed:
        status = "PRICE_BREAKOUT_LOW_VOLUME"
    elif not candle_quality_confirmed:
        status = "PRICE_BREAKOUT_WEAK_CANDLE"
    else:
        status = "BREAKOUT_CONFIRMED"

    confirmed = price_confirmed and volume_confirmed and candle_quality_confirmed

    if confirmed:
        reasons.append("Price, volume, and breakout candle quality all passed")
    else:
        if price_confirmed and not volume_confirmed:
            reasons.append(
                f"Volume confirmation requires at least {min_volume_ratio:.2f}x average volume"
            )
        if price_confirmed and volume_confirmed and not body_confirmed:
            reasons.append(
                f"Breakout candle requires a bullish body covering at least {min_body_ratio:.0%} of its range"
            )
        if price_confirmed and volume_confirmed and not close_quality_confirmed:
            reasons.append(
                f"Breakout candle must close in the upper {1-min_close_location:.0%} of its range"
            )
        if price_confirmed and volume_confirmed and not upper_wick_confirmed:
            reasons.append(
                f"Upper wick must be no more than {max_upper_wick_ratio:.0%} of candle range"
            )

    return BreakoutConfirmationResult(
        status=status,
        confirmed=confirmed,
        breakout_level=round(breakout_level, 4),
        confirmation_price=round(confirmation_price, 4),
        buffer_price=round(buffer_price, 4),
        volume_ratio=round(volume_ratio, 2),
        candle_range=round(candle_range, 4),
        body_ratio=round(body_ratio, 4),
        close_location=round(close_location, 4),
        upper_wick_ratio=round(upper_wick_ratio, 4),
        price_confirmed=price_confirmed,
        volume_confirmed=volume_confirmed,
        candle_quality_confirmed=candle_quality_confirmed,
        reasons=reasons,
    )
