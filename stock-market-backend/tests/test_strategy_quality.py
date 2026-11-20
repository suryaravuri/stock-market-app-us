from datetime import datetime, timezone

from app.strategies.strategy_quality import calculate_strategy_quality, calculate_quality_breakdown


def row(source, symbol="PLTR", r=1.0, outcome="WIN"):
    return {
        "source": source,
        "position_id": "1",
        "test_run_id": "t" if source == "ISOLATED_TEST" else None,
        "symbol": symbol,
        "timeframe": "15Min",
        "state": "STOP_HIT",
        "outcome": outcome,
        "entry_price": 100.0,
        "exit_price": 100.0 + r * 2.0,
        "realized_per_share": r * 2.0,
        "realized_r": r,
        "opened_at": datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc),
        "closed_at": datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc),
        "holding_minutes": 60.0,
        "exit_reason": "TRAILING_STOP",
        "signal_cycle_number": None,
        "analytics_candle_source": "SYNTHETIC_PERSISTED_CANDLES" if source == "ISOLATED_TEST" else "MARKET_CANDLE",
    }


def test_only_synthetic_is_not_evaluable():
    q = calculate_strategy_quality([row("ISOLATED_TEST") for _ in range(5)])
    assert q["assessment"] == "NOT_EVALUABLE"
    assert q["real_market_trade_count"] == 0
    assert q["isolated_test_trade_count"] == 5
    assert q["test_trades_excluded_from_score"] == 5
    assert q["quality_grade"] == "UNRATED"
    assert q["confidence"] == "INSUFFICIENT_DATA"


def test_synthetic_wins_do_not_inflate_real_score():
    real = [row("PRODUCTION_ANALYTICAL", r=-1.0, outcome="LOSS") for _ in range(5)]
    tests = [row("ISOLATED_TEST", r=3.0, outcome="WIN") for _ in range(100)]
    q = calculate_strategy_quality(real + tests)
    assert q["real_market_trade_count"] == 5
    assert q["isolated_test_trade_count"] == 100
    assert q["wins"] == 0
    assert q["losses"] == 5
    assert q["average_r"] == -1.0


def test_grade_requires_real_sample():
    q = calculate_strategy_quality([row("PRODUCTION_ANALYTICAL", r=1.25) for _ in range(14)])
    assert q["quality_grade"] == "UNRATED"
    assert q["assessment"] == "INSUFFICIENT_REAL_SAMPLE"


def test_quality_becomes_evaluable_with_real_sample():
    rows = [row("PRODUCTION_ANALYTICAL", r=1.0, outcome="WIN") for _ in range(12)]
    rows += [row("PRODUCTION_ANALYTICAL", r=-1.0, outcome="LOSS") for _ in range(8)]
    q = calculate_strategy_quality(rows)
    assert q["assessment"] == "EVALUATED"
    assert q["real_market_trade_count"] == 20
    assert q["win_rate_pct"] == 60.0
    assert q["average_r"] == 0.2
    assert q["quality_grade"] != "UNRATED"


def test_breakdown_ignores_isolated_test_groups():
    rows = [row("PRODUCTION_ANALYTICAL", symbol="AMD"), row("ISOLATED_TEST", symbol="PLTR")]
    b = calculate_quality_breakdown(rows, "symbol")
    assert len(b) == 1
    assert b[0]["key"] == "AMD"
