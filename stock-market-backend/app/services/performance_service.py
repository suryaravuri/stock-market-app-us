"""Data for the Sector Heatmap and P&L screens. Read-only."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.performance import (
    PERIOD_SESSIONS,
    Fill,
    aggregate_pnl,
    change_pct,
    group_by_sector,
    reference_close,
    round_trips,
)
from app.market.sectors import sector_for
from app.market.sessions import is_indian_exchange
from app.models.market_candle import MarketCandle
from app.models.stock import Stock
from app.models.watchlist import WatchlistStock

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")
PNL_RANGES = {"1M": 31, "3M": 92, "6M": 183, "1A": 366}


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class PerformanceService:

    # --------------------------------------------------------- heatmap
    @staticmethod
    def sector_heatmap(db: Session, period: str = "1D", watchlist_id: int | None = None) -> dict:
        if period not in PERIOD_SESSIONS:
            raise ValueError(f"period must be one of {', '.join(PERIOD_SESSIONS)}")
        query = (
            select(Stock)
            .join(WatchlistStock, WatchlistStock.stock_id == Stock.stock_id)
            .where(Stock.active.is_(True), WatchlistStock.analysis_enabled.is_(True))
            .distinct()
        )
        if watchlist_id is not None:
            query = query.where(WatchlistStock.watchlist_id == watchlist_id)
        stocks = [s for s in db.scalars(query).all() if not is_indian_exchange(s.exchange)]

        need = PERIOD_SESSIONS[period] + 2
        rows = []
        as_of = None
        for stock in stocks:
            latest = db.scalar(
                select(MarketCandle)
                .where(MarketCandle.stock_id == stock.stock_id, MarketCandle.timeframe == "15Min")
                .order_by(MarketCandle.candle_time.desc()).limit(1)
            ) or db.scalar(
                select(MarketCandle)
                .where(MarketCandle.stock_id == stock.stock_id, MarketCandle.timeframe == "1Day")
                .order_by(MarketCandle.candle_time.desc()).limit(1)
            )
            if latest is None:
                continue
            latest_time = _utc(latest.candle_time)
            session_day = latest_time.astimezone(ET).date()
            day_start_utc = datetime(session_day.year, session_day.month, session_day.day,
                                     tzinfo=ET).astimezone(timezone.utc)
            prior = db.scalars(
                select(MarketCandle.close_price)
                .where(MarketCandle.stock_id == stock.stock_id,
                       MarketCandle.timeframe == "1Day",
                       MarketCandle.candle_time < day_start_utc)
                .order_by(MarketCandle.candle_time.desc()).limit(need)
            ).all()
            last = float(latest.close_price)
            ref = reference_close([float(p) for p in prior], period)
            symbol = stock.symbol.strip().upper()
            rows.append({
                "symbol": symbol,
                "company_name": stock.company_name,
                "sector": sector_for(symbol, stock.sector),
                "price": round(last, 2),
                "reference_price": round(ref, 2) if ref else None,
                "change_pct": change_pct(last, ref),
                "as_of": latest_time,
            })
            as_of = max(as_of, latest_time) if as_of else latest_time

        return {"period": period, "as_of": as_of, "stocks": len(rows),
                "sectors": group_by_sector(rows)}

    # ------------------------------------------------------------- P&L
    @staticmethod
    def pnl_report(group: str = "day", range_key: str = "3M") -> dict:
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest, GetPortfolioHistoryRequest

        from app.brokers.alpaca.trading_client import AlpacaPaperTradingClient

        if group not in ("day", "week", "month"):
            raise ValueError("group must be day, week or month")
        if range_key not in PNL_RANGES:
            raise ValueError(f"range must be one of {', '.join(PNL_RANGES)}")

        client = AlpacaPaperTradingClient()
        start = datetime.now(timezone.utc) - timedelta(days=PNL_RANGES[range_key])

        # Account equity per day (includes open positions' value changes).
        history = client.client.get_portfolio_history(
            GetPortfolioHistoryRequest(period=range_key, timeframe="1D")
        )
        equity_points = []
        for ts, equity in zip(history.timestamp or [], history.equity or []):
            if equity is None:
                continue
            equity_points.append((datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(ET).date(),
                                  float(equity)))

        # Closed trades from filled orders (FIFO), including bracket legs.
        orders = client.client.get_orders(filter=GetOrdersRequest(
            status=QueryOrderStatus.CLOSED, after=start, limit=500, nested=False,
        ))
        fills = []
        for order in orders:
            qty = float(order.filled_qty or 0)
            if qty <= 0 or not order.filled_avg_price or not order.filled_at:
                continue
            side = str(order.side.value if hasattr(order.side, "value") else order.side).lower()
            fills.append(Fill(str(order.symbol).upper(), side, qty,
                              float(order.filled_avg_price), _utc(order.filled_at)))
        trades = round_trips(fills)

        buckets = aggregate_pnl(
            equity_points, float(history.base_value) if history.base_value else None,
            trades, group, lambda t: _utc(t).astimezone(ET).date(),
        )

        positions = []
        for p in client.get_open_positions():
            positions.append({
                "symbol": str(p.symbol), "qty": float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price) if p.current_price else None,
                "unrealized_pnl": float(p.unrealized_pl) if p.unrealized_pl else 0.0,
                "unrealized_pnl_pct": round(float(p.unrealized_plpc or 0) * 100, 2),
            })

        realized = round(sum(t["pnl"] for t in trades), 2)
        wins = sum(1 for t in trades if t["pnl"] > 0)
        return {
            "group": group,
            "range": range_key,
            "totals": {
                "account_pnl": round(sum(b["account_pnl"] for b in buckets), 2),
                "realized_pnl": realized,
                "unrealized_pnl": round(sum(p["unrealized_pnl"] for p in positions), 2),
                "trades": len(trades),
                "wins": wins,
                "losses": sum(1 for t in trades if t["pnl"] < 0),
                "win_rate": round(wins / len(trades) * 100, 1) if trades else None,
                "end_equity": equity_points[-1][1] if equity_points else None,
            },
            "buckets": buckets,
            "trades": sorted(trades, key=lambda t: t["exit_time"], reverse=True),
            "open_positions": positions,
            "orders_capped": len(orders) >= 500,
        }
