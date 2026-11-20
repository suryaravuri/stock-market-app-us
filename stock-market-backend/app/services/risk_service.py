from sqlalchemy.orm import Session

from app.core.config import settings
from app.risk import calculate_position_size
from app.services.setup_service import SetupService


class RiskService:

    @staticmethod
    def get_position_size(
        db: Session,
        symbol: str,
        account_size: float,
        risk_percent: float,
        setup: dict | None = None,
    ) -> dict:

        symbol = symbol.strip().upper()

        # Re-use a setup the caller already evaluated (e.g. the watchlist
        # scan). Re-running SetupService here would evaluate a second time
        # outside the completed-candle guard and advance lifecycle state again.
        if setup is None:
            setup = SetupService.get_setup(
                db=db,
                symbol=symbol,
            )

        risk_reward = setup["risk_reward"]

        # Missing structural support is a valid non-actionable setup.  Do not
        # force fabricated stop-loss values into the position-size calculator.
        if not risk_reward.get("available", True) or risk_reward.get("stop_loss") is None:
            max_risk_amount = account_size * risk_percent / 100
            max_position_value = account_size * settings.max_position_percent / 100
            return {
                "symbol": symbol,
                "setup": {
                    "actionable": False,
                    "action": setup["action"],
                    "decision_reasons": setup["decision_reasons"],
                    "overall_score": setup["multi_timeframe"]["overall_score"],
                    "overall_classification": setup["multi_timeframe"]["overall_classification"],
                    "risk_reward_quality": risk_reward.get("quality", "UNAVAILABLE"),
                },
                "position": {
                    "allowed": False,
                    "shares": 0,
                    "account_size": round(account_size, 2),
                    "risk_percent": round(risk_percent, 2),
                    "max_risk_amount": round(max_risk_amount, 2),
                    "max_position_percent": round(settings.max_position_percent, 2),
                    "max_position_value": round(max_position_value, 2),
                    "entry_price": risk_reward.get("entry"),
                    "stop_loss": None,
                    "risk_per_share": None,
                    "position_value": 0.0,
                    "actual_risk_amount": 0.0,
                    "reason": risk_reward.get("reason") or "Risk parameters are unavailable",
                },
                "option_analysis": setup.get("option_analysis"),
            }

        result = calculate_position_size(
            account_size=account_size,
            risk_percent=risk_percent,
            entry_price=risk_reward["entry"],
            stop_loss=risk_reward["stop_loss"],
            actionable=setup["actionable"],
            max_position_percent=settings.max_position_percent,
        )

        return {
            "symbol": symbol,

            "setup": {
                "actionable": setup["actionable"],
                "action": setup["action"],
                "decision_reasons": setup["decision_reasons"],
                "overall_score":
                    setup["multi_timeframe"]["overall_score"],
                "overall_classification":
                    setup["multi_timeframe"][
                        "overall_classification"
                    ],
                "risk_reward_quality":
                    risk_reward["quality"],
            },

            "position": {
                "allowed": result.allowed,
                "shares": result.shares,

                "account_size": result.account_size,
                "risk_percent": result.risk_percent,
                "max_risk_amount": result.max_risk_amount,
                "max_position_percent":
                    result.max_position_percent,
                "max_position_value":
                    result.max_position_value,

                "entry_price": result.entry_price,
                "stop_loss": result.stop_loss,
                "risk_per_share": result.risk_per_share,

                "position_value": result.position_value,
                "actual_risk_amount":
                    result.actual_risk_amount,

                "reason": result.reason,

                "target_1": risk_reward.get("target_1"),
                "target_2": risk_reward.get("target_2"),
            },

            "option_analysis": setup.get("option_analysis"),
        }