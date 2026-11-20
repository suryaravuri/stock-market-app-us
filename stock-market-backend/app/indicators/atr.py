from collections.abc import Sequence


def calculate_atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float | None]:

    if period <= 0:
        raise ValueError("ATR period must be greater than 0")

    if not (
        len(highs) == len(lows) == len(closes)
    ):
        raise ValueError(
            "High, low, and close lists must have the same length"
        )

    if not closes:
        return []

    result: list[float | None] = [None] * len(closes)

    true_ranges: list[float] = [0.0] * len(closes)

    true_ranges[0] = highs[0] - lows[0]

    for i in range(1, len(closes)):
        high_low = highs[i] - lows[i]
        high_prev_close = abs(
            highs[i] - closes[i - 1]
        )
        low_prev_close = abs(
            lows[i] - closes[i - 1]
        )

        true_ranges[i] = max(
            high_low,
            high_prev_close,
            low_prev_close,
        )

    if len(closes) < period:
        return result

    initial_atr = sum(
        true_ranges[:period]
    ) / period

    result[period - 1] = initial_atr

    previous_atr = initial_atr

    for i in range(period, len(closes)):
        current_atr = (
            (previous_atr * (period - 1))
            + true_ranges[i]
        ) / period

        result[i] = current_atr
        previous_atr = current_atr

    return result