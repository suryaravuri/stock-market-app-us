from dataclasses import dataclass
import math


@dataclass
class PositionSizeResult:
    allowed: bool
    shares: int
    account_size: float
    risk_percent: float
    max_risk_amount: float
    max_position_percent: float
    max_position_value: float
    entry_price: float
    stop_loss: float
    risk_per_share: float
    position_value: float
    actual_risk_amount: float
    reason: str | None


def calculate_position_size(
    account_size: float,
    risk_percent: float,
    entry_price: float,
    stop_loss: float,
    actionable: bool = True,
    max_position_percent: float = 20.0,
) -> PositionSizeResult:

    # ---------------------------------
    # 1. Validation
    # ---------------------------------

    if account_size <= 0:
        raise ValueError(
            "Account size must be greater than zero"
        )

    if risk_percent <= 0 or risk_percent > 100:
        raise ValueError(
            "Risk percent must be between 0 and 100"
        )

    if max_position_percent <= 0 or max_position_percent > 100:
        raise ValueError(
            "Max position percent must be between 0 and 100"
        )

    if entry_price <= 0:
        raise ValueError(
            "Entry price must be greater than zero"
        )

    if stop_loss <= 0:
        raise ValueError(
            "Stop loss must be greater than zero"
        )

    if stop_loss >= entry_price:
        raise ValueError(
            "Stop loss must be below entry price "
            "for a long position"
        )

    # ---------------------------------
    # 2. Risk calculations
    # ---------------------------------

    max_risk_amount = (
        account_size
        * risk_percent
        / 100
    )

    risk_per_share = (
        entry_price
        - stop_loss
    )

    # Shares allowed by risk budget
    risk_based_shares = math.floor(
        max_risk_amount
        / risk_per_share
    )

    # Shares affordable with total account capital
    capital_based_shares = math.floor(
        account_size
        / entry_price
    )

    # Independent concentration cap. This prevents a tight stop
    # from allowing nearly the entire account into one stock.
    max_position_value = (
        account_size
        * max_position_percent
        / 100
    )

    concentration_based_shares = math.floor(
        max_position_value
        / entry_price
    )

    shares = min(
        risk_based_shares,
        capital_based_shares,
        concentration_based_shares,
    )

    # ---------------------------------
    # 3. Setup filter
    # ---------------------------------

    if not actionable:
        return PositionSizeResult(
            allowed=False,
            shares=0,
            account_size=round(account_size, 2),
            risk_percent=round(risk_percent, 2),
            max_risk_amount=round(
                max_risk_amount,
                2,
            ),
            max_position_percent=round(
                max_position_percent,
                2,
            ),
            max_position_value=round(
                max_position_value,
                2,
            ),
            entry_price=round(entry_price, 4),
            stop_loss=round(stop_loss, 4),
            risk_per_share=round(
                risk_per_share,
                4,
            ),
            position_value=0.0,
            actual_risk_amount=0.0,
            reason="Setup is not actionable",
        )

    # ---------------------------------
    # 4. Ensure at least one share
    # ---------------------------------

    if shares < 1:
        return PositionSizeResult(
            allowed=False,
            shares=0,
            account_size=round(account_size, 2),
            risk_percent=round(risk_percent, 2),
            max_risk_amount=round(
                max_risk_amount,
                2,
            ),
            max_position_percent=round(
                max_position_percent,
                2,
            ),
            max_position_value=round(
                max_position_value,
                2,
            ),
            entry_price=round(entry_price, 4),
            stop_loss=round(stop_loss, 4),
            risk_per_share=round(
                risk_per_share,
                4,
            ),
            position_value=0.0,
            actual_risk_amount=0.0,
            reason=(
                "Account size or risk budget "
                "is insufficient for one share"
            ),
        )

    # ---------------------------------
    # 5. Final position
    # ---------------------------------

    position_value = (
        shares * entry_price
    )

    actual_risk_amount = (
        shares * risk_per_share
    )

    return PositionSizeResult(
        allowed=True,
        shares=shares,
        account_size=round(account_size, 2),
        risk_percent=round(risk_percent, 2),
        max_risk_amount=round(
            max_risk_amount,
            2,
        ),
        max_position_percent=round(
            max_position_percent,
            2,
        ),
        max_position_value=round(
            max_position_value,
            2,
        ),
        entry_price=round(entry_price, 4),
        stop_loss=round(stop_loss, 4),
        risk_per_share=round(
            risk_per_share,
            4,
        ),
        position_value=round(
            position_value,
            2,
        ),
        actual_risk_amount=round(
            actual_risk_amount,
            2,
        ),
        reason=None,
    )