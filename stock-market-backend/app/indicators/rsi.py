from collections.abc import Sequence


def calculate_rsi(
    values: Sequence[float],
    period: int = 14,
) -> list[float | None]:

    if period <= 0:
        raise ValueError("RSI period must be greater than 0")

    result: list[float | None] = [None] * len(values)

    if len(values) <= period:
        return result

    gains: list[float] = []
    losses: list[float] = []

    for index in range(1, period + 1):
        change = values[index] - values[index - 1]

        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    average_gain = sum(gains) / period
    average_loss = sum(losses) / period

    result[period] = _calculate_rsi_value(
        average_gain,
        average_loss,
    )

    for index in range(period + 1, len(values)):
        change = values[index] - values[index - 1]

        gain = max(change, 0)
        loss = max(-change, 0)

        # Wilder smoothing
        average_gain = (
            (average_gain * (period - 1)) + gain
        ) / period

        average_loss = (
            (average_loss * (period - 1)) + loss
        ) / period

        result[index] = _calculate_rsi_value(
            average_gain,
            average_loss,
        )

    return result


def _calculate_rsi_value(
    average_gain: float,
    average_loss: float,
) -> float:

    if average_loss == 0:
        return 100.0

    if average_gain == 0:
        return 0.0

    relative_strength = average_gain / average_loss

    return 100 - (
        100 / (1 + relative_strength)
    )