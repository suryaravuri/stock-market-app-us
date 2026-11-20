from datetime import datetime, timedelta, timezone

import pytest

from app.services import live_bounce_service as lb
from app.strategies.support_bounce import BounceRules, reprice_bounce

T0 = datetime(2026, 11, 16, 19, 30, tzinfo=timezone.utc)  # 2:30 PM ET


def minute(n):
    return T0 + timedelta(minutes=n)


# ------------------------------------------------------------ repricing
def test_reprice_skips_when_price_back_at_support():
    # NXPI 2026-11-16: support 259.54, filled 259.61 - just above support is
    # allowed, at/below is not.
    d = reprice_bounce(support=259.54, resistance=271.98, target_2=None,
                       live_price=259.50, atr=2.12)
    assert not d.triggered
    assert "back at/below support" in d.reasons[0]


def test_reprice_uses_live_price_for_stop_and_rr():
    d = reprice_bounce(support=259.54, resistance=271.98, target_2=275.0,
                       live_price=259.61, atr=2.12)
    assert d.triggered
    assert d.entry == 259.61
    assert d.stop_loss == pytest.approx(259.61 - 2.12)
    assert d.rr_1 == pytest.approx(round((271.98 - 259.61) / 2.12, 2))


def test_reprice_rejects_poor_rr_at_live_price():
    d = reprice_bounce(support=100.0, resistance=102.0, target_2=None,
                       live_price=101.0, atr=1.0, rules=BounceRules(min_rr=1.5))
    assert not d.triggered
    assert "reward/risk" in d.reasons[0]


def test_reprice_at_resistance():
    d = reprice_bounce(support=100.0, resistance=102.0, target_2=None,
                       live_price=102.5, atr=1.0)
    assert not d.triggered


# ------------------------------------------------------------ aggregator
def test_aggregator_emits_on_last_minute_of_bucket():
    agg = lb.MinuteAggregator(minutes=5)
    for i in range(4):
        assert agg.add("NXPI", minute(i), 260, 261, 259 + i * 0.1, 260.5, 100) == []
    done = agg.add("NXPI", minute(4), 260.5, 262, 259.0, 261.5, 100)
    assert len(done) == 1
    c = done[0]
    assert c.start == T0
    assert c.open == 260 and c.high == 262 and c.low == 259.0 and c.close == 261.5
    assert c.volume == 500


def test_aggregator_emits_when_minutes_are_missing():
    agg = lb.MinuteAggregator(minutes=5)
    agg.add("X", minute(0), 10, 11, 9, 10.5, 1)
    agg.add("X", minute(2), 10.5, 12, 10, 11, 1)        # minutes 1,3,4 had no trades
    done = agg.add("X", minute(6), 11, 11, 10, 10.2, 1)  # next bucket
    assert len(done) == 1 and done[0].start == T0 and done[0].close == 11


def test_aggregator_ignores_duplicates_and_never_emits_twice():
    agg = lb.MinuteAggregator(minutes=5)
    agg.add("X", minute(3), 10, 11, 9, 10, 1)
    assert len(agg.add("X", minute(4), 10, 11, 9, 10, 1)) == 1
    assert agg.add("X", minute(4), 10, 11, 9, 10, 1) == []   # duplicate bar
    assert agg.add("X", minute(5), 10, 11, 9, 10, 1) == []   # new bucket starts, old already emitted


def test_aggregator_one_minute_mode():
    agg = lb.MinuteAggregator(minutes=1)
    assert len(agg.add("X", minute(0), 10, 11, 9, 10, 1)) == 1


# ------------------------------------------------------- live candle eval
def plan(**kw):
    p = dict(symbol="NXPI", stock_id=1, watchlist_id=1, user_id=1, holding_style="SWING",
             levels=[259.54, 271.98], entry_atr=2.12, trend_score=10.0, base_setup={},
             created_at=T0)
    p.update(kw)
    return lb.BouncePlan(**p)


def test_live_candle_bounce_triggers_with_plan_levels():
    candle = lb.LiveCandle(T0, open=259.70, high=260.60, low=259.45, close=260.45,
                           volume=1000, last_bar=minute(4))
    d = lb.evaluate_live_candle(plan(), candle, BounceRules())
    assert d.triggered, d.reasons
    assert d.support == 259.54
    assert d.stop_loss == pytest.approx(260.45 - 2.12)


def test_live_candle_bearish_trend_blocks():
    candle = lb.LiveCandle(T0, 259.70, 260.60, 259.45, 260.45, 1000, minute(4))
    d = lb.evaluate_live_candle(plan(trend_score=-20), candle, BounceRules())
    assert not d.triggered


def test_stale_plan_is_ignored():
    lb.remember_plan(plan(created_at=T0))
    assert lb.get_plan("NXPI", now=T0 + timedelta(minutes=10)) is not None
    assert lb.get_plan("NXPI", now=T0 + timedelta(minutes=40)) is None


# --------------------------------------------------------- live check
def test_apply_live_check_uses_fresh_stream_price(monkeypatch):
    monkeypatch.setattr(lb.settings, "live_price_check_enabled", True, raising=False)
    now = datetime.now(timezone.utc)
    lb.set_live_price("NXPI", 259.50, now)
    bounce = {"triggered": True, "reasons": ["Bounced off support 259.54"],
              "support": 259.54, "resistance": 271.98, "target_1": 271.98,
              "target_2": None, "entry": 260.45, "entry_atr": 2.12}
    out = lb.apply_live_check(bounce, "NXPI", BounceRules())
    assert out["triggered"] is False
    assert out["live_price"] == 259.50
    assert "back at/below support" in out["live_check"]


def test_apply_live_check_reprices(monkeypatch):
    monkeypatch.setattr(lb.settings, "live_price_check_enabled", True, raising=False)
    lb.set_live_price("AMD", 101.2, datetime.now(timezone.utc))
    bounce = {"triggered": True, "reasons": ["Bounced"], "support": 100.0,
              "resistance": 110.0, "target_1": 110.0, "target_2": None,
              "entry": 101.0, "entry_atr": 1.0}
    out = lb.apply_live_check(bounce, "AMD", BounceRules())
    assert out["triggered"] and out["entry"] == 101.2
    assert out["stop_loss"] == pytest.approx(99.75)   # support - 0.25 ATR is lower than 101.2 - 1
    assert out["signal_entry"] == 101.0


def test_apply_live_check_fails_closed_without_price(monkeypatch):
    monkeypatch.setattr(lb.settings, "live_price_check_enabled", True, raising=False)
    monkeypatch.setattr(lb, "latest_price", lambda symbol, now=None: None)
    bounce = {"triggered": True, "reasons": ["Bounced"], "support": 100.0,
              "resistance": 110.0, "entry": 101.0, "entry_atr": 1.0}
    out = lb.apply_live_check(bounce, "ZZZZ", BounceRules())
    assert out["triggered"] is False and out["live_check"] == "NO_LIVE_PRICE"


def test_avgo_2026_11_18_stale_entry_fails_live_rr():
    # Yesterday's signal: support 335.89, resistance 351.94; next morning
    # price 349.93 -> reward 2.01 vs risk 14.67 -> must not buy.
    d = reprice_bounce(support=335.89, resistance=351.94, target_2=None,
                       live_price=349.93, atr=2.5)
    assert not d.triggered
