from datetime import datetime, timezone

from app.services import alert_service as al


def enable(monkeypatch, sent):
    monkeypatch.setattr(al.settings, "telegram_bot_token", "t", raising=False)
    monkeypatch.setattr(al.settings, "telegram_chat_id", "1", raising=False)
    monkeypatch.setattr(al.settings, "alerts_enabled", True, raising=False)
    monkeypatch.setattr(al, "_post", lambda text: sent.append(text) or True)
    al._last_sent.clear()


def test_disabled_without_token(monkeypatch):
    monkeypatch.setattr(al.settings, "telegram_bot_token", "", raising=False)
    assert al.send("x", wait=True) is False


def test_send_and_cooldown(monkeypatch):
    sent = []
    enable(monkeypatch, sent)
    assert al.send("a", key="stale", cooldown_minutes=60, wait=True)
    assert not al.send("b", key="stale", cooldown_minutes=60, wait=True)
    assert al.send("c", wait=True)
    assert sent == ["a", "c"]


def test_format_buy():
    text = al.format_buy("WMT", {"shares": 15}, {
        "entry_type": "SUPPORT_BOUNCE",
        "risk_reward": {"entry": 125.24, "stop_loss": 123.1, "target_1": 131.78, "rr_1": 3.1},
    })
    assert text.startswith("🟢 BUY WMT x15 (SUPPORT_BOUNCE)")
    assert "Stop 123.1" in text and "Target 131.78" in text


def test_format_sell_loss():
    trade = {"symbol": "TSLA", "qty": 5.0, "entry_price": 386.75, "exit_price": 384.142,
             "pnl": -13.04, "pnl_pct": -0.67}
    text = al.format_sell(trade, "stop loss")
    assert text.startswith("🔴 SELL TSLA x5 (stop loss)")
    assert "P&L -$13.04" in text


def test_format_summary():
    trades = [{"symbol": "AVGO", "pnl": 10.21}, {"symbol": "TSLA", "pnl": -13.04}]
    text = al.format_summary(trades, [{"unrealized_pnl": 13.5}], "Thu Nov 19")
    assert "Closed trades: 2 (1 won)  Realized -$2.83" in text
    assert "Best AVGO +$10.21  Worst TSLA -$13.04" in text
    assert "Unrealized +$13.50" in text
