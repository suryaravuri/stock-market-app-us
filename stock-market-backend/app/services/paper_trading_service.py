from __future__ import annotations

from sqlalchemy.orm import Session

from app.brokers.alpaca.trading_client import AlpacaPaperTradingClient
from app.core.config import settings
from app.services.trading_safety_service import TradingSafetyService


class PaperTradingService:

    @staticmethod
    def _exit_prices(position: dict) -> tuple[float, float]:
        """
        Stop = the structural stop the share count was sized on
        (fallback: default stop-loss %).
        Target = setup target_1 (resistance) if above entry
        (fallback: default take-profit %).
        """
        entry = float(position["entry_price"])

        stop = position.get("stop_loss")
        if stop is None or float(stop) >= entry:
            stop = entry * (1 - settings.default_stop_loss_percent / 100)

        target = position.get("target_1")
        if target is None or float(target) <= entry:
            target = entry * (1 + settings.default_take_profit_percent / 100)

        return float(stop), float(target)

    @staticmethod
    def preview_order(
            db: Session,
            symbol: str,
            account_size: float,
            risk_percent: float,
            current_daily_pnl: float,
            max_daily_loss_percent: float,
    ) -> dict:
        symbol = symbol.strip().upper()

        safety = TradingSafetyService.evaluate(
            db=db,
            symbol=symbol,
            account_size=account_size,
            risk_percent=risk_percent,
            current_daily_pnl=current_daily_pnl,
            max_daily_loss_percent=max_daily_loss_percent,
            mode="PAPER",
        )

        position = safety["position"]

        return {
            "symbol": symbol,
            "mode": "PAPER",
            "can_submit": safety["allowed"],
            "shares": position["shares"],
            "entry_price": position["entry_price"],
            "stop_loss": position["stop_loss"],
            "position_value": position["position_value"],
            "max_risk_amount": position["max_risk_amount"],
            "max_position_percent": position["max_position_percent"],
            "max_position_value": position["max_position_value"],
            "actual_risk_amount": position["actual_risk_amount"],
            "safety": {
                "allowed": safety["allowed"],
                "reasons": safety["reasons"],
            },
        }

    @staticmethod
    def submit_order(
            db: Session,
            symbol: str,
            account_size: float,
            risk_percent: float,
            current_daily_pnl: float,
            max_daily_loss_percent: float,
            setup: dict | None = None,
    ) -> dict:
        symbol = symbol.strip().upper()

        # Run the full safety check immediately before submission.
        # When the caller passes the setup it just evaluated, it is re-used
        # instead of re-running the strategy a second time.
        safety = TradingSafetyService.evaluate(
            db=db,
            symbol=symbol,
            account_size=account_size,
            risk_percent=risk_percent,
            current_daily_pnl=current_daily_pnl,
            max_daily_loss_percent=max_daily_loss_percent,
            mode="PAPER",
            setup=setup,
        )

        if not safety["allowed"]:
            return {
                "submitted": False,
                "symbol": symbol,
                "mode": "PAPER",
                "reasons": safety["reasons"],
            }

        position = safety["position"]
        shares = position["shares"]

        if shares <= 0:
            return {
                "submitted": False,
                "symbol": symbol,
                "mode": "PAPER",
                "reasons": [
                    "Calculated position size is zero"
                ],
            }

        client = AlpacaPaperTradingClient()

        # Prevent duplicate paper orders for the same symbol.
        if client.has_open_order(symbol):
            return {
                "submitted": False,
                "symbol": symbol,
                "mode": "PAPER",
                "reasons": [
                    f"Open paper order already exists for {symbol}"
                ],
            }

        # Prevent adding another position while one is already open.
        if client.has_open_position(symbol):
            return {
                "submitted": False,
                "symbol": symbol,
                "mode": "PAPER",
                "reasons": [
                    f"Open paper position already exists for {symbol}"
                ],
            }

        stop_loss_price = take_profit_price = None

        if settings.paper_use_bracket_orders:
            stop_loss_price, take_profit_price = (
                PaperTradingService._exit_prices(position)
            )
            order = client.submit_bracket_buy(
                symbol=symbol,
                quantity=shares,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
            )
        else:
            order = client.submit_market_buy(
                symbol=symbol,
                quantity=shares,
            )

        return {
            "submitted": True,
            "mode": "PAPER",
            "symbol": symbol,
            "shares": shares,
            "order_id": str(order.id),
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            "status": (
                order.status.value
                if hasattr(order.status, "value")
                else str(order.status)
            ),
            "side": (
                order.side.value
                if hasattr(order.side, "value")
                else str(order.side)
            ),
            "order_type": (
                order.type.value
                if hasattr(order.type, "value")
                else str(order.type)
            ),
            "time_in_force": (
                order.time_in_force.value
                if hasattr(order.time_in_force, "value")
                else str(order.time_in_force)
            ),
        }
