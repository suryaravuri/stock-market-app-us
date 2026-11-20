from app.strategies.strategy_diagnostics import diagnose_strategy


def trade(r, *, source="PRODUCTION_ANALYTICAL", symbol="PLTR", timeframe="15Min", state=None, exit_reason=None):
    if state is None:
        state = "TARGET_2_HIT" if r > 0 else "STOP_HIT"
    return {
        "source": source,
        "symbol": symbol,
        "timeframe": timeframe,
        "outcome": "WIN" if r > 0 else "LOSS" if r < 0 else "BREAKEVEN",
        "realized_r": r,
        "state": state,
        "exit_reason": exit_reason or ("TARGET_2" if state == "TARGET_2_HIT" else "INITIAL_STOP"),
        "holding_minutes": 60,
    }


def test_no_real_trades_is_not_evaluable_and_tests_are_excluded():
    result = diagnose_strategy([trade(1.25, source="ISOLATED_TEST") for _ in range(5)])
    assert result["diagnostic_status"] == "NOT_EVALUABLE"
    assert result["real_market_trade_count"] == 0
    assert result["isolated_test_trade_count"] == 5
    assert result["weaknesses"][0]["code"] == "NO_REAL_TRADE_EVIDENCE"


def test_small_real_sample_is_flagged():
    result = diagnose_strategy([trade(1), trade(-1)])
    codes = {x["code"] for x in result["weaknesses"]}
    assert "INSUFFICIENT_SAMPLE" in codes


def test_negative_expectancy_is_critical():
    result = diagnose_strategy([trade(-1) for _ in range(6)] + [trade(0.5) for _ in range(4)])
    issue = next(x for x in result["weaknesses"] if x["code"] == "NON_POSITIVE_EXPECTANCY")
    assert issue["severity"] == "CRITICAL"


def test_profit_factor_below_one_is_flagged():
    result = diagnose_strategy([trade(0.5) for _ in range(5)] + [trade(-1) for _ in range(5)])
    codes = {x["code"] for x in result["weaknesses"]}
    assert "PROFIT_FACTOR_BELOW_ONE" in codes


def test_healthy_metrics_create_strengths():
    result = diagnose_strategy([trade(1) for _ in range(20)] + [trade(-0.5) for _ in range(10)])
    assert result["metrics"]["average_r"] == 0.5
    assert result["metrics"]["profit_factor_r"] == 4.0
    assert result["strengths"]


def test_weak_symbol_bucket_is_identified():
    entries = [trade(-1, symbol="AMD") for _ in range(5)] + [trade(1, symbol="PLTR") for _ in range(10)]
    result = diagnose_strategy(entries)
    assert any(x["code"] == "WEAK_SYMBOL_BUCKET" for x in result["weaknesses"])


def test_weak_timeframe_bucket_is_identified():
    entries = [trade(-1, timeframe="1Hour") for _ in range(5)] + [trade(1, timeframe="15Min") for _ in range(10)]
    result = diagnose_strategy(entries)
    assert any(x["code"] == "WEAK_TIMEFRAME_BUCKET" for x in result["weaknesses"])


def test_stop_concentration_is_flagged_when_edge_is_thin():
    entries = [trade(0.2, state="STOP_HIT", exit_reason="TRAILING_STOP") for _ in range(8)] + [trade(-0.2) for _ in range(2)]
    result = diagnose_strategy(entries)
    assert any(x["code"] == "STOP_EXIT_CONCENTRATION" for x in result["weaknesses"])


def test_isolated_tests_cannot_hide_real_weakness():
    entries = [trade(-1) for _ in range(5)] + [trade(5, source="ISOLATED_TEST") for _ in range(100)]
    result = diagnose_strategy(entries)
    assert result["real_market_trade_count"] == 5
    assert result["isolated_test_trade_count"] == 100
    assert result["metrics"]["average_r"] == -1.0


def test_priorities_are_sequential():
    result = diagnose_strategy([trade(-1) for _ in range(6)])
    assert [x["priority"] for x in result["weaknesses"]] == list(range(1, result["weakness_count"] + 1))


def test_priorities_are_severity_first_then_business_order():
    entries = [
        trade(0.5, state="STOP_HIT", exit_reason="TRAILING_STOP") for _ in range(4)
    ] + [
        trade(-1, state="STOP_HIT", exit_reason="INITIAL_STOP") for _ in range(6)
    ]
    result = diagnose_strategy(entries)
    ordered = [(x["severity"], x["code"]) for x in result["weaknesses"]]
    assert ordered == [
        ("CRITICAL", "NON_POSITIVE_EXPECTANCY"),
        ("CRITICAL", "PROFIT_FACTOR_BELOW_ONE"),
        ("HIGH", "INSUFFICIENT_SAMPLE"),
        ("HIGH", "WEAK_SYMBOL_BUCKET"),
        ("HIGH", "WEAK_TIMEFRAME_BUCKET"),
        ("MEDIUM", "LOW_WIN_RATE_THIN_EDGE"),
        ("MEDIUM", "STOP_EXIT_CONCENTRATION"),
    ]
    assert [x["priority"] for x in result["weaknesses"]] == list(range(1, 8))
