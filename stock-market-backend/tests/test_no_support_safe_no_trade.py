from app.services.setup_service import SetupService
from app.services.risk_service import RiskService


def _intraday_no_support():
    return {
        "current_price": 338.24,
        "support": {"nearest": None, "next": None, "strongest": None},
        "resistance": {"nearest": 341.6875, "next": 342.735, "strongest": 341.6875},
        "indicators": {"atr_14": 1.4317},
    }


def _breakout_waiting():
    return {
        "confirmed": False,
        "status": "WAITING_FOR_PRICE",
        "timestamp": None,
        "breakout_detected": False,
        "confirmation_price": 341.8,
        "breakout_level": 341.6875,
        "follow_through_close": None,
    }


def test_setup_no_support_is_safe_no_trade_not_analysis_failure(monkeypatch):
    monkeypatch.setattr(
        "app.services.setup_service.AnalysisService.get_summary",
        lambda **kwargs: _intraday_no_support(),
    )
    monkeypatch.setattr(
        "app.services.setup_service.MultiTimeframeService.get_analysis",
        lambda **kwargs: {"overall_score": 45, "overall_classification": "WATCH"},
    )
    monkeypatch.setattr(
        "app.services.setup_service.BreakoutService.get_confirmation",
        lambda **kwargs: _breakout_waiting(),
    )
    monkeypatch.setattr(
        "app.services.setup_service.calculate_long_risk_reward",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("strict risk calculator must not run without support")),
    )
    monkeypatch.setattr(
        "app.services.setup_service.SignalLifecycleService.advance",
        lambda **kwargs: {
            "state": "WATCHING", "previous_state": None, "last_event": "SETUP_WATCHING",
            "state_changed": False, "cycle_number": 1, "signal_candle_time": None,
        },
    )
    monkeypatch.setattr(
        "app.services.setup_service.PositionLifecycleService.advance_from_setup",
        lambda **kwargs: {"state": "NOT_OPEN", "opening_gate_passed": False, "database_mutated": False},
    )

    result = SetupService.get_setup(db=None, symbol="GOOGL")

    assert result["action"] == "NO_TRADE"
    assert result["actionable"] is False
    assert result["risk_reward"]["available"] is False
    assert result["risk_reward"]["quality"] == "UNAVAILABLE"
    assert result["risk_reward"]["stop_loss"] is None
    assert result["decision_reasons"] == ["No qualifying support level available for risk calculation"]
    assert result["position_lifecycle"]["state"] == "NOT_OPEN"


def test_position_size_fails_closed_when_structural_risk_unavailable(monkeypatch):
    monkeypatch.setattr(
        "app.services.risk_service.SetupService.get_setup",
        lambda **kwargs: {
            "action": "NO_TRADE",
            "actionable": False,
            "decision_reasons": ["No qualifying support level available for risk calculation"],
            "multi_timeframe": {"overall_score": 45, "overall_classification": "WATCH"},
            "risk_reward": {
                "available": False,
                "reason": "No qualifying support level available for risk calculation",
                "quality": "UNAVAILABLE",
                "entry": 338.24,
                "stop_loss": None,
            },
        },
    )
    monkeypatch.setattr(
        "app.services.risk_service.calculate_position_size",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("position sizing must not run without a stop")),
    )

    result = RiskService.get_position_size(
        db=None, symbol="GOOGL", account_size=10000, risk_percent=2,
    )

    assert result["position"]["allowed"] is False
    assert result["position"]["shares"] == 0
    assert result["position"]["stop_loss"] is None
    assert result["position"]["reason"] == "No qualifying support level available for risk calculation"
