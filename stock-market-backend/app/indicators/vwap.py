from collections.abc import Sequence
from datetime import datetime


def calculate_session_vwap(
    timestamps: Sequence[datetime],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
) -> list[float | None]:

    if not (
        len(timestamps)
        == len(highs)
        == len(lows)
        == len(closes)
        == len(volumes)
    ):
        raise ValueError(
            "All input lists must have the same length"
        )

    if not timestamps:
        return []

    result: list[float | None] = []

    current_session = None
    cumulative_price_volume = 0.0
    cumulative_volume = 0.0

    for timestamp, high, low, close, volume in zip(
        timestamps,
        highs,
        lows,
        closes,
        volumes,
    ):

        session_date = timestamp.date()

        if session_date != current_session:
            current_session = session_date
            cumulative_price_volume = 0.0
            cumulative_volume = 0.0

        typical_price = (
            high + low + close
        ) / 3.0

        cumulative_price_volume += (
            typical_price * volume
        )

        cumulative_volume += volume

        if cumulative_volume == 0:
            result.append(None)
        else:
            result.append(
                cumulative_price_volume
                / cumulative_volume
            )

    return result