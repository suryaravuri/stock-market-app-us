"""Backtest statistics with pandas."""
from __future__ import annotations

import math

import pandas as pd

from app.backtest.broker import Trade


def trades_frame(trades: list[Trade]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(
            columns=["symbol", "entry_time", "exit_time", "pnl", "pnl_percent", "r_multiple", "exit_reason"]
        )
    return pd.DataFrame(
        [
            {
                "symbol": t.symbol,
                "signal_time": t.signal_time,
                "entry_time": t.entry_time,
                "entry_price": t.entry_price,
                "exit_time": t.exit_time,
                "exit_price": t.exit_price,
                "shares": t.shares,
                "pnl": t.pnl,
                "pnl_percent": t.pnl_percent,
                "r_multiple": t.r_multiple,
                "exit_reason": t.exit_reason,
            }
            for t in trades
        ]
    )


def _round(value, digits=2):
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    return round(float(value), digits)


def summarize(
    trades: list[Trade],
    equity: pd.Series,
    starting_cash: float,
    buy_and_hold_return_percent: float | None,
    bars_in_market: int,
    bars_total: int,
) -> dict:
    """equity: daily closing equity indexed by session date."""
    df = trades_frame(trades)

    ending = float(equity.iloc[-1]) if len(equity) else starting_cash
    total_return = (ending / starting_cash - 1) * 100

    days = (equity.index[-1] - equity.index[0]).days if len(equity) > 1 else 0
    years = days / 365.25 if days else 0
    cagr = ((ending / starting_cash) ** (1 / years) - 1) * 100 if years > 0 and ending > 0 else None

    running_peak = equity.cummax() if len(equity) else equity
    drawdown = (equity / running_peak - 1) * 100 if len(equity) else equity
    max_drawdown = float(drawdown.min()) if len(drawdown) else 0.0

    daily_returns = equity.pct_change().dropna()
    sharpe = (
        daily_returns.mean() / daily_returns.std() * math.sqrt(252)
        if len(daily_returns) > 1 and daily_returns.std() > 0
        else None
    )

    wins = df[df["pnl"] > 0] if len(df) else df
    losses = df[df["pnl"] <= 0] if len(df) else df
    gross_win = float(wins["pnl"].sum()) if len(wins) else 0.0
    gross_loss = float(-losses["pnl"].sum()) if len(losses) else 0.0

    return {
        "starting_cash": _round(starting_cash),
        "ending_equity": _round(ending),
        "total_return_percent": _round(total_return),
        "cagr_percent": _round(cagr),
        "max_drawdown_percent": _round(max_drawdown),
        "sharpe_ratio": _round(sharpe),
        "buy_and_hold_return_percent": _round(buy_and_hold_return_percent),
        "trades": int(len(df)),
        "win_rate_percent": _round(len(wins) / len(df) * 100) if len(df) else None,
        "profit_factor": _round(gross_win / gross_loss) if gross_loss > 0 else None,
        "average_win": _round(wins["pnl"].mean()) if len(wins) else None,
        "average_loss": _round(losses["pnl"].mean()) if len(losses) else None,
        "average_r_multiple": _round(df["r_multiple"].dropna().mean()) if len(df) else None,
        "largest_loss": _round(df["pnl"].min()) if len(df) else None,
        "exposure_percent": _round(bars_in_market / bars_total * 100) if bars_total else None,
        "exit_reasons": {str(k): int(v) for k, v in df["exit_reason"].value_counts().items()} if len(df) else {},
    }


def equity_curve_points(equity: pd.Series) -> list[dict]:
    """Daily equity for charts (about 252 points per year)."""
    return [
        {"date": index.isoformat(), "equity": round(float(value), 2)}
        for index, value in equity.items()
    ]
