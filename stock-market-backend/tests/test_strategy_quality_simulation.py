import pytest

from app.services.strategy_quality_simulation_service import StrategyQualitySimulationService


def test_simulation_is_stateless_and_scores_known_20_trade_sample():
    # 12 x +1R, 8 x -1R => 60% wins, avg +0.2R, PF 1.5.
    result = StrategyQualitySimulationService.simulate([1.0] * 12 + [-1.0] * 8)

    assert result["simulation_mode"] == "STATELESS_QUALITY_SCORE_VALIDATION"
    assert result["execution_mode"] == "ANALYSIS_ONLY"
    assert result["persistence_mode"] == "NONE"
    assert result["broker_order_submitted"] is False
    assert result["database_mutated"] is False
    assert result["production_position_tables_mutated"] is False
    assert result["trades_received"] == 20
    assert result["wins"] == 12
    assert result["losses"] == 8
    assert result["breakeven"] == 0
    assert result["win_rate_pct"] == 60.0
    assert result["average_r"] == 0.2
    assert result["profit_factor_r"] == 1.5
    assert result["sample_size_score"] == 26.67
    assert result["expectancy_score"] == 10.8
    assert result["profit_factor_score"] == 12.0
    assert result["win_rate_score"] == 8.33
    assert result["quality_score"] == 57.8
    assert result["quality_grade"] == "C"
    assert result["confidence"] == "LOW"
    assert result["assessment"] == "EVALUATED"
    assert result["validation_status"] == "PASS"


def test_simulation_does_not_grade_small_sample():
    result = StrategyQualitySimulationService.simulate([2.0, 1.0, -1.0, 0.5, -0.5])
    assert result["trades_received"] == 5
    assert result["quality_grade"] == "UNRATED"
    assert result["confidence"] == "VERY_LOW"
    assert result["assessment"] == "INSUFFICIENT_REAL_SAMPLE"


def test_simulation_derives_breakeven_from_zero_r():
    result = StrategyQualitySimulationService.simulate([1.0, 0.0, -1.0])
    assert result["wins"] == 1
    assert result["losses"] == 1
    assert result["breakeven"] == 1


def test_simulation_rejects_empty_input():
    with pytest.raises(ValueError, match="at least one"):
        StrategyQualitySimulationService.simulate([])


def test_simulation_rejects_non_finite_values():
    with pytest.raises(ValueError, match="finite"):
        StrategyQualitySimulationService.simulate([1.0, float("nan")])
