from app.services.strategy_diagnostics_simulation_service import StrategyDiagnosticsSimulationService


def t(r, *, symbol="PLTR", timeframe="15Min", state=None, exit_reason=None, holding_minutes=60):
    return {
        "realized_r": r,
        "symbol": symbol,
        "timeframe": timeframe,
        "state": state,
        "exit_reason": exit_reason,
        "holding_minutes": holding_minutes,
    }


def codes(result):
    return {w["code"] for w in result["weaknesses"]}


def test_simulation_is_stateless_and_analysis_only():
    result = StrategyDiagnosticsSimulationService.simulate([t(1), t(-1)])
    assert result["simulation_mode"] == "STATELESS_DIAGNOSTICS_VALIDATION"
    assert result["execution_mode"] == "ANALYSIS_ONLY"
    assert result["persistence_mode"] == "NONE"
    assert result["database_mutated"] is False
    assert result["broker_order_submitted"] is False
    assert result["production_position_tables_mutated"] is False
    assert result["validation_status"] == "PASS"


def test_negative_expectancy_and_profit_factor_are_detected():
    result = StrategyDiagnosticsSimulationService.simulate(
        [t(0.5) for _ in range(4)] + [t(-1) for _ in range(6)]
    )
    assert "NON_POSITIVE_EXPECTANCY" in codes(result)
    assert "PROFIT_FACTOR_BELOW_ONE" in codes(result)


def test_low_win_rate_is_detected_when_payoff_does_not_compensate():
    result = StrategyDiagnosticsSimulationService.simulate(
        [t(1) for _ in range(3)] + [t(-0.5) for _ in range(7)]
    )
    assert "LOW_WIN_RATE" in codes(result)


def test_stop_exit_concentration_is_detected():
    trades = [t(0.2, state="STOP_HIT", exit_reason="TRAILING_STOP") for _ in range(8)]
    trades += [t(-0.2, state="STOP_HIT", exit_reason="INITIAL_STOP") for _ in range(2)]
    result = StrategyDiagnosticsSimulationService.simulate(trades)
    assert "STOP_EXIT_CONCENTRATION" in codes(result)
    assert result["metrics"]["stop_exit_rate_pct"] == 100.0


def test_weak_symbol_and_timeframe_buckets_are_detected():
    trades = [t(-1, symbol="AMD", timeframe="1Hour") for _ in range(5)]
    trades += [t(1, symbol="PLTR", timeframe="15Min") for _ in range(10)]
    result = StrategyDiagnosticsSimulationService.simulate(trades)
    assert "WEAK_SYMBOL_BUCKET" in codes(result)
    assert "WEAK_TIMEFRAME_BUCKET" in codes(result)


def test_empty_input_is_rejected():
    try:
        StrategyDiagnosticsSimulationService.simulate([])
    except ValueError as exc:
        assert "at least one" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
