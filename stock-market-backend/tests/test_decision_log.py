from datetime import datetime, timezone

import pytest

from app.services import decision_log
from app.services.decision_log import DecisionLog, breakout_summary, primary_blocker

ALL_ON = {
    "TRADING_ENABLED": True,
    "PAPER_TRADING_ENABLED": True,
    "AUTO_TRADING_ENABLED": True,
    "LIVE_TRADING_DISABLED": True,
}


def base(**overrides):
    d = {
        "symbol": "AAPL",
        "evaluated_at": datetime(2026, 11, 16, 15, 1, tzinfo=timezone.utc),
        "data_status": "PASS",
        "eligible": True,
        "switches": dict(ALL_ON),
        "trading_enabled": True,
        "indian_stock": False,
    }
    d.update(overrides)
    return d


@pytest.fixture(autouse=True)
def tmp_logs(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(decision_log, "_json_logger", None)
    DecisionLog._clear_for_tests()
    yield


def test_submitted_has_no_blocker():
    assert primary_blocker(base(order_submitted=True)) is None


def test_data_blocked_first():
    d = base(eligible=False, data_status="FAIL", data_reasons=["STALE_DATA:3_BAR_LAG"],
             trading_enabled=False)
    assert primary_blocker(d) == "DATA_BLOCKED:STALE_DATA:3_BAR_LAG"


def test_switch_off_beats_stock_flag():
    switches = {**ALL_ON, "AUTO_TRADING_ENABLED": False}
    assert primary_blocker(base(switches=switches, trading_enabled=False)) == \
        "SWITCH_OFF:AUTO_TRADING_ENABLED"


def test_indian_stock():
    assert primary_blocker(base(indian_stock=True)) == "INDIAN_STOCK_NOT_AUTO_TRADED"


def test_stock_not_enabled():
    assert primary_blocker(base(trading_enabled=False)) == "TRADING_NOT_ENABLED_FOR_STOCK"


def test_order_rejected_by_broker_step():
    d = base(order_attempted=True, order_reason="Open paper position already exists for AAPL")
    assert primary_blocker(d) == "ORDER_REJECTED:Open paper position already exists for AAPL"


def test_no_signal():
    d = base(order_reason="SIGNAL_NOT_ENTRY_CONFIRMED:WATCHING")
    assert primary_blocker(d) == "NO_ENTRY_SIGNAL"


def test_would_buy_if_enabled_flag_and_log_file(tmp_path):
    record = DecisionLog.record(base(trading_enabled=False, bounce_triggered=True))
    assert record["blocker"] == "TRADING_NOT_ENABLED_FOR_STOCK"
    assert record["would_buy_if_enabled"] is True
    assert record["outcome"] == "NO_ORDER"
    assert (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").strip()


def test_no_signal_is_not_would_buy():
    record = DecisionLog.record(base(trading_enabled=False))
    assert record["would_buy_if_enabled"] is False


def test_recent_filters_and_counts():
    DecisionLog.record(base(symbol="AAPL", order_submitted=True, entry_type="BREAKOUT"))
    DecisionLog.record(base(symbol="MSFT", trading_enabled=False))
    DecisionLog.record(base(symbol="MSFT"))
    assert [r["symbol"] for r in DecisionLog.recent(symbol="msft")] == ["MSFT", "MSFT"]
    assert len(DecisionLog.recent(only_blocked=True)) == 2
    counts = DecisionLog.blocker_counts(DecisionLog.recent())
    assert counts == {"ORDER_SUBMITTED": 1, "TRADING_NOT_ENABLED_FOR_STOCK": 1, "NO_ENTRY_SIGNAL": 1}


def test_recent_falls_back_to_file_after_restart():
    DecisionLog.record(base(symbol="NVDA"))
    DecisionLog._clear_for_tests()  # simulate a restart
    assert DecisionLog.recent()[0]["symbol"] == "NVDA"


def test_breakout_summary_text():
    setup = {
        "action": "WAIT_FOR_PULLBACK",
        "signal_lifecycle": {"state": "ENTRY_CONFIRMED"},
        "breakout_confirmation": {"status": "WAITING_FOR_PRICE"},
        "risk_reward": {"quality": "POOR", "rr_1": 0.02},
    }
    assert breakout_summary(setup) == (
        "WAIT_FOR_PULLBACK (signal=ENTRY_CONFIRMED, breakout=WAITING_FOR_PRICE, rr=POOR 0.02)"
    )
