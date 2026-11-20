from datetime import datetime, timedelta, timezone

from app.services import holdings_guard_service as hg

NOW = datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc)


def test_trade_quantity():
    assert hg.trade_quantity(15, 40) == 6       # WMT: 6 traded, 9 core
    assert hg.trade_quantity(2, 40) == 1        # at least one share
    assert hg.trade_quantity(0.5, 40) == 0


def test_auto_trail_percent():
    assert hg.auto_trail_percent(2.0) == 5.0    # 2.5 x 2% daily ATR
    assert hg.auto_trail_percent(1.0) == 4.0    # floor for calm stocks (KO)
    assert hg.auto_trail_percent(6.0) == 12.0   # cap for wild stocks
    assert hg.auto_trail_percent(None) == 8.0


def decide(**kw):
    args = dict(sold_price=545.0, sold_at=NOW - timedelta(days=1), now=NOW, price=500.0,
                bounce_triggered=False, market_ok=True, rebuy_above_pct=1.0, max_days=10)
    args.update(kw)
    return hg.rebuy_decision(**args)


def test_amd_example_rebuys_at_support_bounce():
    d = decide(price=488.0, bounce_triggered=True)
    assert d.buy and d.reason.startswith("REBUY_AT_SUPPORT")


def test_no_rebuy_while_market_falling():
    assert not decide(price=488.0, bounce_triggered=True, market_ok=False).buy


def test_waits_without_signal():
    d = decide(price=500.0)
    assert not d.buy and "Waiting" in d.reason


def test_recovery_safety_net():
    d = decide(price=551.0)       # > 545 * 1.01
    assert d.buy and d.reason.startswith("REBUY_RECOVERY")


def test_max_days():
    d = decide(price=500.0, sold_at=NOW - timedelta(days=10))
    assert d.buy and d.reason.startswith("REBUY_MAX_DAYS")


def test_guarded_symbols(monkeypatch):
    monkeypatch.setattr(hg.settings, "holdings_guard_enabled", True, raising=False)
    monkeypatch.setattr(hg.settings, "holdings_guard_symbols", " wmt, AMD ,", raising=False)
    assert hg.guarded_symbols() == {"WMT", "AMD"}
    assert hg.is_guarded("wmt")
    monkeypatch.setattr(hg.settings, "holdings_guard_enabled", False, raising=False)
    assert not hg.is_guarded("WMT")
