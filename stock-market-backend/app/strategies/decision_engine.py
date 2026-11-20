from dataclasses import dataclass


@dataclass
class DecisionResult:
    action: str
    actionable: bool
    reasons: list[str]


def decide_long_setup(
    *,
    overall_score: int,
    overall_classification: str,
    risk_reward_quality: str,
    current_price: float,
    nearest_support: float | None,
    nearest_resistance: float | None,
    atr_14: float | None,
    breakout_confirmed: bool = False,
    breakout_status: str | None = None,
    breakout_confirmation_price: float | None = None,
) -> DecisionResult:
    """Convert analysis + risk/reward into an operational long-side action.

    Improvement #6 makes breakout confirmation the final entry gate. A good
    analytical setup can be a candidate, but it is not actionable until the
    breakout layer confirms the entry trigger.
    """

    classification = overall_classification.upper()
    rr_quality = risk_reward_quality.upper()

    support_atr_distance = _atr_distance(
        current_price=current_price,
        level_price=nearest_support,
        atr_14=atr_14,
    )

    # 1. Hard rejection: broader trend/momentum is negative.
    if classification == "AVOID" or overall_score <= -30:
        return DecisionResult(
            action="AVOID",
            actionable=False,
            reasons=[
                f"Multi-timeframe score is {overall_score} ({classification})",
            ],
        )

    # 2. No setup until the multi-timeframe score clears the minimum threshold.
    if overall_score < 30:
        return DecisionResult(
            action="NEUTRAL",
            actionable=False,
            reasons=[
                f"Multi-timeframe score {overall_score} is below the setup threshold of 30",
            ],
        )

    # 3. Do not wait for a breakout when the entry itself has poor economics.
    if rr_quality == "POOR":
        return DecisionResult(
            action="WAIT_FOR_PULLBACK",
            actionable=False,
            reasons=[
                "Risk/reward quality is POOR",
                "Wait for a better entry or improved reward/risk before breakout confirmation",
            ],
        )

    # 4. Avoid chasing a setup that is already materially extended from support.
    if support_atr_distance is not None and support_atr_distance > 1.00:
        return DecisionResult(
            action="WAIT_FOR_PULLBACK",
            actionable=False,
            reasons=[
                f"Nearest support is {support_atr_distance:.2f} ATR below price",
                "Price is extended from support; wait for a pullback",
            ],
        )

    # 5. A confirmed breakout is the final entry trigger.
    if breakout_confirmed and rr_quality in {"GOOD", "ACCEPTABLE"}:
        return DecisionResult(
            action="ENTRY_CONFIRMED",
            actionable=True,
            reasons=[
                f"Multi-timeframe score {overall_score} meets the setup threshold",
                f"Risk/reward quality is {rr_quality}",
                "Breakout and follow-through/retest confirmation passed the final entry gate",
            ],
        )

    # 6. The analytical setup is valid, but entry is blocked until confirmation.
    if rr_quality in {"GOOD", "ACCEPTABLE"}:
        reasons = [
            f"Multi-timeframe score {overall_score} meets the setup threshold",
            f"Risk/reward quality is {rr_quality}",
        ]

        if breakout_confirmation_price is not None:
            reasons.append(
                f"Waiting for a completed 15-minute candle to confirm above {breakout_confirmation_price:.4f}"
            )
        else:
            reasons.append("Waiting for breakout confirmation before entry")

        if breakout_status:
            reasons.append(f"Breakout status is {breakout_status}")

        return DecisionResult(
            action="WAIT_FOR_BREAKOUT",
            actionable=False,
            reasons=reasons,
        )

    return DecisionResult(
        action="NEUTRAL",
        actionable=False,
        reasons=["No actionable long setup condition was met"],
    )


def _atr_distance(
    *,
    current_price: float,
    level_price: float | None,
    atr_14: float | None,
) -> float | None:
    if level_price is None or atr_14 is None or atr_14 <= 0:
        return None

    return abs(current_price - level_price) / atr_14
