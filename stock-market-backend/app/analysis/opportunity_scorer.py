from dataclasses import dataclass


@dataclass
class ScoreReason:
    code: str
    description: str
    score: int


@dataclass
class OpportunityResult:
    score: int
    classification: str
    reasons: list[ScoreReason]


def calculate_opportunity_score(
    current_price: float,
    ema_9: float | None,
    ema_20: float | None,
    ema_50: float | None,
    rsi_14: float | None,
    macd: float | None,
    macd_signal: float | None,
    macd_histogram: float | None,
    session_vwap: float | None,
    nearest_support: float | None,
    nearest_resistance: float | None,
    atr_14: float | None,
    nearest_support_strength: float | None = None,
    nearest_resistance_strength: float | None = None,
) -> OpportunityResult:

    score = 0
    reasons: list[ScoreReason] = []

    # ---------------------------------
    # 1. Short-term trend
    # ---------------------------------

    if ema_9 is not None:
        if current_price > ema_9:
            score += 10
            reasons.append(
                ScoreReason(
                    code="ABOVE_EMA_9",
                    description="Price is above EMA 9",
                    score=10,
                )
            )
        else:
            score -= 10
            reasons.append(
                ScoreReason(
                    code="BELOW_EMA_9",
                    description="Price is below EMA 9",
                    score=-10,
                )
            )

    if ema_20 is not None:
        if current_price > ema_20:
            score += 10
            reasons.append(
                ScoreReason(
                    code="ABOVE_EMA_20",
                    description="Price is above EMA 20",
                    score=10,
                )
            )
        else:
            score -= 10
            reasons.append(
                ScoreReason(
                    code="BELOW_EMA_20",
                    description="Price is below EMA 20",
                    score=-10,
                )
            )

    # ---------------------------------
    # 2. Medium-term trend
    # ---------------------------------

    if ema_50 is not None:
        if current_price > ema_50:
            score += 10
            reasons.append(
                ScoreReason(
                    code="ABOVE_EMA_50",
                    description="Price is above EMA 50",
                    score=10,
                )
            )
        else:
            score -= 5
            reasons.append(
                ScoreReason(
                    code="BELOW_EMA_50",
                    description="Price is below EMA 50",
                    score=-5,
                )
            )

    # ---------------------------------
    # 3. EMA alignment
    # ---------------------------------

    if (
        ema_9 is not None
        and ema_20 is not None
        and ema_50 is not None
    ):
        if ema_9 > ema_20 > ema_50:
            score += 15
            reasons.append(
                ScoreReason(
                    code="BULLISH_EMA_ALIGNMENT",
                    description="EMA 9 > EMA 20 > EMA 50",
                    score=15,
                )
            )

        elif ema_9 < ema_20 < ema_50:
            score -= 15
            reasons.append(
                ScoreReason(
                    code="BEARISH_EMA_ALIGNMENT",
                    description="EMA 9 < EMA 20 < EMA 50",
                    score=-15,
                )
            )

    # ---------------------------------
    # 4. RSI
    # ---------------------------------

    if rsi_14 is not None:

        if 50 <= rsi_14 <= 65:
            score += 10
            reasons.append(
                ScoreReason(
                    code="HEALTHY_RSI",
                    description="RSI shows positive momentum",
                    score=10,
                )
            )

        elif rsi_14 >= 75:
            score -= 10
            reasons.append(
                ScoreReason(
                    code="OVERBOUGHT_RSI",
                    description="RSI is highly extended",
                    score=-10,
                )
            )

        elif rsi_14 < 40:
            score -= 10
            reasons.append(
                ScoreReason(
                    code="WEAK_RSI",
                    description="RSI shows weak momentum",
                    score=-10,
                )
            )

    # ---------------------------------
    # 5. MACD
    # ---------------------------------

    if (
        macd is not None
        and macd_signal is not None
    ):
        if macd > macd_signal:
            score += 10
            reasons.append(
                ScoreReason(
                    code="MACD_ABOVE_SIGNAL",
                    description="MACD is above signal line",
                    score=10,
                )
            )
        else:
            score -= 10
            reasons.append(
                ScoreReason(
                    code="MACD_BELOW_SIGNAL",
                    description="MACD is below signal line",
                    score=-10,
                )
            )

    if macd_histogram is not None:
        if macd_histogram > 0:
            score += 5
            reasons.append(
                ScoreReason(
                    code="POSITIVE_MACD_HISTOGRAM",
                    description="MACD histogram is positive",
                    score=5,
                )
            )
        elif macd_histogram < 0:
            score -= 5
            reasons.append(
                ScoreReason(
                    code="NEGATIVE_MACD_HISTOGRAM",
                    description="MACD histogram is negative",
                    score=-5,
                )
            )

    # ---------------------------------
    # 6. VWAP
    # ---------------------------------

    if session_vwap is not None:
        if current_price > session_vwap:
            score += 10
            reasons.append(
                ScoreReason(
                    code="ABOVE_VWAP",
                    description="Price is above session VWAP",
                    score=10,
                )
            )
        else:
            score -= 10
            reasons.append(
                ScoreReason(
                    code="BELOW_VWAP",
                    description="Price is below session VWAP",
                    score=-10,
                )
            )

    # ---------------------------------
    # 7. Support / resistance
    #    Confidence + ATR-normalized proximity
    # ---------------------------------

    if atr_14 is not None and atr_14 > 0:

        if nearest_support is not None:
            support_distance = current_price - nearest_support
            if support_distance >= 0:
                support_atr_distance = support_distance / atr_14
                multiplier = _atr_proximity_multiplier(support_atr_distance)
                if multiplier > 0:
                    base_score = _support_proximity_score(nearest_support_strength)
                    support_score = _scaled_score(base_score, multiplier)
                    score += support_score
                    reasons.append(
                        ScoreReason(
                            code="NEAR_SUPPORT",
                            description=(
                                f"Support is {support_atr_distance:.2f} ATR away "
                                f"(strength {nearest_support_strength or 0:g}, "
                                f"proximity x{multiplier:.2f})"
                            ),
                            score=support_score,
                        )
                    )

        if nearest_resistance is not None:
            resistance_distance = nearest_resistance - current_price
            if resistance_distance >= 0:
                resistance_atr_distance = resistance_distance / atr_14
                multiplier = _atr_proximity_multiplier(resistance_atr_distance)
                if multiplier > 0:
                    base_penalty = _resistance_proximity_penalty(nearest_resistance_strength)
                    resistance_penalty = _scaled_score(base_penalty, multiplier)
                    score += resistance_penalty
                    reasons.append(
                        ScoreReason(
                            code="NEAR_RESISTANCE",
                            description=(
                                f"Resistance is {resistance_atr_distance:.2f} ATR away "
                                f"(strength {nearest_resistance_strength or 0:g}, "
                                f"proximity x{multiplier:.2f})"
                            ),
                            score=resistance_penalty,
                        )
                    )

    # ---------------------------------
    # 8. Normalize
    # ---------------------------------

    score = max(
        -100,
        min(100, score),
    )

    classification = _classify_score(
        score
    )

    return OpportunityResult(
        score=score,
        classification=classification,
        reasons=reasons,
    )


def _atr_proximity_multiplier(atr_distance: float) -> float:
    """Weight a level by its distance from price, measured in ATR units."""
    if atr_distance <= 0.10:
        return 1.00
    if atr_distance <= 0.25:
        return 0.85
    if atr_distance <= 0.50:
        return 0.65
    if atr_distance <= 0.75:
        return 0.45
    if atr_distance <= 1.00:
        return 0.25
    return 0.0


def _scaled_score(base_score: int, multiplier: float) -> int:
    """Scale a signed score while preserving a non-zero effect when applicable."""
    scaled = round(base_score * multiplier)
    if scaled == 0 and base_score != 0 and multiplier > 0:
        return 1 if base_score > 0 else -1
    return scaled


def _support_proximity_score(
    strength: float | None,
) -> int:
    """Positive score for nearby support, scaled by confidence."""

    strength = strength or 0.0

    if strength >= 80:
        return 10
    if strength >= 60:
        return 7
    if strength >= 40:
        return 4
    return 2


def _resistance_proximity_penalty(
    strength: float | None,
) -> int:
    """Penalty for nearby resistance, scaled by confidence."""

    strength = strength or 0.0

    if strength >= 80:
        return -15
    if strength >= 60:
        return -10
    if strength >= 40:
        return -6
    return -3


def _classify_score(
    score: int,
) -> str:

    if score >= 60:
        return "STRONG"

    if score >= 30:
        return "WATCH"

    if score > -30:
        return "NEUTRAL"

    return "AVOID"