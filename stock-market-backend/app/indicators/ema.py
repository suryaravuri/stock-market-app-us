from collections.abc import Sequence


def calculate_ema(
    values: Sequence[float],
    period: int,
) -> list[float | None]:

    if period <= 0:
        raise ValueError("EMA period must be greater than 0")

    if not values:
        return []

    result: list[float | None] = [None] * len(values)

    if len(values) < period:
        return result

    # Initial EMA starts with SMA
    initial_sma = sum(values[:period]) / period

    result[period - 1] = initial_sma

    multiplier = 2 / (period + 1)

    previous_ema = initial_sma

    for index in range(period, len(values)):
        current_value = values[index]

        current_ema = (
            (current_value - previous_ema)
            * multiplier
            + previous_ema
        )

        result[index] = current_ema
        previous_ema = current_ema

    return result