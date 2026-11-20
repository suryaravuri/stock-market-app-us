from dataclasses import dataclass
from typing import Sequence


@dataclass
class PriceLevel:
    price: float
    level_type: str
    strength: float
    touches: int
    distance_from_price: float


def detect_support_resistance(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    atr: float | None,
    swing_window: int = 3,
    cluster_threshold_atr: float = 0.35,
    max_levels: int = 5,
) -> dict[str, list[PriceLevel]]:

    if not highs or not lows or not closes:
        return {
            "supports": [],
            "resistances": [],
        }

    if not (
        len(highs)
        == len(lows)
        == len(closes)
    ):
        raise ValueError(
            "High, low, and close arrays must have equal length"
        )

    if swing_window <= 0:
        raise ValueError(
            "swing_window must be greater than 0"
        )

    current_price = closes[-1]

    swing_highs = _find_swing_highs(
        highs,
        swing_window,
    )

    swing_lows = _find_swing_lows(
        lows,
        swing_window,
    )

    threshold = _calculate_cluster_threshold(
        current_price=current_price,
        atr=atr,
        cluster_threshold_atr=cluster_threshold_atr,
    )

    resistance_clusters = _cluster_levels(
        swing_highs,
        threshold,
    )

    support_clusters = _cluster_levels(
        swing_lows,
        threshold,
    )

    supports = _build_levels(
        clusters=support_clusters,
        current_price=current_price,
        level_type="SUPPORT",
    )

    resistances = _build_levels(
        clusters=resistance_clusters,
        current_price=current_price,
        level_type="RESISTANCE",
    )

    # Support should normally be below current price.
    supports = [
        level
        for level in supports
        if level.price <= current_price
    ]

    # Resistance should normally be above current price.
    resistances = [
        level
        for level in resistances
        if level.price >= current_price
    ]

    supports.sort(
        key=lambda level: (
            level.distance_from_price,
            -level.strength,
        )
    )

    resistances.sort(
        key=lambda level: (
            level.distance_from_price,
            -level.strength,
        )
    )

    return {
        "supports": supports[:max_levels],
        "resistances": resistances[:max_levels],
    }


def _find_swing_highs(
    highs: Sequence[float],
    window: int,
) -> list[float]:

    result: list[float] = []

    for index in range(
        window,
        len(highs) - window,
    ):
        current = highs[index]

        left = highs[
            index - window:index
        ]

        right = highs[
            index + 1:index + window + 1
        ]

        if (
            current >= max(left)
            and current >= max(right)
        ):
            result.append(current)

    return result


def _find_swing_lows(
    lows: Sequence[float],
    window: int,
) -> list[float]:

    result: list[float] = []

    for index in range(
        window,
        len(lows) - window,
    ):
        current = lows[index]

        left = lows[
            index - window:index
        ]

        right = lows[
            index + 1:index + window + 1
        ]

        if (
            current <= min(left)
            and current <= min(right)
        ):
            result.append(current)

    return result


def _calculate_cluster_threshold(
    current_price: float,
    atr: float | None,
    cluster_threshold_atr: float,
) -> float:

    if atr is not None and atr > 0:
        return atr * cluster_threshold_atr

    # Fallback if ATR is unavailable.
    return current_price * 0.003


def _cluster_levels(
    prices: Sequence[float],
    threshold: float,
) -> list[list[float]]:

    if not prices:
        return []

    sorted_prices = sorted(prices)

    clusters: list[list[float]] = []

    current_cluster = [
        sorted_prices[0]
    ]

    for price in sorted_prices[1:]:

        cluster_average = (
            sum(current_cluster)
            / len(current_cluster)
        )

        if abs(
            price - cluster_average
        ) <= threshold:

            current_cluster.append(price)

        else:
            clusters.append(
                current_cluster
            )

            current_cluster = [
                price
            ]

    clusters.append(
        current_cluster
    )

    return clusters


def _build_levels(
    clusters: Sequence[Sequence[float]],
    current_price: float,
    level_type: str,
) -> list[PriceLevel]:

    levels: list[PriceLevel] = []

    for cluster in clusters:

        price = (
            sum(cluster)
            / len(cluster)
        )

        touches = len(cluster)

        distance = abs(
            current_price - price
        )

        distance_pct = (
            distance
            / current_price
            * 100
        )

        # Confidence-based support/resistance strength.
        # Repeated tests make a level more reliable.
        if touches <= 1:
            strength = 25.0
        elif touches == 2:
            strength = 45.0
        elif touches == 3:
            strength = 65.0
        elif touches == 4:
            strength = 85.0
        else:
            strength = 100.0

        levels.append(
            PriceLevel(
                price=round(price, 4),
                level_type=level_type,
                strength=round(strength, 2),
                touches=touches,
                distance_from_price=round(
                    distance_pct,
                    4,
                ),
            )
        )

    return levels