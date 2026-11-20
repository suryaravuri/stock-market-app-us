from datetime import datetime, timezone

from app.strategies.trade_performance import calculate_trade_statistics


def e(symbol, r, pnl, outcome, state="STOP_HIT", reason="TRAILING_STOP", holding=60):
    return {
        "source": "ISOLATED_TEST",
        "position_id": symbol + str(r),
        "test_run_id": "x",
        "symbol": symbol,
        "timeframe": "15Min",
        "state": state,
        "outcome": outcome,
        "entry_price": 100.0,
        "exit_price": 100.0 + pnl,
        "realized_per_share": pnl,
        "realized_r": r,
        "opened_at": datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc),
        "closed_at": datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc),
        "holding_minutes": holding,
        "exit_reason": reason,
        "signal_cycle_number": None,
        "analytics_candle_source": "SYNTHETIC_PERSISTED_CANDLES",
    }


def test_statistics_core_math():
    rows = [
        e("PLTR", 1.25, 2.5, "WIN"),
        e("PLTR", -1.0, -2.0, "LOSS", reason="INITIAL_STOP"),
        e("AMD", 2.0, 4.0, "WIN", state="TARGET_2_HIT", reason="TARGET_2"),
        e("AMD", 0.0, 0.0, "BREAKEVEN", reason="BREAKEVEN_STOP"),
    ]
    s = calculate_trade_statistics(rows)
    assert s["total_trades"] == 4
    assert s["wins"] == 2
    assert s["losses"] == 1
    assert s["breakeven"] == 1
    assert s["win_rate_pct"] == 50.0
    assert s["average_r"] == 0.5625
    assert s["median_r"] == 0.625
    assert s["expectancy_r"] == 0.5625
    assert s["gross_profit_per_share"] == 6.5
    assert s["gross_loss_per_share"] == -2.0
    assert s["net_realized_per_share"] == 4.5
    assert s["profit_factor"] == 3.25
    assert s["best_trade"]["symbol"] == "AMD"
    assert s["worst_trade"]["realized_r"] == -1.0
    assert len(s["by_symbol"]) == 2


def test_empty_statistics_are_safe():
    s = calculate_trade_statistics([])
    assert s["total_trades"] == 0
    assert s["win_rate_pct"] == 0.0
    assert s["average_r"] is None
    assert s["profit_factor"] is None
    assert s["best_trade"] is None
    assert s["summary"].startswith("0 completed")

