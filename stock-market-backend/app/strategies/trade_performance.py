from collections import defaultdict
from statistics import median


def _avg(values: list[float], digits: int = 4):
    return round(sum(values) / len(values), digits) if values else None


def _group(entries: list[dict], field: str) -> list[dict]:
    groups = defaultdict(list)
    for entry in entries:
        groups[entry[field]].append(entry)
    result = []
    for key in sorted(groups):
        subset = groups[key]
        wins = [e for e in subset if e["outcome"] == "WIN"]
        losses = [e for e in subset if e["outcome"] == "LOSS"]
        breakeven = [e for e in subset if e["outcome"] == "BREAKEVEN"]
        r_values = [e["realized_r"] for e in subset if e["realized_r"] is not None]
        gross_profit = sum(max(e["realized_per_share"], 0) for e in subset)
        gross_loss_abs = sum(abs(min(e["realized_per_share"], 0)) for e in subset)
        result.append({
            "key": key,
            "trades": len(subset),
            "wins": len(wins),
            "losses": len(losses),
            "breakeven": len(breakeven),
            "win_rate_pct": round(len(wins) * 100.0 / len(subset), 2),
            "average_r": round(sum(r_values) / len(r_values), 4) if r_values else None,
            "expectancy_r": round(sum(r_values) / len(r_values), 4) if r_values else None,
            "profit_factor": round(gross_profit / gross_loss_abs, 4) if gross_loss_abs > 0 else None,
            "average_holding_minutes": round(sum(e["holding_minutes"] for e in subset) / len(subset), 2),
        })
    return result


def calculate_trade_statistics(entries: list[dict]) -> dict:
    total = len(entries)
    wins = [e for e in entries if e["outcome"] == "WIN"]
    losses = [e for e in entries if e["outcome"] == "LOSS"]
    breakeven = [e for e in entries if e["outcome"] == "BREAKEVEN"]
    r_values = [e["realized_r"] for e in entries if e["realized_r"] is not None]

    gross_profit = round(sum(max(e["realized_per_share"], 0) for e in entries), 6)
    gross_loss_abs = round(sum(abs(min(e["realized_per_share"], 0)) for e in entries), 6)
    net = round(sum(e["realized_per_share"] for e in entries), 6)
    profit_factor = round(gross_profit / gross_loss_abs, 4) if gross_loss_abs > 0 else None

    average_r = round(sum(r_values) / len(r_values), 4) if r_values else None
    median_r = round(float(median(r_values)), 4) if r_values else None
    average_winner_r = _avg([e["realized_r"] for e in wins if e["realized_r"] is not None])
    average_loser_r = _avg([e["realized_r"] for e in losses if e["realized_r"] is not None])
    average_holding = _avg([e["holding_minutes"] for e in entries], digits=2)

    best = max(entries, key=lambda e: e["realized_r"] if e["realized_r"] is not None else float("-inf"), default=None)
    worst = min(entries, key=lambda e: e["realized_r"] if e["realized_r"] is not None else float("inf"), default=None)

    win_rate = round(len(wins) * 100.0 / total, 2) if total else 0.0
    loss_rate = round(len(losses) * 100.0 / total, 2) if total else 0.0
    summary = (
        f"{total} completed analytical trade(s): win rate {win_rate:.2f}%"
        + (f", average {average_r:+.2f}R" if average_r is not None else "")
        + f", net {net:+.4f}/share."
    )

    return {
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(breakeven),
        "win_rate_pct": win_rate,
        "loss_rate_pct": loss_rate,
        "average_r": average_r,
        "median_r": median_r,
        "expectancy_r": average_r,
        "gross_profit_per_share": gross_profit,
        "gross_loss_per_share": round(-gross_loss_abs, 6),
        "net_realized_per_share": net,
        "profit_factor": profit_factor,
        "average_winner_r": average_winner_r,
        "average_loser_r": average_loser_r,
        "average_holding_minutes": average_holding,
        "stop_hit_exits": sum(1 for e in entries if e["state"] == "STOP_HIT"),
        "target_2_hit_exits": sum(1 for e in entries if e["state"] == "TARGET_2_HIT"),
        "trailing_stop_exits": sum(1 for e in entries if e.get("exit_reason") == "TRAILING_STOP"),
        "best_trade": best,
        "worst_trade": worst,
        "by_symbol": _group(entries, "symbol"),
        "by_timeframe": _group(entries, "timeframe"),
        "summary": summary,
    }
