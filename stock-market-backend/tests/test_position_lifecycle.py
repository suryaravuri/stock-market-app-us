from app.strategies.position_lifecycle import PositionState, evaluate_long_position_candle


def obs(**kwargs):
    base = dict(
        state=PositionState.POSITION_OPEN,
        candle_high=102.0,
        candle_low=99.5,
        candle_close=101.0,
        entry_price=100.0,
        initial_stop=98.0,
        active_stop=98.0,
        target_1=104.0,
        target_2=106.0,
        target_1_hit=False,
        initial_risk_per_share=2.0,
    )
    base.update(kwargs)
    return evaluate_long_position_candle(**base)


def test_open_position_remains_open_between_levels():
    r = obs()
    assert r.state == PositionState.POSITION_OPEN
    assert r.changed is False


def test_stop_has_priority_when_same_candle_spans_stop_and_target():
    r = obs(candle_low=97.5, candle_high=105.0)
    assert r.state == PositionState.STOP_HIT
    assert r.exit_reason == "STOP_LOSS"
    assert r.exit_price == 98.0


def test_target_one_moves_stop_to_breakeven_for_future_candles():
    r = obs(candle_low=99.0, candle_high=104.2, candle_close=103.8)
    assert r.state == PositionState.TARGET_1_HIT
    assert r.target_1_hit is True
    assert r.active_stop == 100.0


def test_post_target_one_breakeven_stop_can_close_position():
    r = obs(
        state=PositionState.TARGET_1_HIT,
        active_stop=100.0,
        target_1_hit=True,
        candle_low=99.8,
        candle_high=103.0,
        candle_close=101.0,
    )
    assert r.state == PositionState.STOP_HIT
    assert r.exit_reason == "BREAKEVEN_STOP"


def test_target_two_is_terminal():
    r = obs(candle_low=100.5, candle_high=106.2, candle_close=105.8)
    assert r.state == PositionState.TARGET_2_HIT
    assert r.target_2_hit is True
    assert r.exit_reason == "TARGET_2"


def test_trailing_stop_only_uses_close_for_next_candle():
    r = obs(
        state=PositionState.TARGET_1_HIT,
        active_stop=100.0,
        target_1_hit=True,
        candle_low=100.5,
        candle_high=105.0,
        candle_close=104.5,
    )
    assert r.state == PositionState.TRAILING
    assert r.active_stop == 102.5
    assert r.exit_price is None


def test_terminal_state_is_sticky():
    r = obs(state=PositionState.STOP_HIT, active_stop=101.0, target_1_hit=True)
    assert r.state == PositionState.STOP_HIT
    assert r.changed is False
