import pytest

from app.risk.trailing_stop import compute_trailing_stop


def run(price, stop, **kw):
    params = dict(
        entry_price=100.0,
        current_price=price,
        current_stop=stop,
        trail_percent=5.0,
        activation_percent=0.0,
        breakeven_percent=5.0,
        min_step_percent=0.25,
    )
    params.update(kw)
    return compute_trailing_stop(**params)


def test_stop_moves_up_proportionally_with_price():
    d = run(110.0, 95.0)
    assert d.should_update and d.new_stop == 104.50   # 110 * 0.95


def test_stop_never_moves_down_on_pullback():
    d = run(108.0, 104.50)                              # 108 * 0.95 = 102.6
    assert not d.should_update and d.new_stop is None


def test_breakeven_lock_once_gain_reaches_threshold():
    d = run(105.0, 95.0)                                # 105 * 0.95 = 99.75
    assert d.should_update and d.new_stop == 100.00     # locked at entry


def test_no_change_before_activation():
    d = run(101.0, 95.0, activation_percent=2.0)
    assert not d.should_update and d.reason.startswith("NOT_ACTIVE")


def test_tiny_moves_are_ignored():
    d = run(110.10, 104.50)                             # 104.59 < 104.50 * 1.0025
    assert not d.should_update


def test_stop_is_always_below_price_and_rounded_down():
    d = run(123.456, None, trail_percent=0.001)
    assert d.new_stop < 123.456
    assert d.new_stop == round(d.new_stop, 2)


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        run(110.0, 95.0, trail_percent=0)
