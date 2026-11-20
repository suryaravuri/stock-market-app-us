from datetime import datetime, timedelta, timezone

import pandas as pd

from app.backtest.broker import Bar, SimulatedBroker
from app.backtest.metrics import summarize

T0 = datetime(2025, 3, 3, 14, 30, tzinfo=timezone.utc)


def bar(i, o, h, l, c):
    return Bar(T0 + timedelta(minutes=15 * i), o, h, l, c)


def test_entry_fills_next_open_and_target_hit():
    b = SimulatedBroker("AAPL", 10_000, slippage_bps=0)
    b.queue_entry(T0, shares=10, stop=95, target=110, reference_price=100)
    b.on_bar(bar(1, 100, 101, 99, 100))      # fills at 100
    assert b.position and b.position.entry_price == 100
    b.on_bar(bar(2, 105, 111, 104, 109))     # target 110 touched
    assert b.position is None
    t = b.trades[0]
    assert t.exit_reason == "TARGET" and t.exit_price == 110 and round(t.pnl, 2) == 100


def test_stop_first_when_both_touched_same_bar():
    b = SimulatedBroker("AAPL", 10_000, slippage_bps=0)
    b.queue_entry(T0, 10, 95, 110, 100)
    b.on_bar(bar(1, 100, 100, 100, 100))
    b.on_bar(bar(2, 100, 112, 94, 100))
    assert b.trades[0].exit_reason == "STOP_LOSS" and b.trades[0].exit_price == 95


def test_gap_down_exits_at_open_not_stop():
    b = SimulatedBroker("AAPL", 10_000, slippage_bps=0)
    b.queue_entry(T0, 10, 95, 110, 100)
    b.on_bar(bar(1, 100, 100, 100, 100))
    b.on_bar(bar(2, 90, 91, 88, 89))
    t = b.trades[0]
    assert t.exit_reason == "STOP_GAP" and t.exit_price == 90 and round(t.r_multiple, 2) == -2.0


def test_entry_skipped_when_open_gaps_below_stop():
    b = SimulatedBroker("AAPL", 10_000, slippage_bps=0)
    b.queue_entry(T0, 10, 95, 110, 100)
    b.on_bar(bar(1, 94, 96, 93, 95))
    assert b.position is None and b.skipped_entries == {"GAP_BELOW_STOP_AT_ENTRY": 1}


def test_trailing_stop_raises_and_exits_as_trailing():
    trail = lambda entry, price, stop: round(price * 0.95, 2)  # noqa: E731
    b = SimulatedBroker("AAPL", 10_000, slippage_bps=0, trail_fn=trail)
    b.queue_entry(T0, 10, 95, 200, 100)
    b.on_bar(bar(1, 100, 101, 99, 100))      # entry; close 100 -> stop stays 95
    b.on_bar(bar(2, 110, 120, 109, 120))     # close 120 -> stop 114
    assert b.position.stop == 114
    b.on_bar(bar(3, 118, 118, 113, 113))     # low 113 <= 114
    assert b.trades[0].exit_reason == "TRAILING_STOP" and b.trades[0].exit_price == 114


def test_slippage_and_cash_cap():
    b = SimulatedBroker("AAPL", 1_000, slippage_bps=10)
    b.queue_entry(T0, 50, 95, 110, 100)      # wants 50 shares, can afford 9
    b.on_bar(bar(1, 100, 100, 100, 100))
    assert b.position.shares == 9 and round(b.position.entry_price, 2) == 100.10


def test_summary_metrics():
    b = SimulatedBroker("AAPL", 10_000, slippage_bps=0)
    b.queue_entry(T0, 10, 95, 110, 100)
    b.on_bar(bar(1, 100, 100, 100, 100))
    b.on_bar(bar(2, 100, 111, 99, 110))
    equity = pd.Series([10_000.0, 10_100.0], index=pd.to_datetime(["2025-03-03", "2026-03-03"]))
    s = summarize(b.trades, equity, 10_000, 12.5, 1, 2)
    assert s["trades"] == 1 and s["win_rate_percent"] == 100.0
    assert s["total_return_percent"] == 1.0 and s["exit_reasons"] == {"TARGET": 1}
    assert s["buy_and_hold_return_percent"] == 12.5
