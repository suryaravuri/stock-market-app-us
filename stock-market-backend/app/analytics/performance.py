"""Pure calculations for the Sector Heatmap and P&L screens (unit tested).

No database or broker calls here - services feed plain values in.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

# How many trading sessions back each heatmap period compares against.
PERIOD_SESSIONS = {"1D": 1, "1W": 5, "1M": 21, "3M": 63, "6M": 126}


# ------------------------------------------------------------- heatmap
def change_pct(last: float | None, reference: float | None) -> float | None:
    if not last or not reference:
        return None
    return round((last / reference - 1) * 100, 2)


def reference_close(prior_closes_newest_first: list[float], period: str) -> float | None:
    """prior_closes = daily closes BEFORE the latest price's session,
    newest first. 1D -> yesterday's close, 1W -> 5 sessions back..."""
    n = PERIOD_SESSIONS[period]
    if len(prior_closes_newest_first) < n:
        return None
    return prior_closes_newest_first[n - 1]


def group_by_sector(rows: list[dict]) -> list[dict]:
    """rows: {symbol, sector, change_pct, price, ...}. Returns sectors sorted
    best to worst, each with its stocks sorted best to worst."""
    sectors: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        sectors[row["sector"]].append(row)
    out = []
    for sector, stocks in sectors.items():
        valid = [s["change_pct"] for s in stocks if s["change_pct"] is not None]
        stocks.sort(key=lambda s: (s["change_pct"] is None, -(s["change_pct"] or 0)))
        out.append({
            "sector": sector,
            "avg_change_pct": round(sum(valid) / len(valid), 2) if valid else None,
            "advancers": sum(1 for v in valid if v > 0),
            "decliners": sum(1 for v in valid if v < 0),
            "stocks": stocks,
        })
    out.sort(key=lambda s: (s["avg_change_pct"] is None, -(s["avg_change_pct"] or 0)))
    return out


# ----------------------------------------------------------------- P&L
@dataclass
class Fill:
    symbol: str
    side: str          # "buy" | "sell"
    qty: float
    price: float
    time: datetime


def round_trips(fills: list[Fill]) -> list[dict]:
    """FIFO-match buys and sells per symbol into closed trades (long only).
    Partial fills split correctly; unmatched buys stay open."""
    open_lots: dict[str, list[list]] = defaultdict(list)   # symbol -> [[qty, price, time]]
    trades = []
    for f in sorted(fills, key=lambda x: x.time):
        if f.side == "buy":
            open_lots[f.symbol].append([f.qty, f.price, f.time])
            continue
        remaining = f.qty
        lots = open_lots[f.symbol]
        while remaining > 1e-9 and lots:
            lot = lots[0]
            qty = min(remaining, lot[0])
            pnl = (f.price - lot[1]) * qty
            trades.append({
                "symbol": f.symbol,
                "qty": qty,
                "entry_price": lot[1],
                "exit_price": f.price,
                "entry_time": lot[2],
                "exit_time": f.time,
                "pnl": round(pnl, 2),
                "pnl_pct": round((f.price / lot[1] - 1) * 100, 2) if lot[1] else None,
            })
            lot[0] -= qty
            remaining -= qty
            if lot[0] <= 1e-9:
                lots.pop(0)
    return trades


def bucket_key(day: date, group: str) -> tuple[str, str]:
    """(sort key, label) for day / week (Mon-Fri) / month."""
    if group == "week":
        monday = day - timedelta(days=day.weekday())
        return monday.isoformat(), f"Week of {monday.strftime('%b %d')}"
    if group == "month":
        return day.strftime("%Y-%m"), day.strftime("%b %Y")
    return day.isoformat(), day.strftime("%a %b %d")


def aggregate_pnl(
    equity_points: list[tuple[date, float]],
    base_value: float | None,
    trades: list[dict],
    group: str,
    to_local_date,
) -> list[dict]:
    """Buckets with account P&L (equity change, incl. open positions) and
    realized P&L from closed trades."""
    buckets: dict[str, dict] = {}

    def bucket(day: date) -> dict:
        key, label = bucket_key(day, group)
        return buckets.setdefault(key, {
            "key": key, "label": label, "account_pnl": 0.0, "realized_pnl": 0.0,
            "trades": 0, "wins": 0, "losses": 0, "start_equity": None, "end_equity": None,
        })

    previous = base_value
    for day, equity in equity_points:
        b = bucket(day)
        if previous is not None:
            b["account_pnl"] += equity - previous
        if b["start_equity"] is None:
            b["start_equity"] = previous if previous is not None else equity
        b["end_equity"] = equity
        previous = equity

    for t in trades:
        b = bucket(to_local_date(t["exit_time"]))
        b["realized_pnl"] += t["pnl"]
        b["trades"] += 1
        b["wins"] += int(t["pnl"] > 0)
        b["losses"] += int(t["pnl"] < 0)

    out = []
    for key in sorted(buckets):
        b = buckets[key]
        b["account_pnl"] = round(b["account_pnl"], 2)
        b["realized_pnl"] = round(b["realized_pnl"], 2)
        b["account_pnl_pct"] = (
            round(b["account_pnl"] / b["start_equity"] * 100, 2) if b["start_equity"] else None
        )
        b["win_rate"] = round(b["wins"] / b["trades"] * 100, 1) if b["trades"] else None
        out.append(b)
    return out
