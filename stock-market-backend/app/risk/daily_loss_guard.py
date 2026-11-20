from dataclasses import dataclass


@dataclass
class DailyLossGuardResult:
    allowed: bool
    daily_loss_limit: float
    current_daily_pnl: float
    remaining_loss_capacity: float
    reason: str | None


def check_daily_loss_guard(
    account_size: float,
    current_daily_pnl: float,
    max_daily_loss_percent: float,
) -> DailyLossGuardResult:

    if account_size <= 0:
        raise ValueError(
            "Account size must be greater than zero"
        )

    if (
        max_daily_loss_percent <= 0
        or max_daily_loss_percent > 100
    ):
        raise ValueError(
            "Max daily loss percent must be between 0 and 100"
        )

    daily_loss_limit = (
        account_size
        * max_daily_loss_percent
        / 100
    )

    # Example:
    # current_daily_pnl = -150
    # daily_loss_limit = 200
    # remaining = 50
    remaining_loss_capacity = (
        daily_loss_limit
        + current_daily_pnl
    )

    if current_daily_pnl <= -daily_loss_limit:
        return DailyLossGuardResult(
            allowed=False,
            daily_loss_limit=round(
                daily_loss_limit,
                2,
            ),
            current_daily_pnl=round(
                current_daily_pnl,
                2,
            ),
            remaining_loss_capacity=0.0,
            reason="Daily loss limit reached",
        )

    return DailyLossGuardResult(
        allowed=True,
        daily_loss_limit=round(
            daily_loss_limit,
            2,
        ),
        current_daily_pnl=round(
            current_daily_pnl,
            2,
        ),
        remaining_loss_capacity=round(
            max(
                0.0,
                remaining_loss_capacity,
            ),
            2,
        ),
        reason=None,
    )