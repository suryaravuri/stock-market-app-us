from __future__ import annotations


def calculate_per_share_position_analytics(
    *,
    entry_price: float,
    initial_risk_per_share: float,
    current_price: float | None,
    exit_price: float | None,
    terminal: bool,
    highs: list[float],
    lows: list[float],
) -> dict:
    """Pure #15E analytics math; no DB, market, or broker side effects."""
    entry = float(entry_price)
    risk = float(initial_risk_per_share)
    best_price = max([entry, *highs]) if highs else entry
    worst_price = min([entry, *lows]) if lows else entry
    mfe = round(best_price - entry, 6)
    mae = round(worst_price - entry, 6)
    mfe_r = round(mfe / risk, 4) if risk > 0 else None
    mae_r = round(mae / risk, 4) if risk > 0 else None

    realized = realized_r = unrealized = unrealized_r = None
    giveback = exit_efficiency = None
    if terminal and exit_price is not None:
        realized = round(float(exit_price) - entry, 6)
        realized_r = round(realized / risk, 4) if risk > 0 else None
        giveback = round(mfe - realized, 6)
        exit_efficiency = round((realized / mfe) * 100.0, 2) if mfe > 0 else None
    elif current_price is not None:
        unrealized = round(float(current_price) - entry, 6)
        unrealized_r = round(unrealized / risk, 4) if risk > 0 else None

    return {
        "best_price": round(best_price, 6),
        "worst_price": round(worst_price, 6),
        "mfe_per_share": mfe,
        "mfe_r": mfe_r,
        "mae_per_share": mae,
        "mae_r": mae_r,
        "unrealized_per_share": unrealized,
        "unrealized_r": unrealized_r,
        "realized_per_share": realized,
        "realized_r": realized_r,
        "giveback_from_mfe_per_share": giveback,
        "exit_efficiency_pct": exit_efficiency,
    }
