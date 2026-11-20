from app.strategies.position_pnl_analytics import calculate_per_share_position_analytics


def test_open_position_math():
    result = calculate_per_share_position_analytics(
        entry_price=100, initial_risk_per_share=2, current_price=102.5,
        exit_price=None, terminal=False, highs=[103, 104, 103.5], lows=[99.5, 98.5, 100],
    )
    assert result["unrealized_per_share"] == 2.5
    assert result["unrealized_r"] == 1.25
    assert result["mfe_per_share"] == 4
    assert result["mfe_r"] == 2
    assert result["mae_per_share"] == -1.5
    assert result["mae_r"] == -0.75
    assert result["realized_per_share"] is None


def test_closed_position_math():
    result = calculate_per_share_position_analytics(
        entry_price=100, initial_risk_per_share=2, current_price=102.7,
        exit_price=102.5, terminal=True, highs=[104, 105], lows=[99, 102.4],
    )
    assert result["realized_per_share"] == 2.5
    assert result["realized_r"] == 1.25
    assert result["mfe_per_share"] == 5
    assert result["mae_per_share"] == -1
    assert result["giveback_from_mfe_per_share"] == 2.5
    assert result["exit_efficiency_pct"] == 50.0
    assert result["unrealized_per_share"] is None


def test_loss_exit_efficiency_can_be_negative():
    result = calculate_per_share_position_analytics(
        entry_price=100, initial_risk_per_share=2, current_price=98,
        exit_price=98, terminal=True, highs=[101], lows=[97.5],
    )
    assert result["realized_per_share"] == -2
    assert result["realized_r"] == -1
    assert result["exit_efficiency_pct"] == -200.0
