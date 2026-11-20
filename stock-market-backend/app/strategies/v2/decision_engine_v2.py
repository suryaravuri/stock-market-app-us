from dataclasses import dataclass

from app.strategies.v2.config_v2 import (
    DEFAULT_V2_CONFIG,
    STRATEGY_VERSION,
    V2Config,
)


@dataclass(frozen=True)
class DecisionResultV2:
    strategy_version: str
    action: str
    actionable: bool

    quality_score: int
    quality: str

    reasons: list[str]


def decide_long_setup_v2(
    *,
    overall_score: int,
    overall_classification: str,
    risk_reward_quality: str,
    rr_1: float | None,
    rr_2: float | None,
    current_price: float,
    nearest_support: float | None,
    nearest_resistance: float | None,
    atr_14: float | None,
    breakout_confirmed: bool = False,
    breakout_status: str | None = None,
    breakout_confirmation_price: float | None = None,
    config: V2Config = DEFAULT_V2_CONFIG,
) -> DecisionResultV2:

    classification = overall_classification.strip().upper()
    rr_quality = risk_reward_quality.strip().upper()

    reasons: list[str] = []

    # -------------------------------------------------
    # 1. Hard trend rejection
    # -------------------------------------------------

    if classification == "AVOID" or overall_score <= -30:
        return _result(
            action="AVOID",
            actionable=False,
            quality_score=0,
            reasons=[
                f"Multi-timeframe score is "
                f"{overall_score} ({classification})"
            ],
        )

    # -------------------------------------------------
    # 2. Candidate threshold
    #
    # V2 may OBSERVE candidates slightly earlier than
    # V1, but this does NOT make them actionable.
    # -------------------------------------------------

    if overall_score < config.minimum_score:
        return _result(
            action="NEUTRAL",
            actionable=False,
            quality_score=0,
            reasons=[
                f"Multi-timeframe score {overall_score} "
                f"is below V2 candidate threshold "
                f"{config.minimum_score}"
            ],
        )

    quality_score = 0

    # -------------------------------------------------
    # 3. Trend quality
    # Maximum: 30
    # -------------------------------------------------

    if overall_score >= config.strong_score:
        quality_score += 30
        reasons.append(
            f"Strong multi-timeframe score: {overall_score}"
        )
    elif overall_score >= 30:
        quality_score += 22
        reasons.append(
            f"Qualified multi-timeframe score: {overall_score}"
        )
    else:
        quality_score += 12
        reasons.append(
            f"Early V2 candidate score: {overall_score}"
        )

    # -------------------------------------------------
    # 4. Risk / reward quality
    # Maximum: 30
    # -------------------------------------------------

    if rr_quality == "GOOD":
        quality_score += 30
        reasons.append("Risk/reward quality is GOOD")

    elif rr_quality == "ACCEPTABLE":
        quality_score += 20
        reasons.append(
            "Risk/reward quality is ACCEPTABLE"
        )

    else:
        reasons.append(
            f"Risk/reward quality is {rr_quality}"
        )

    # Extra validation from actual RR values.
    if rr_1 is not None and rr_1 < config.minimum_rr_1:
        reasons.append(
            f"RR1 {rr_1:.2f} is below minimum "
            f"{config.minimum_rr_1:.2f}"
        )

    if rr_2 is not None and rr_2 >= config.preferred_rr_2:
        quality_score += 5
        reasons.append(
            f"RR2 {rr_2:.2f} meets preferred target"
        )

    # -------------------------------------------------
    # 5. Distance from support
    # Maximum: 20
    # -------------------------------------------------

    support_atr_distance = _atr_distance(
        current_price=current_price,
        level_price=nearest_support,
        atr_14=atr_14,
    )

    if support_atr_distance is None:
        reasons.append(
            "Support ATR distance unavailable"
        )

    elif (
        support_atr_distance
        <= config.max_support_atr_distance
    ):
        quality_score += 20
        reasons.append(
            f"Price is {support_atr_distance:.2f} ATR "
            f"from support"
        )

    else:
        reasons.append(
            f"Price is extended "
            f"{support_atr_distance:.2f} ATR from support"
        )

    # -------------------------------------------------
    # 6. Breakout confirmation
    # Maximum: 20
    # -------------------------------------------------

    if breakout_confirmed:
        quality_score += 20
        reasons.append(
            "Breakout follow-through/retest confirmed"
        )
    else:
        reasons.append(
            "Waiting for breakout confirmation"
        )

        if breakout_confirmation_price is not None:
            reasons.append(
                "Confirmation level: "
                f"{breakout_confirmation_price:.4f}"
            )

        if breakout_status:
            reasons.append(
                f"Breakout status is {breakout_status}"
            )

    # -------------------------------------------------
    # 7. Quality classification
    # -------------------------------------------------

    quality = _quality_label(quality_score)

    # -------------------------------------------------
    # 8. Hard economic gates
    #
    # Quality score must NEVER override bad economics.
    # -------------------------------------------------

    if rr_quality == "POOR":
        return _result(
            action="WAIT_FOR_PULLBACK",
            actionable=False,
            quality_score=quality_score,
            reasons=reasons,
        )

    if (
        rr_1 is not None
        and rr_1 < config.minimum_rr_1
    ):
        return _result(
            action="WAIT_FOR_PULLBACK",
            actionable=False,
            quality_score=quality_score,
            reasons=reasons,
        )

    if (
        support_atr_distance is not None
        and support_atr_distance
        > config.max_support_atr_distance
    ):
        return _result(
            action="WAIT_FOR_PULLBACK",
            actionable=False,
            quality_score=quality_score,
            reasons=reasons,
        )

    # -------------------------------------------------
    # 9. Final V2 entry gate
    # -------------------------------------------------

    if (
        breakout_confirmed
        and rr_quality in {"GOOD", "ACCEPTABLE"}
        and quality_score >= config.minimum_entry_quality
    ):
        return _result(
            action="ENTRY_CONFIRMED",
            actionable=True,
            quality_score=quality_score,
            reasons=reasons,
        )

    # -------------------------------------------------
    # 10. Qualified candidate, but not entry-ready
    # -------------------------------------------------

    if rr_quality in {"GOOD", "ACCEPTABLE"}:
        return _result(
            action="WATCH",
            actionable=False,
            quality_score=quality_score,
            reasons=reasons,
        )

    return _result(
        action="NEUTRAL",
        actionable=False,
        quality_score=quality_score,
        reasons=reasons,
    )


def _result(
    *,
    action: str,
    actionable: bool,
    quality_score: int,
    reasons: list[str],
) -> DecisionResultV2:

    return DecisionResultV2(
        strategy_version=STRATEGY_VERSION,
        action=action,
        actionable=actionable,
        quality_score=quality_score,
        quality=_quality_label(quality_score),
        reasons=reasons,
    )


def _quality_label(score: int) -> str:

    if score >= 85:
        return "EXCELLENT"

    if score >= 70:
        return "GOOD"

    if score >= 50:
        return "WATCH"

    return "WEAK"


def _atr_distance(
    *,
    current_price: float,
    level_price: float | None,
    atr_14: float | None,
) -> float | None:

    if (
        level_price is None
        or atr_14 is None
        or atr_14 <= 0
    ):
        return None

    return abs(
        current_price - level_price
    ) / atr_14