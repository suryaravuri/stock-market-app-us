import pytest

from app.strategies.support_bounce import BounceRules, evaluate_bounce

ATR = 2.0
LEVELS = [293.4, 304.6, 310.0, 280.0]


def bounce(**kw):
    params = dict(open_=293.6, high=294.4, low=293.2, close=294.2,
                  levels=LEVELS, atr=ATR, trend_score=40)
    params.update(kw)
    return evaluate_bounce(**params)


def test_googl_style_bounce_triggers():
    d = bounce()
    assert d.triggered, d.reasons
    assert d.support == 293.4
    assert d.entry == 294.2
    # support - 0.25 ATR = 292.9 is only 0.65 ATR under entry, so the
    # 1 ATR minimum applies: 294.2 - 2.0
    assert d.stop_loss == pytest.approx(292.2)
    assert d.target_1 == 304.6 and d.target_2 == 310.0
    assert d.rr_1 == pytest.approx(round(10.4 / 2.0, 2))


def test_no_support_nearby():
    d = bounce(open_=299.0, high=300.5, low=298.9, close=300.2)
    assert not d.triggered
    assert "not bouncing" in d.reasons[0]


def test_close_below_support_is_not_a_bounce():
    d = bounce(open_=293.5, high=293.6, low=292.8, close=293.0)
    assert not d.triggered


def test_wick_too_far_below_support_means_support_broke():
    d = bounce(low=292.5)          # 0.9 below support > tolerance 0.5
    assert not d.triggered


def test_red_candle_rejected():
    d = bounce(open_=294.3, close=294.0)
    assert not d.triggered
    assert "not green" in " ".join(d.reasons)


def test_bearish_trend_rejected():
    d = bounce(trend_score=-20)
    assert not d.triggered
    assert "bearish" in " ".join(d.reasons)


def test_resistance_too_close_rejected():
    d = bounce(levels=[293.4, 295.0])
    assert not d.triggered
    assert "Reward/risk" in " ".join(d.reasons)


def test_no_resistance_above_rejected():
    d = bounce(levels=[293.4])
    assert not d.triggered
    assert "No resistance" in " ".join(d.reasons)


def test_highest_tested_support_is_used():
    d = bounce(levels=[293.4, 293.0, 304.6])
    assert d.support == 293.4


def test_custom_rr():
    loose = BounceRules(min_rr=1.0)
    assert bounce(levels=[293.4, 297.0], **{}).triggered is False
    assert evaluate_bounce(open_=293.6, high=294.4, low=293.2, close=294.2,
                           levels=[293.4, 297.0], atr=ATR, trend_score=40,
                           rules=loose).triggered


def test_missing_atr():
    assert not bounce(atr=None).triggered


def test_nxpi_2026_11_16_stop_is_at_least_one_atr():
    # Real trade: support 259.54, entry 260.50, ATR ~1.68. Old stop 259.12
    # (0.8 ATR) was hit by a 259.03 wick; the new stop sits below that.
    d = evaluate_bounce(open_=259.80, high=260.70, low=259.50, close=260.50,
                        levels=[259.54, 271.98], atr=1.68, trend_score=10)
    assert d.triggered, d.reasons
    assert d.stop_loss == pytest.approx(260.50 - 1.68)
    assert d.stop_loss < 259.03
    assert d.rr_1 == pytest.approx(round((271.98 - 260.50) / 1.68, 2))


def test_support_buffer_used_when_it_is_already_wider():
    # close far above support: support - 0.25 ATR is more than 1 ATR away
    d = bounce(open_=293.6, high=295.0, low=293.5, close=294.9)
    assert d.stop_loss == pytest.approx(292.9)


def test_min_stop_can_be_disabled():
    d = bounce(rules=BounceRules(min_stop_atr=0.0))
    assert d.stop_loss == pytest.approx(292.9)


# ---- experimental rules: level-sized zone + multi-candle confirmation -------
# Real COST 15-min candles, 2026-11-20 (support 1096.46 from daily levels):
#   9:30 O1104.85 H1108.91 L1100.29 C1104.72   9:45 O1105.66 H1108.93 L1105.42 C1106.67
#  10:00 O1107.01 H1112.95 L1106.83 C1112.95   then up to 1122.67 by 10:45
SUPPORT = 1096.46


def test_cost_current_rules_miss_it():
    d = evaluate_bounce(open_=1104.85, high=1108.91, low=1100.29, close=1104.72,
                        levels=[SUPPORT, 1125.0], atr=4.0, trend_score=5)
    assert not d.triggered


def test_level_zone_alone_still_needs_green_candle():
    d = evaluate_bounce(open_=1104.85, high=1108.91, low=1100.29, close=1104.72,
                        levels=[SUPPORT, 1125.0], atr=4.0, trend_score=5,
                        rules=BounceRules(level_zone_atr=0.25), level_atr=20.0)
    assert not d.triggered            # in the wider zone, but the candle closed red


def test_cost_945_rejected_for_weak_close():
    d = evaluate_bounce(open_=1105.66, high=1108.93, low=1105.42, close=1106.67,
                        levels=[SUPPORT, 1140.0], atr=4.0, trend_score=5,
                        rules=BounceRules(level_zone_atr=0.25, confirm_bars=2),
                        level_atr=20.0, prev_lows=[1100.29])
    assert not d.triggered and "Weak close" in d.reasons[0]


def test_cost_1000_three_candle_confirmation_triggers_if_rr_allows():
    rules = BounceRules(level_zone_atr=0.25, confirm_bars=3)
    d = evaluate_bounce(open_=1107.01, high=1112.95, low=1106.83, close=1112.95,
                        levels=[SUPPORT, 1145.0], atr=4.0, trend_score=5, rules=rules,
                        level_atr=20.0, prev_lows=[1105.42, 1100.29])
    assert d.triggered, d.reasons
    # ...but with resistance close by, entering 16 above support fails RR
    d2 = evaluate_bounce(open_=1107.01, high=1112.95, low=1106.83, close=1112.95,
                         levels=[SUPPORT, 1125.0], atr=4.0, trend_score=5, rules=rules,
                         level_atr=20.0, prev_lows=[1105.42, 1100.29])
    assert not d2.triggered


def test_multi_candle_rejects_if_current_candle_broke_support():
    d = evaluate_bounce(open_=1100.0, high=1104.0, low=1090.0, close=1103.0,
                        levels=[SUPPORT, 1140.0], atr=4.0, trend_score=5,
                        rules=BounceRules(level_zone_atr=0.25, confirm_bars=2),
                        level_atr=20.0, prev_lows=[1099.0])
    assert not d.triggered


def test_defaults_unchanged_with_new_inputs():
    d = evaluate_bounce(open_=1107.01, high=1112.95, low=1106.83, close=1112.95,
                        levels=[SUPPORT, 1145.0], atr=4.0, trend_score=5,
                        level_atr=20.0, prev_lows=[1105.42, 1100.29])
    assert not d.triggered
