from datetime import datetime
from zoneinfo import ZoneInfo

from app.trading.pnl import Fill, apply_last_prices, compute_fifo, summarize

IST = ZoneInfo("Asia/Kolkata")


def _fill(side, qty, price, day, hour=10, symbol="ITC"):
    return Fill("NSE", symbol, "CNC", side, qty, price, datetime(2026, 11, day, hour, 0, tzinfo=IST))


def test_simple_round_trip():
    result = compute_fifo([_fill("BUY", 10, 100.0, 2), _fill("SELL", 10, 110.0, 3)])
    assert len(result.closed) == 1
    assert result.closed[0].pnl == 100.0
    assert result.closed[0].return_percent == 10.0
    assert result.open_positions == []


def test_fifo_uses_oldest_lots_first():
    fills = [
        _fill("BUY", 5, 100.0, 2),
        _fill("BUY", 5, 120.0, 3),
        _fill("SELL", 7, 130.0, 4),
    ]
    result = compute_fifo(fills)
    trade = result.closed[0]
    # 5 @100 + 2 @120 = 740 cost for 7 shares
    assert trade.quantity == 7
    assert round(trade.buy_price, 4) == round(740 / 7, 4)
    assert trade.pnl == round(7 * 130 - 740, 2)
    assert result.open_positions[0].quantity == 3
    assert result.open_positions[0].average_price == 120.0


def test_unmatched_sell_is_excluded_from_pnl():
    result = compute_fifo([_fill("SELL", 4, 50.0, 2)])
    assert result.closed == []
    assert result.unmatched_sells[0].quantity == 4
    assert summarize(result)["realized_pnl"] == 0.0


def test_order_of_input_does_not_matter():
    fills = [_fill("SELL", 10, 90.0, 3), _fill("BUY", 10, 100.0, 2)]
    result = compute_fifo(fills)
    assert result.closed[0].pnl == -100.0


def test_summary_and_unrealized():
    fills = [
        _fill("BUY", 10, 100.0, 2), _fill("SELL", 10, 110.0, 2, 14),
        _fill("BUY", 10, 200.0, 3, symbol="TCS"), _fill("SELL", 10, 190.0, 4, symbol="TCS"),
        _fill("BUY", 2, 50.0, 4, symbol="SBIN"),
    ]
    result = compute_fifo(fills)
    apply_last_prices(result.open_positions, {"NSE:SBIN": 55.0})
    summary = summarize(result)
    assert summary["realized_pnl"] == 0.0  # +100 and -100
    assert summary["wins"] == 1 and summary["losses"] == 1
    assert summary["win_rate_percent"] == 50.0
    assert summary["unrealized_pnl"] == 10.0
    assert summary["unrealized_complete"] is True
    assert [d["date"] for d in summary["daily_pnl"]] == ["2026-11-02", "2026-11-04"]
