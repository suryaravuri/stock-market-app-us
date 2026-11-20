"""Broker-side profit protection.

For every open Alpaca paper position:
  * work out a proportional trailing stop (app/risk/trailing_stop.py),
  * raise the real stop order at Alpaca when price has moved up.

The stop is only ever raised, never lowered. The take-profit leg of a
bracket order is left untouched, so the 20% target still works.
"""
from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.brokers.alpaca.trading_client import AlpacaPaperTradingClient
from app.core.config import settings
from app.models.auto_trade import AutoTrade
from app.models.stock import Stock
from app.models.watchlist import WatchlistStock
from app.risk.trailing_stop import compute_trailing_stop

logger = logging.getLogger(__name__)


class TrailingStopService:

    @staticmethod
    def _trading_allowed() -> str | None:
        if not settings.trailing_stop_enabled:
            return "TRAILING_STOP_DISABLED"
        if not settings.trading_enabled or not settings.paper_trading_enabled:
            return "PAPER_TRADING_DISABLED"
        if settings.live_trading_enabled:
            return "LIVE_TRADING_MUST_BE_DISABLED"
        return None

    @staticmethod
    def _trail_percent(db: Session, symbol: str) -> float:
        """User's per-stock loss limit drives the trail distance.

        Preferred: the setting of the watchlist that actually OPENED this
        position (snapshotted on its auto_trade row), so one user's settings
        never move another user's stop. Fallback for positions opened
        manually or before auto_trade existed: the tightest loss limit of
        any watchlist holding the symbol."""
        opened_with = db.execute(
            select(AutoTrade.trail_percent)
            .where(
                AutoTrade.symbol == symbol,
                AutoTrade.status == "OPEN",
                AutoTrade.trail_percent.is_not(None),
            )
            .order_by(AutoTrade.submitted_at.desc())
            .limit(1)
        ).scalar()
        if opened_with is not None and 0 < float(opened_with) < 100:
            return float(opened_with)

        value = db.execute(
            select(func.min(WatchlistStock.loss_limit_percent))
            .join(Stock, Stock.stock_id == WatchlistStock.stock_id)
            .where(func.upper(Stock.symbol) == symbol)
        ).scalar()
        if value is not None and 0 < float(value) < 100:
            return float(value)
        return settings.trailing_stop_percent

    @classmethod
    def sync(cls, db: Session, *, dry_run: bool = False) -> dict:
        blocked = cls._trading_allowed()
        if blocked:
            return {"ran": False, "reason": blocked, "positions": []}

        client = AlpacaPaperTradingClient()
        results: list[dict] = []

        for position in client.get_open_positions():
            symbol = str(position.symbol).upper()
            try:
                results.append(
                    cls._sync_position(db, client, position, symbol, dry_run)
                )
            except Exception as exc:  # noqa: BLE001 - keep other symbols going
                logger.exception("Trailing stop failed for %s", symbol)
                results.append({
                    "symbol": symbol,
                    "action": "ERROR",
                    "reason": f"{type(exc).__name__}: {exc}",
                })

        return {
            "ran": True,
            "dry_run": dry_run,
            "positions_checked": len(results),
            "stops_raised": sum(r.get("action") == "STOP_RAISED" for r in results),
            "stops_created": sum(r.get("action") == "STOP_CREATED" for r in results),
            "positions": results,
        }

    @classmethod
    def _sync_position(cls, db, client, position, symbol, dry_run) -> dict:
        from app.services.holdings_guard_service import is_guarded

        if is_guarded(symbol):
            return {"symbol": symbol, "action": "SKIPPED", "reason": "MANAGED_BY_HOLDINGS_GUARD"}
        qty = float(position.qty)
        if qty <= 0:
            # This bot is long-only; never touch shorts.
            return {"symbol": symbol, "action": "SKIPPED", "reason": "NOT_LONG"}

        entry = float(position.avg_entry_price)
        price = float(position.current_price)
        trail = cls._trail_percent(db, symbol)

        stops = client.get_open_sell_stop_orders(symbol)
        current_stop = max((float(o.stop_price) for o in stops), default=None)

        decision = compute_trailing_stop(
            entry_price=entry,
            current_price=price,
            current_stop=current_stop,
            trail_percent=trail,
            activation_percent=settings.trailing_activation_percent,
            breakeven_percent=settings.trailing_breakeven_percent,
            min_step_percent=settings.trailing_min_step_percent,
        )

        base = {
            "symbol": symbol,
            "qty": qty,
            "entry_price": entry,
            "current_price": price,
            "gain_percent": round(decision.gain_percent, 2),
            "trail_percent": trail,
            "current_stop": current_stop,
            "new_stop": decision.new_stop,
            "reason": decision.reason,
        }

        if not stops:
            # Unprotected position (e.g. bought before bracket orders existed).
            # Only add a stop if no other sell order already holds the shares.
            if client.get_open_sell_orders(symbol):
                return {**base, "action": "SKIPPED",
                        "reason": "NO_STOP_BUT_OTHER_SELL_ORDER_OPEN"}

            stop = decision.new_stop or round(entry * (1 - trail / 100), 2)
            stop = min(stop, round(price - 0.01, 2))
            if not dry_run:
                client.submit_stop_sell(symbol, int(qty), stop)
            return {**base, "new_stop": stop, "action": "STOP_CREATED"}

        if not decision.should_update:
            return {**base, "action": "NO_CHANGE"}

        if not dry_run:
            # Normally one stop (the bracket leg); raise every open one.
            for order in stops:
                client.replace_stop_price(order.id, decision.new_stop)

        return {**base, "action": "STOP_RAISED"}
