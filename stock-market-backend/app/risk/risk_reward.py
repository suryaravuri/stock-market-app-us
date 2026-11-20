from dataclasses import dataclass


@dataclass
class RiskRewardResult:
    entry: float
    stop_loss: float
    target_1: float | None
    target_2: float | None
    risk_per_share: float
    reward_1_per_share: float | None
    reward_2_per_share: float | None
    rr_1: float | None
    rr_2: float | None
    quality: str
    recalculated_after_breakout: bool = False
    calculation_basis: str = "PRE_BREAKOUT_STRUCTURE"
    target_source: str = "STRUCTURAL_RESISTANCE"


def calculate_long_risk_reward(
    current_price: float,
    nearest_support: float | None,
    nearest_resistance: float | None,
    next_resistance: float | None,
    atr_14: float | None,
    stop_atr_buffer: float = 0.25,
    min_stop_atr: float = 0.0,
    atr_target_fallback: bool = False,
    target_1_atr: float = 2.0,
    target_2_atr: float = 3.0,
) -> RiskRewardResult:
    """Pre-breakout long risk/reward.

    Legacy behaviour (defaults): stop just below the nearest support, targets
    = nearest and next structural resistance.

    ATR_FLOOR model (min_stop_atr > 0, atr_target_fallback=True):
      * the stop is at least `min_stop_atr` x ATR below entry, so normal
        intraday noise doesn't stop the trade out;
      * when there is no resistance above (new highs), targets are projected
        at `target_1_atr` / `target_2_atr` x ATR instead of "no target";
      * a structural resistance that exists is still used, so buying right
        under resistance still scores POOR (wait for the breakout).
    """
    entry = current_price

    if nearest_support is None or atr_14 is None or atr_14 <= 0:
        raise ValueError(
            "Support and ATR are required for risk calculation"
        )

    stop_loss = (
        nearest_support
        - (atr_14 * stop_atr_buffer)
    )
    calculation_basis = "PRE_BREAKOUT_STRUCTURE"
    if min_stop_atr > 0 and entry - stop_loss < atr_14 * min_stop_atr:
        stop_loss = entry - atr_14 * min_stop_atr
        calculation_basis = "PRE_BREAKOUT_ATR_FLOOR"

    risk_per_share = entry - stop_loss

    if risk_per_share <= 0:
        raise ValueError(
            "Calculated stop loss must be below entry"
        )

    # Legacy: structural levels exactly as given.
    target_1 = nearest_resistance
    target_2 = next_resistance
    target_source = "STRUCTURAL_RESISTANCE"
    if atr_target_fallback:
        above = sorted(
            level for level in (nearest_resistance, next_resistance)
            if level is not None and level > entry
        )
        if not above:
            target_1 = entry + atr_14 * target_1_atr
            target_2 = entry + atr_14 * target_2_atr
            target_source = "ATR_PROJECTION"
        elif len(above) == 1:
            target_1 = above[0]
            target_2 = max(target_1 + atr_14, entry + atr_14 * target_2_atr)
            target_source = "STRUCTURAL_THEN_ATR"
        else:
            target_1, target_2 = above[0], above[1]

    reward_1 = (
        target_1 - entry
        if target_1 is not None
        else None
    )

    reward_2 = (
        target_2 - entry
        if target_2 is not None
        else None
    )

    rr_1 = (
        reward_1 / risk_per_share
        if reward_1 is not None and reward_1 > 0
        else None
    )

    rr_2 = (
        reward_2 / risk_per_share
        if reward_2 is not None and reward_2 > 0
        else None
    )

    best_rr = max(
        [
            value
            for value in [rr_1, rr_2]
            if value is not None
        ],
        default=0.0,
    )

    if best_rr >= 2.0:
        quality = "GOOD"
    elif best_rr >= 1.5:
        quality = "ACCEPTABLE"
    else:
        quality = "POOR"

    return RiskRewardResult(
        entry=round(entry, 4),
        stop_loss=round(stop_loss, 4),
        target_1=round(target_1, 4) if target_1 else None,
        target_2=round(target_2, 4) if target_2 else None,
        risk_per_share=round(risk_per_share, 4),
        reward_1_per_share=(
            round(reward_1, 4)
            if reward_1 is not None
            else None
        ),
        reward_2_per_share=(
            round(reward_2, 4)
            if reward_2 is not None
            else None
        ),
        rr_1=round(rr_1, 2) if rr_1 is not None else None,
        rr_2=round(rr_2, 2) if rr_2 is not None else None,
        quality=quality,
        calculation_basis=calculation_basis,
        target_source=target_source,
    )

def calculate_confirmed_breakout_risk_reward(
    *,
    confirmed_entry_price: float,
    breakout_level: float,
    follow_through_low: float,
    atr_14: float,
    structural_resistances: list[float] | None = None,
    stop_atr_buffer: float = 0.10,
    fallback_target_1_r: float = 2.0,
    fallback_target_2_r: float = 3.0,
) -> RiskRewardResult:
    """Recalculate long risk only after the breakout entry gate is confirmed.

    Entry is the completed follow-through/retest candle close.  The stop sits
    below the lower of old resistance and the follow-through low, with a small
    ATR buffer.  Targets prefer post-entry structural resistance.  When none is
    available, explicit 2R/3R planning targets are used as a risk-management
    fallback; these are not price forecasts.
    """
    if atr_14 is None or atr_14 <= 0:
        raise ValueError("ATR is required for confirmed-breakout risk calculation")
    if confirmed_entry_price <= 0 or breakout_level <= 0 or follow_through_low <= 0:
        raise ValueError("Confirmed entry, breakout level, and follow-through low must be positive")

    entry = float(confirmed_entry_price)
    stop_anchor = min(float(breakout_level), float(follow_through_low))
    stop_loss = stop_anchor - (float(atr_14) * stop_atr_buffer)
    risk_per_share = entry - stop_loss
    if risk_per_share <= 0:
        raise ValueError("Calculated confirmed-breakout stop loss must be below entry")

    structural = sorted({
        float(level) for level in (structural_resistances or [])
        if level is not None and float(level) > entry
    })

    target_1 = structural[0] if structural else entry + (risk_per_share * fallback_target_1_r)
    target_2 = structural[1] if len(structural) > 1 else entry + (risk_per_share * fallback_target_2_r)
    target_source = "STRUCTURAL_RESISTANCE" if structural else "R_MULTIPLE_FALLBACK"
    if len(structural) == 1:
        target_source = "STRUCTURAL_THEN_R_MULTIPLE"

    reward_1 = target_1 - entry if target_1 > entry else None
    reward_2 = target_2 - entry if target_2 > entry else None
    rr_1 = reward_1 / risk_per_share if reward_1 is not None else None
    rr_2 = reward_2 / risk_per_share if reward_2 is not None else None
    best_rr = max([v for v in (rr_1, rr_2) if v is not None], default=0.0)

    if best_rr >= 2.0:
        quality = "GOOD"
    elif best_rr >= 1.5:
        quality = "ACCEPTABLE"
    else:
        quality = "POOR"

    return RiskRewardResult(
        entry=round(entry, 4),
        stop_loss=round(stop_loss, 4),
        target_1=round(target_1, 4),
        target_2=round(target_2, 4),
        risk_per_share=round(risk_per_share, 4),
        reward_1_per_share=round(reward_1, 4) if reward_1 is not None else None,
        reward_2_per_share=round(reward_2, 4) if reward_2 is not None else None,
        rr_1=round(rr_1, 2) if rr_1 is not None else None,
        rr_2=round(rr_2, 2) if rr_2 is not None else None,
        quality=quality,
        recalculated_after_breakout=True,
        calculation_basis="CONFIRMED_FOLLOW_THROUGH",
        target_source=target_source,
    )
