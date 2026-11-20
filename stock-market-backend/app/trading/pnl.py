"""FIFO profit-and-loss from a list of fills. Pure Python, no I/O.

Every SELL fill closes the oldest open BUY lots of the same
(exchange, symbol, product). One SELL fill produces one closed trade, using
the quantity-weighted cost of the lots it consumed. A SELL with no tracked
BUY (e.g. shares bought before tracking started) is reported separately and
excluded from P&L, because its cost is unknown.

Amounts are gross: exchange charges, taxes and brokerage are NOT deducted.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class Fill:
    exchange: str
    tradingsymbol: str
    product: str
    side: str  # BUY | SELL
    quantity: int
    price: float
    timestamp: datetime  # timezone-aware
    ref: str | None = None

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.exchange, self.tradingsymbol, self.product)


@dataclass
class ClosedTrade:
    exchange: str
    tradingsymbol: str
    product: str
    quantity: int
    buy_price: float
    sell_price: float
    opened_at: datetime
    closed_at: datetime
    pnl: float
    return_percent: float


@dataclass
class OpenPosition:
    exchange: str
    tradingsymbol: str
    product: str
    quantity: int
    average_price: float
    opened_at: datetime
    last_price: float | None = None
    unrealized_pnl: float | None = None


@dataclass
class UnmatchedSell:
    exchange: str
    tradingsymbol: str
    product: str
    quantity: int
    price: float
    timestamp: datetime


@dataclass
class PnLResult:
    closed: list[ClosedTrade] = field(default_factory=list)
    open_positions: list[OpenPosition] = field(default_factory=list)
    unmatched_sells: list[UnmatchedSell] = field(default_factory=list)


def compute_fifo(fills: list[Fill]) -> PnLResult:
    result = PnLResult()
    # Each lot: [remaining_qty, price, timestamp]
    lots: dict[tuple, deque] = defaultdict(deque)

    for fill in sorted(fills, key=lambda f: f.timestamp):
        if fill.quantity <= 0:
            continue
        book = lots[fill.key]

        if fill.side == "BUY":
            book.append([fill.quantity, fill.price, fill.timestamp])
            continue

        remaining = fill.quantity
        matched_qty = 0
        matched_cost = 0.0
        first_opened = None
        while remaining > 0 and book:
            lot = book[0]
            take = min(remaining, lot[0])
            matched_qty += take
            matched_cost += take * lot[1]
            first_opened = first_opened or lot[2]
            lot[0] -= take
            remaining -= take
            if lot[0] == 0:
                book.popleft()

        if matched_qty:
            buy_price = matched_cost / matched_qty
            pnl = (fill.price - buy_price) * matched_qty
            result.closed.append(
                ClosedTrade(
                    exchange=fill.exchange,
                    tradingsymbol=fill.tradingsymbol,
                    product=fill.product,
                    quantity=matched_qty,
                    buy_price=round(buy_price, 4),
                    sell_price=fill.price,
                    opened_at=first_opened,
                    closed_at=fill.timestamp,
                    pnl=round(pnl, 2),
                    return_percent=round((fill.price / buy_price - 1) * 100, 2),
                )
            )
        if remaining:
            result.unmatched_sells.append(
                UnmatchedSell(
                    exchange=fill.exchange,
                    tradingsymbol=fill.tradingsymbol,
                    product=fill.product,
                    quantity=remaining,
                    price=fill.price,
                    timestamp=fill.timestamp,
                )
            )

    for (exchange, symbol, product), book in lots.items():
        quantity = sum(lot[0] for lot in book)
        if quantity <= 0:
            continue
        cost = sum(lot[0] * lot[1] for lot in book)
        result.open_positions.append(
            OpenPosition(
                exchange=exchange,
                tradingsymbol=symbol,
                product=product,
                quantity=quantity,
                average_price=round(cost / quantity, 4),
                opened_at=book[0][2],
            )
        )
    return result


def apply_last_prices(positions: list[OpenPosition], prices: dict[str, float]) -> None:
    """prices keyed 'EXCHANGE:SYMBOL'. Missing prices leave unrealized as None."""
    for position in positions:
        price = prices.get(f"{position.exchange}:{position.tradingsymbol}")
        if price is None:
            continue
        position.last_price = price
        position.unrealized_pnl = round((price - position.average_price) * position.quantity, 2)


def summarize(result: PnLResult) -> dict:
    closed = result.closed
    wins = [t for t in closed if t.pnl > 0]
    losses = [t for t in closed if t.pnl < 0]
    realized = round(sum(t.pnl for t in closed), 2)

    unrealized_values = [p.unrealized_pnl for p in result.open_positions]
    unrealized = (
        round(sum(v for v in unrealized_values if v is not None), 2)
        if result.open_positions
        else 0.0
    )

    daily: dict[str, float] = defaultdict(float)
    for trade in closed:
        daily[trade.closed_at.astimezone(IST).date().isoformat()] += trade.pnl

    per_symbol: dict[str, dict] = {}
    for trade in closed:
        row = per_symbol.setdefault(
            trade.tradingsymbol,
            {"tradingsymbol": trade.tradingsymbol, "trades": 0, "wins": 0, "realized_pnl": 0.0},
        )
        row["trades"] += 1
        row["wins"] += 1 if trade.pnl > 0 else 0
        row["realized_pnl"] = round(row["realized_pnl"] + trade.pnl, 2)

    return {
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "unrealized_complete": all(v is not None for v in unrealized_values),
        "closed_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_percent": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "average_win": round(sum(t.pnl for t in wins) / len(wins), 2) if wins else None,
        "average_loss": round(sum(t.pnl for t in losses) / len(losses), 2) if losses else None,
        "best_trade": max((t.pnl for t in closed), default=None),
        "worst_trade": min((t.pnl for t in closed), default=None),
        "open_positions": len(result.open_positions),
        "unmatched_sells": len(result.unmatched_sells),
        "daily_pnl": [
            {"date": day, "pnl": round(value, 2)} for day, value in sorted(daily.items())
        ],
        "per_symbol": sorted(per_symbol.values(), key=lambda r: r["realized_pnl"], reverse=True),
    }
