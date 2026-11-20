from sqlalchemy.orm import Session

from app.core.config import settings
from app.risk import (
    check_daily_loss_guard,
    check_kill_switch,
)
from app.services.risk_service import RiskService


class TradingSafetyService:

    @staticmethod
    def evaluate(
            db: Session,
            symbol: str,
            account_size: float,
            risk_percent: float,
            current_daily_pnl: float,
            max_daily_loss_percent: float,
            mode: str = "PAPER",
            setup: dict | None = None,
    ) -> dict:

        symbol = symbol.strip().upper()
        mode = mode.strip().upper()

        # ---------------------------------
        # 1. Setup + position sizing
        # ---------------------------------

        position_result = RiskService.get_position_size(
            db=db,
            symbol=symbol,
            account_size=account_size,
            risk_percent=risk_percent,
            setup=setup,
        )

        position = position_result["position"]
        setup = position_result["setup"]

        # ---------------------------------
        # 2. Kill switch
        # ---------------------------------

        kill_switch = check_kill_switch(
            trading_enabled=settings.trading_enabled,
            paper_trading_enabled=settings.paper_trading_enabled,
            live_trading_enabled=settings.live_trading_enabled,
            mode=mode,
        )

        # ---------------------------------
        # 3. Daily loss guard
        # ---------------------------------

        daily_loss = check_daily_loss_guard(
            account_size=account_size,
            current_daily_pnl=current_daily_pnl,
            max_daily_loss_percent=max_daily_loss_percent,
        )

        # ---------------------------------
        # 4. Final decision
        # ---------------------------------

        reasons: list[str] = []

        def add_reason(reason: str | None) -> None:
            if reason and reason not in reasons:
                reasons.append(reason)

        if not setup["actionable"]:
            add_reason(
                "Setup is not actionable"
            )

        if not position["allowed"]:
            add_reason(
                position["reason"]
                or "Position sizing rejected"
            )

        if not kill_switch.allowed:
            add_reason(
                kill_switch.reason
                or "Trading is disabled"
            )

        if not daily_loss.allowed:
            add_reason(
                daily_loss.reason
                or "Daily loss guard rejected trading"
            )

        allowed = (
                setup["actionable"]
                and position["allowed"]
                and kill_switch.allowed
                and daily_loss.allowed
        )

        return {
            "symbol": symbol,
            "mode": mode,
            "allowed": allowed,

            "setup": setup,

            "position": position,

            "kill_switch": {
                "allowed": kill_switch.allowed,
                "reason": kill_switch.reason,
            },

            "daily_loss_guard": {
                "allowed": daily_loss.allowed,
                "daily_loss_limit":
                    daily_loss.daily_loss_limit,
                "current_daily_pnl":
                    daily_loss.current_daily_pnl,
                "remaining_loss_capacity":
                    daily_loss.remaining_loss_capacity,
                "reason": daily_loss.reason,
            },

            "reasons": reasons,
        }
