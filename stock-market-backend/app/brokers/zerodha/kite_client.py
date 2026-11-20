"""Thin wrapper around the official pykiteconnect client.

Everything Zerodha-specific lives here so services stay broker-agnostic.
Only LIMIT orders are exposed on purpose: with real money, a fat-fingered
MARKET order in a thin stock can fill far from the expected price.
"""
from __future__ import annotations

from datetime import datetime
from urllib.parse import quote, urlencode

from kiteconnect import KiteConnect

from app.core.config import settings
from app.trading.zerodha_order_rules import IST

KITE_LOGIN_URL = "https://kite.zerodha.com/connect/login"


def _require_credentials() -> tuple[str, str]:
    if not settings.kite_api_key or not settings.kite_api_secret:
        raise ValueError("KITE_API_KEY / KITE_API_SECRET are not configured")
    return settings.kite_api_key, settings.kite_api_secret


def build_login_url(state: str) -> str:
    """Kite returns `redirect_params` unchanged to the registered redirect URL."""
    api_key, _ = _require_credentials()
    query = urlencode(
        {
            "v": "3",
            "api_key": api_key,
            "redirect_params": f"state={quote(state, safe='')}",
        }
    )
    return f"{KITE_LOGIN_URL}?{query}"


def exchange_request_token(request_token: str) -> dict:
    api_key, api_secret = _require_credentials()
    kite = KiteConnect(api_key=api_key)
    return kite.generate_session(request_token, api_secret=api_secret)


class ZerodhaClient:
    def __init__(self, access_token: str) -> None:
        api_key, _ = _require_credentials()
        self.kite = KiteConnect(api_key=api_key)
        self.kite.set_access_token(access_token)

    def profile(self) -> dict:
        return self.kite.profile()

    def last_price(self, exchange: str, tradingsymbol: str) -> float | None:
        key = f"{exchange}:{tradingsymbol}"
        data = self.kite.ltp([key]).get(key)
        return float(data["last_price"]) if data else None

    def instrument_token(self, exchange: str, tradingsymbol: str) -> int | None:
        """Look up the numeric token Kite needs for historical data (equity only)."""
        for row in self.kite.instruments(exchange):
            if (
                row.get("tradingsymbol") == tradingsymbol
                and row.get("segment") == exchange
                and row.get("instrument_type") == "EQ"
            ):
                return int(row["instrument_token"])
        return None

    def historical(
        self,
        instrument_token: int,
        start: datetime,
        end: datetime,
        interval: str,
    ) -> list[dict]:
        """OHLCV bars; each row's `date` is the IST bar start.

        pykiteconnect formats the range without a timezone and Kite reads it as
        IST, so aware datetimes are converted to naive IST first.
        """
        def as_ist(value: datetime) -> datetime:
            if value.tzinfo is None:
                return value
            return value.astimezone(IST).replace(tzinfo=None)

        return self.kite.historical_data(
            instrument_token,
            as_ist(start),
            as_ist(end),
            interval,
            continuous=False,
            oi=False,
        )

    def instruments(self, exchange: str) -> list[dict]:
        """Full instrument dump for an exchange (large; cache the result)."""
        return self.kite.instruments(exchange)

    def quote(self, keys: list[str]) -> dict:
        """Full quotes (last price, OHLC, volume, OI) for 'EXCHANGE:SYMBOL' keys."""
        return self.kite.quote(keys) if keys else {}

    def order_margins(self, orders: list[dict]) -> list[dict]:
        """Margin Zerodha would block for hypothetical orders (nothing is placed)."""
        return self.kite.order_margins(orders)

    def orders(self) -> list[dict]:
        """Today's orders only (Kite clears the order book daily)."""
        return self.kite.orders()

    def trades(self) -> list[dict]:
        """Today's executed fills only."""
        return self.kite.trades()

    def last_prices(self, keys: list[str]) -> dict[str, float]:
        """keys like 'NSE:ITC' -> last traded price."""
        if not keys:
            return {}
        data = self.kite.ltp(keys)
        return {key: float(value["last_price"]) for key, value in data.items()}

    def sellable_quantity(self, exchange: str, tradingsymbol: str, product: str) -> int:
        """Shares that can be sold without going short, for this product."""
        quantity = 0
        if product == "CNC":
            for holding in self.kite.holdings():
                if holding["tradingsymbol"] == tradingsymbol and holding["exchange"] == exchange:
                    quantity += int(holding.get("quantity") or 0)
                    quantity += int(holding.get("t1_quantity") or 0)
        for position in self.kite.positions().get("net", []):
            if (
                position["tradingsymbol"] == tradingsymbol
                and position["exchange"] == exchange
                and position["product"] == product
            ):
                quantity += max(int(position.get("quantity") or 0), 0)
        return quantity

    def place_limit_order(
        self,
        *,
        exchange: str,
        tradingsymbol: str,
        side: str,
        quantity: int,
        price: float,
        product: str,
        tag: str,
    ) -> str:
        return self.kite.place_order(
            variety=self.kite.VARIETY_REGULAR,
            exchange=exchange,
            tradingsymbol=tradingsymbol,
            transaction_type=side,
            quantity=quantity,
            product=product,
            order_type=self.kite.ORDER_TYPE_LIMIT,
            price=price,
            validity=self.kite.VALIDITY_DAY,
            tag=tag,
        )

    def cancel_order(self, order_id: str) -> str:
        return self.kite.cancel_order(
            variety=self.kite.VARIETY_REGULAR,
            order_id=order_id,
        )

    def invalidate(self) -> None:
        self.kite.invalidate_access_token()
