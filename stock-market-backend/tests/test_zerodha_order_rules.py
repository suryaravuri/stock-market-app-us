from datetime import datetime, timezone

from app.trading.zerodha_order_rules import (
    IST,
    is_regular_session,
    kite_token_expiry,
    validate_order,
)

# Monday 2 Nov 2026, 11:00 IST
OPEN_TIME = datetime(2026, 11, 2, 11, 0, tzinfo=IST)


def _validate(**overrides):
    params = dict(
        exchange="NSE",
        side="BUY",
        product="CNC",
        quantity=5,
        limit_price=1500.0,
        last_price=1500.0,
        now=OPEN_TIME,
        max_order_value=10000.0,
        max_price_deviation_percent=3.0,
        orders_placed_today=0,
        max_orders_per_day=10,
        has_open_order_same_side=False,
        sellable_quantity=0,
    )
    params.update(overrides)
    return validate_order(**params)


def test_valid_buy_passes():
    result = _validate()
    assert result.allowed, result.reasons


def test_session_hours():
    assert is_regular_session(datetime(2026, 11, 2, 9, 15, tzinfo=IST))
    assert not is_regular_session(datetime(2026, 11, 2, 9, 14, tzinfo=IST))
    assert not is_regular_session(datetime(2026, 11, 2, 15, 30, tzinfo=IST))
    assert not is_regular_session(datetime(2026, 10, 31, 11, 0, tzinfo=IST))  # Saturday
    # 05:30 UTC == 11:00 IST
    assert is_regular_session(datetime(2026, 11, 2, 5, 30, tzinfo=timezone.utc))


def test_rejects_outside_session():
    result = _validate(now=datetime(2026, 11, 2, 16, 0, tzinfo=IST))
    assert not result.allowed


def test_rejects_order_value_over_limit():
    result = _validate(quantity=7)  # 7 * 1500 = 10500
    assert not result.allowed
    assert any("per-order limit" in r for r in result.reasons)


def test_rejects_fat_finger_price():
    result = _validate(limit_price=1600.0)  # ~6.7% above LTP
    assert not result.allowed


def test_rejects_missing_last_price():
    assert not _validate(last_price=None).allowed


def test_daily_limit():
    assert not _validate(orders_placed_today=10).allowed


def test_duplicate_open_order():
    assert not _validate(has_open_order_same_side=True).allowed


def test_sell_cannot_go_short():
    assert not _validate(side="SELL", quantity=5, sellable_quantity=3).allowed
    assert _validate(side="SELL", quantity=3, sellable_quantity=3).allowed


def test_token_expiry_is_next_6am_ist():
    morning = kite_token_expiry(datetime(2026, 11, 2, 8, 30, tzinfo=IST))
    assert morning == datetime(2026, 11, 3, 6, 0, tzinfo=IST)
    early = kite_token_expiry(datetime(2026, 11, 2, 5, 0, tzinfo=IST))
    assert early == datetime(2026, 11, 2, 6, 0, tzinfo=IST)
