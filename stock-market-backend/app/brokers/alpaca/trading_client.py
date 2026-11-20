from alpaca.trading.client import TradingClient
from alpaca.trading.enums import (
    OrderClass,
    OrderSide,
    OrderType,
    QueryOrderStatus,
    TimeInForce,
)
from alpaca.trading.requests import (
    GetOrdersRequest,
    MarketOrderRequest,
    ReplaceOrderRequest,
    StopLossRequest,
    StopOrderRequest,
    TakeProfitRequest,
)

from app.core.config import settings


class AlpacaPaperTradingClient:

    def __init__(self) -> None:

        if not settings.alpaca_api_key:
            raise ValueError(
                "ALPACA_API_KEY is not configured"
            )

        if not settings.alpaca_secret_key:
            raise ValueError(
                "ALPACA_SECRET_KEY is not configured"
            )

        # IMPORTANT:
        # paper=True forces Alpaca paper-trading endpoint.
        self.client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=True,
        )

    def get_account(self):
        return self.client.get_account()

    def get_account_summary(self) -> dict:

        account = self.get_account()

        return {
            "account_id": str(account.id),
            "status": str(account.status),
            "currency": account.currency,
            "cash": float(account.cash),
            "portfolio_value": float(
                account.portfolio_value
            ),
            "buying_power": float(
                account.buying_power
            ),
            "equity": float(
                account.equity
            ),
            "last_equity": float(
                account.last_equity
            ),
            "trading_blocked":
                account.trading_blocked,
            "account_blocked":
                account.account_blocked,
            "pattern_day_trader":
                account.pattern_day_trader,
        }

    def get_open_orders(self):
        request = GetOrdersRequest(
            status=QueryOrderStatus.OPEN,
            # Alpaca's default page is 50; bracket legs count individually.
            limit=500,
        )
        return self.client.get_orders(filter=request)

    def has_open_order(self, symbol: str) -> bool:
        symbol = symbol.strip().upper()

        open_orders = self.get_open_orders()

        return any(
            str(order.symbol).upper() == symbol
            for order in open_orders
        )

    def has_open_position(self, symbol: str) -> bool:
        symbol = symbol.strip().upper()

        positions = self.client.get_all_positions()

        return any(
            str(position.symbol).upper() == symbol
            for position in positions
        )
    def prepare_market_buy(
        self,
        symbol: str,
        quantity: int,
    ) -> MarketOrderRequest:

        if quantity <= 0:
            raise ValueError(
                "Quantity must be greater than zero"
            )

        return MarketOrderRequest(
            symbol=symbol.strip().upper(),
            qty=quantity,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )

    def submit_market_buy(
        self,
        symbol: str,
        quantity: int,
    ):
        """
        PAPER ACCOUNT ONLY.

        Do not call this method unless all application
        safety checks have already passed.
        """

        order_request = self.prepare_market_buy(
            symbol=symbol,
            quantity=quantity,
        )

        return self.client.submit_order(
            order_data=order_request
        )

    def submit_bracket_buy(
        self,
        symbol: str,
        quantity: int,
        stop_loss_price: float,
        take_profit_price: float,
    ):
        """
        PAPER ACCOUNT ONLY.

        Market buy with a broker-held stop-loss and take-profit.
        GTC is required: with DAY the exit legs would expire at the close
        and the position would be left unprotected overnight.
        """
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero")

        if stop_loss_price <= 0 or take_profit_price <= stop_loss_price:
            raise ValueError(
                f"Invalid bracket prices: stop={stop_loss_price}, "
                f"target={take_profit_price}"
            )

        order_request = MarketOrderRequest(
            symbol=symbol.strip().upper(),
            qty=quantity,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.GTC,
            order_class=OrderClass.BRACKET,
            # Alpaca rejects sub-penny prices for stocks >= $1.
            stop_loss=StopLossRequest(
                stop_price=round(stop_loss_price, 2),
            ),
            take_profit=TakeProfitRequest(
                limit_price=round(take_profit_price, 2),
            ),
        )

        return self.client.submit_order(order_data=order_request)

    # ------------------------------------------------------------------
    # Profit protection helpers
    # ------------------------------------------------------------------

    def is_market_open(self) -> bool:
        return bool(self.client.get_clock().is_open)

    def get_open_positions(self):
        return self.client.get_all_positions()

    def get_open_sell_orders(self, symbol: str) -> list:
        symbol = symbol.strip().upper()
        return [
            order
            for order in self.get_open_orders()
            if str(order.symbol).upper() == symbol
            and _enum_value(order.side) == OrderSide.SELL.value
        ]

    def get_open_sell_stop_orders(self, symbol: str) -> list:
        """Open sell stops for a symbol, including a bracket's stop-loss
        leg (Alpaca reports that leg with status 'held')."""
        return [
            order
            for order in self.get_open_sell_orders(symbol)
            if _enum_value(order.type)
            in {OrderType.STOP.value, OrderType.STOP_LIMIT.value}
        ]

    def replace_stop_price(self, order_id, stop_price: float):
        return self.client.replace_order_by_id(
            order_id=order_id,
            order_data=ReplaceOrderRequest(stop_price=round(stop_price, 2)),
        )

    def get_position_quantity(self, symbol: str) -> float:
        """Shares held for a symbol (0 when there is no position)."""
        symbol = symbol.strip().upper()
        for position in self.client.get_all_positions():
            if str(position.symbol).upper() == symbol:
                return float(position.qty)
        return 0.0

    def has_open_buy_order(self, symbol: str) -> bool:
        symbol = symbol.strip().upper()
        return any(
            str(order.symbol).upper() == symbol
            and _enum_value(order.side) == OrderSide.BUY.value
            for order in self.get_open_orders()
        )

    def cancel_open_orders(self, symbol: str) -> int:
        """Cancel every open order for a symbol, including bracket legs
        (they hold the shares, so a close would otherwise be rejected)."""
        symbol = symbol.strip().upper()
        cancelled = 0
        for order in self.get_open_orders():
            if str(order.symbol).upper() == symbol:
                self.client.cancel_order_by_id(order.id)
                cancelled += 1
        return cancelled

    def close_position(self, symbol: str):
        """Market-sell the whole position."""
        return self.client.close_position(symbol.strip().upper())

    def submit_stop_sell(self, symbol: str, quantity: int, stop_price: float):
        """Protective GTC stop for a position that has none."""
        return self.client.submit_order(
            order_data=StopOrderRequest(
                symbol=symbol.strip().upper(),
                qty=quantity,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                stop_price=round(stop_price, 2),
            )
        )


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)
