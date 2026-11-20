"""Pure validation rules for real-money Zerodha orders.

No database, broker or framework imports here, so every rule can be unit
tested in isolation. The order service calls these before anything is sent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

NSE_OPEN = time(9, 15)
NSE_CLOSE = time(15, 30)

ALLOWED_EXCHANGES = {"NSE", "BSE"}
ALLOWED_SIDES = {"BUY", "SELL"}
ALLOWED_PRODUCTS = {"CNC", "MIS"}

# Kite order statuses that still represent a working order.
OPEN_ORDER_STATUSES = {
    "OPEN",
    "OPEN PENDING",
    "TRIGGER PENDING",
    "VALIDATION PENDING",
    "PUT ORDER REQ RECEIVED",
    "MODIFY PENDING",
    "MODIFY VALIDATION PENDING",
    "AMO REQ RECEIVED",
}


@dataclass
class RuleResult:
    allowed: bool
    reasons: list[str] = field(default_factory=list)

    def reject(self, reason: str) -> None:
        self.allowed = False
        if reason not in self.reasons:
            self.reasons.append(reason)


def to_ist(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(IST)


def is_regular_session(now: datetime) -> bool:
    """Mon-Fri 09:15-15:30 IST. Exchange holidays are rejected by Zerodha."""
    local = to_ist(now)
    if local.weekday() >= 5:
        return False
    return NSE_OPEN <= local.time() < NSE_CLOSE


def ist_day_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Start/end of the current IST calendar day, as aware datetimes."""
    local = to_ist(now)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def kite_token_expiry(login_time: datetime) -> datetime:
    """Kite access tokens expire at 06:00 IST on the next morning."""
    local = to_ist(login_time)
    expiry = local.replace(hour=6, minute=0, second=0, microsecond=0)
    if local >= expiry:
        expiry += timedelta(days=1)
    return expiry


def validate_order(
    *,
    exchange: str,
    side: str,
    product: str,
    quantity: int,
    limit_price: float,
    last_price: float | None,
    now: datetime,
    max_order_value: float,
    max_price_deviation_percent: float,
    orders_placed_today: int,
    max_orders_per_day: int,
    has_open_order_same_side: bool,
    sellable_quantity: int,
) -> RuleResult:
    result = RuleResult(allowed=True)

    if exchange not in ALLOWED_EXCHANGES:
        result.reject(f"Exchange must be one of {sorted(ALLOWED_EXCHANGES)}")
    if side not in ALLOWED_SIDES:
        result.reject("Side must be BUY or SELL")
    if product not in ALLOWED_PRODUCTS:
        result.reject(f"Product must be one of {sorted(ALLOWED_PRODUCTS)}")
    if quantity <= 0:
        result.reject("Quantity must be greater than zero")
    if limit_price <= 0:
        result.reject("Limit price must be greater than zero")

    if not is_regular_session(now):
        result.reject("NSE/BSE regular session is closed (Mon-Fri 09:15-15:30 IST)")

    if last_price is None or last_price <= 0:
        result.reject("Last traded price is unavailable; refusing to price the order")
    elif limit_price > 0:
        deviation = abs(limit_price - last_price) / last_price * 100
        if deviation > max_price_deviation_percent:
            result.reject(
                f"Limit price {limit_price:.2f} is {deviation:.2f}% from last price "
                f"{last_price:.2f} (max {max_price_deviation_percent:.2f}%)"
            )

    if quantity > 0 and limit_price > 0:
        order_value = quantity * limit_price
        if order_value > max_order_value:
            result.reject(
                f"Order value {order_value:.2f} INR exceeds the per-order limit "
                f"of {max_order_value:.2f} INR"
            )

    if orders_placed_today >= max_orders_per_day:
        result.reject(f"Daily order limit reached ({max_orders_per_day})")

    if has_open_order_same_side:
        result.reject("An open order already exists for this symbol and side")

    # Never let a SELL open a short position.
    if side == "SELL" and quantity > sellable_quantity:
        result.reject(
            f"SELL quantity {quantity} exceeds sellable quantity {sellable_quantity}"
        )

    return result
