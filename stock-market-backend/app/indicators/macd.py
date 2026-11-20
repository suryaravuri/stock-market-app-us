from collections.abc import Sequence

from app.indicators.ema import calculate_ema


def calculate_macd(
    values: Sequence[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[
    list[float | None],
    list[float | None],
    list[float | None],
]:

    fast_ema = calculate_ema(values, fast_period)
    slow_ema = calculate_ema(values, slow_period)

    macd_line: list[float | None] = [None] * len(values)

    for i in range(len(values)):
        if fast_ema[i] is not None and slow_ema[i] is not None:
            macd_line[i] = fast_ema[i] - slow_ema[i]

    valid_macd = [
        value
        for value in macd_line
        if value is not None
    ]

    signal_values = calculate_ema(
        valid_macd,
        signal_period,
    )

    signal_line: list[float | None] = [None] * len(values)

    valid_index = 0

    for i, macd_value in enumerate(macd_line):
        if macd_value is not None:
            signal_line[i] = signal_values[valid_index]
            valid_index += 1

    histogram: list[float | None] = [None] * len(values)

    for i in range(len(values)):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram[i] = macd_line[i] - signal_line[i]

    return macd_line, signal_line, histogram