from datetime import datetime, timezone

from app.strategies.position_persistence import (
    evaluate_persistent_opening_gate,
    is_completed_candle,
    is_regular_session_candle,
)


def confirmed_signal():
    return {"state": "ENTRY_CONFIRMED", "cycle_number": 2}


def confirmed_breakout():
    return {
        "confirmed": True,
        "status": "ENTRY_CONFIRMED",
        "follow_through_candle_timestamp": datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc),
    }


def recalculated_risk():
    return {
        "entry": 187.0,
        "stop_loss": 185.0,
        "target_1": 191.0,
        "target_2": 193.0,
        "risk_per_share": 2.0,
        "recalculated_after_breakout": True,
    }


def test_persistent_opening_gate_accepts_only_fully_confirmed_recalculated_setup():
    ok, reason = evaluate_persistent_opening_gate(confirmed_signal(), recalculated_risk(), confirmed_breakout())
    assert ok is True
    assert "passed" in reason


def test_persistent_opening_gate_rejects_non_entry_signal():
    signal = confirmed_signal(); signal["state"] = "WATCHING"
    ok, reason = evaluate_persistent_opening_gate(signal, recalculated_risk(), confirmed_breakout())
    assert ok is False
    assert "ENTRY_CONFIRMED" in reason


def test_persistent_opening_gate_rejects_unconfirmed_breakout():
    breakout = confirmed_breakout(); breakout["confirmed"] = False
    ok, reason = evaluate_persistent_opening_gate(confirmed_signal(), recalculated_risk(), breakout)
    assert ok is False
    assert "breakout confirmation" in reason


def test_persistent_opening_gate_rejects_pre_breakout_risk():
    risk = recalculated_risk(); risk["recalculated_after_breakout"] = False
    ok, reason = evaluate_persistent_opening_gate(confirmed_signal(), risk, confirmed_breakout())
    assert ok is False
    assert "post-breakout" in reason


def test_completed_15_minute_candle_requires_interval_to_elapse():
    now = datetime(2026, 8, 28, 15, 22, tzinfo=timezone.utc)
    assert is_completed_candle(datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc), "15Min", now) is True
    assert is_completed_candle(datetime(2026, 8, 28, 15, 15, tzinfo=timezone.utc), "15Min", now) is False


def test_regular_session_filter_excludes_after_hours():
    assert is_regular_session_candle(datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc)) is True
    assert is_regular_session_candle(datetime(2026, 8, 28, 20, 0, tzinfo=timezone.utc)) is False
