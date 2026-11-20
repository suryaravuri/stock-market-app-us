"""Small, pure calculations for the options and futures screens."""
from __future__ import annotations

from datetime import date

OPTION_MULTIPLIER = 100  # standard US equity option = 100 shares


def option_cost_per_contract(premium: float, multiplier: int = OPTION_MULTIPLIER) -> float:
    """What buying one contract costs (= the maximum loss for a long option)."""
    return round(premium * multiplier, 2)


def option_breakeven(option_type: str, strike: float, premium: float) -> float:
    """Underlying price at expiry where a LONG option neither gains nor loses."""
    kind = option_type.strip().upper()
    if kind == "CALL":
        return round(strike + premium, 4)
    if kind == "PUT":
        return round(strike - premium, 4)
    raise ValueError("option_type must be CALL or PUT")


def pick_nearest_futures(
    instruments: list[dict],
    underlying: str,
    today: date,
    count: int = 2,
) -> list[dict]:
    """Nearest `count` unexpired FUT contracts of an underlying from a Kite
    instruments list (rows have name, instrument_type, expiry...)."""
    name = underlying.strip().upper()
    futures = [
        row for row in instruments
        if str(row.get("instrument_type", "")).upper() == "FUT"
        and str(row.get("name", "")).upper() == name
        and isinstance(row.get("expiry"), date)
        and row["expiry"] >= today
    ]
    futures.sort(key=lambda row: row["expiry"])
    return futures[:count]


def change_percent(last_price: float | None, previous_close: float | None) -> float | None:
    if not last_price or not previous_close:
        return None
    return round((last_price - previous_close) / previous_close * 100, 2)


def basis(future_price: float | None, spot_price: float | None) -> tuple[float | None, float | None]:
    """(points, percent) the future trades above (+) or below (-) spot."""
    if not future_price or not spot_price:
        return None, None
    points = round(future_price - spot_price, 2)
    return points, round(points / spot_price * 100, 3)
