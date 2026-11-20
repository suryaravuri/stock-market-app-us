"""Trades & P&L statistics for Zerodha orders.

LIVE mode    - real fills copied from Kite's trade book into zerodha_trade.
DRY_RUN mode - simulated fills: every DRY_RUN order is assumed to have filled
               completely at its limit price at the moment it was recorded.

Kite's API only exposes TODAY's orders and trades, so fills must be synced
the same day (any time before the next morning's token reset). Syncing runs
automatically whenever the LIVE statistics are opened while Zerodha is
connected, and on demand via POST /zerodha/trades/sync.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.user import AppUser
from app.models.zerodha import ZerodhaOrder, ZerodhaTrade
from app.services.zerodha_auth_service import ZerodhaAuthService
from app.services.zerodha_order_service import ZerodhaOrderService
from app.trading.pnl import IST, Fill, apply_last_prices, compute_fifo, summarize

MODES = ("LIVE", "DRY_RUN")

CHARGES_NOTE = (
    "Gross P&L: brokerage, STT, exchange charges, GST and stamp duty are not deducted."
)
DRY_RUN_NOTE = (
    "Simulated: assumes every dry-run LIMIT order filled completely at its limit price."
)


def _as_ist_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=IST) if value.tzinfo is None else value


class ZerodhaStatisticsService:

    # ------------------------------------------------------------------ sync

    @staticmethod
    def sync(db: Session, user: AppUser) -> dict:
        client, session = ZerodhaAuthService.client_for(db, user)

        trades = client.trades()
        rows = []
        for trade in trades:
            fill_time = _as_ist_aware(
                trade.get("fill_timestamp")
                or trade.get("exchange_timestamp")
                or trade.get("order_timestamp")
            )
            if fill_time is None or not trade.get("trade_id"):
                continue
            rows.append(
                {
                    "user_id": user.id,
                    "kite_user_id": session.kite_user_id,
                    "kite_trade_id": str(trade["trade_id"]),
                    "kite_order_id": str(trade["order_id"]),
                    "exchange": trade["exchange"],
                    "tradingsymbol": trade["tradingsymbol"],
                    "side": trade["transaction_type"],
                    "product": trade["product"],
                    "quantity": int(trade["quantity"]),
                    "price": float(trade["average_price"]),
                    "fill_time": fill_time,
                }
            )

        inserted = 0
        if rows:
            stmt = (
                insert(ZerodhaTrade)
                .values(rows)
                .on_conflict_do_nothing(constraint="uq_zerodha_trade_user_trade")
                .returning(ZerodhaTrade.id)
            )
            inserted = len(db.execute(stmt).all())

        broker_orders = {str(o["order_id"]): o for o in client.orders()}
        updated = 0
        if broker_orders:
            ours = db.scalars(
                select(ZerodhaOrder).where(
                    ZerodhaOrder.user_id == user.id,
                    ZerodhaOrder.kite_order_id.in_(list(broker_orders)),
                )
            ).all()
            for row in ours:
                order = broker_orders[row.kite_order_id]
                row.kite_status = order.get("status")
                row.kite_status_message = order.get("status_message")
                row.filled_quantity = order.get("filled_quantity")
                row.average_price = order.get("average_price") or None
                updated += 1

        db.commit()
        return {
            "trades_seen": len(trades),
            "trades_new": inserted,
            "orders_updated": updated,
            "synced_at": datetime.now(timezone.utc),
            "error": None,
        }

    # ------------------------------------------------------------ statistics

    @staticmethod
    def _live_fills(db: Session, user: AppUser) -> list[Fill]:
        rows = db.scalars(select(ZerodhaTrade).where(ZerodhaTrade.user_id == user.id)).all()
        return [
            Fill(
                exchange=r.exchange,
                tradingsymbol=r.tradingsymbol,
                product=r.product,
                side=r.side,
                quantity=r.quantity,
                price=float(r.price),
                timestamp=r.fill_time,
                ref=r.kite_trade_id,
            )
            for r in rows
        ]

    @staticmethod
    def _dry_run_fills(db: Session, user: AppUser) -> list[Fill]:
        rows = db.scalars(
            select(ZerodhaOrder).where(
                ZerodhaOrder.user_id == user.id,
                ZerodhaOrder.status == "DRY_RUN",
            )
        ).all()
        return [
            Fill(
                exchange=r.exchange,
                tradingsymbol=r.tradingsymbol,
                product=r.product,
                side=r.side,
                quantity=r.quantity,
                price=float(r.limit_price),
                timestamp=r.created_at,
                ref=str(r.id),
            )
            for r in rows
        ]

    @staticmethod
    def statistics(db: Session, user: AppUser, mode: str = "LIVE") -> dict:
        mode = mode.upper()
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")

        connected = ZerodhaAuthService.get_active_session(db, user) is not None
        client = None
        sync_info = None

        if connected:
            client, _ = ZerodhaAuthService.client_for(db, user)
            if mode == "LIVE":
                try:
                    sync_info = ZerodhaStatisticsService.sync(db, user)
                except Exception as exc:  # stats still render from stored fills
                    db.rollback()
                    sync_info = {"error": f"Trade sync failed: {exc}"}

        fills = (
            ZerodhaStatisticsService._live_fills(db, user)
            if mode == "LIVE"
            else ZerodhaStatisticsService._dry_run_fills(db, user)
        )
        result = compute_fifo(fills)

        prices_error = None
        if client is not None and result.open_positions:
            keys = sorted({f"{p.exchange}:{p.tradingsymbol}" for p in result.open_positions})
            try:
                apply_last_prices(result.open_positions, client.last_prices(keys))
            except Exception as exc:
                prices_error = f"Live prices unavailable: {exc}"

        orders = db.scalars(
            select(ZerodhaOrder)
            .where(ZerodhaOrder.user_id == user.id)
            .order_by(ZerodhaOrder.created_at.desc())
        ).all()
        if mode == "LIVE":
            mode_orders = [o for o in orders if o.status != "DRY_RUN"]
        else:
            mode_orders = [o for o in orders if o.status == "DRY_RUN"]

        closed = sorted(result.closed, key=lambda t: t.closed_at, reverse=True)

        return {
            "mode": mode,
            "zerodha_connected": connected,
            "tracking_since": min((f.timestamp for f in fills), default=None),
            "notes": [CHARGES_NOTE] + ([DRY_RUN_NOTE] if mode == "DRY_RUN" else []),
            "sync": sync_info,
            "prices_error": prices_error,
            "summary": summarize(result),
            "order_counts": dict(Counter(o.status for o in orders)),
            "closed_trades": [asdict(t) for t in closed[:100]],
            "open_positions": [asdict(p) for p in result.open_positions],
            "unmatched_sells": [asdict(u) for u in result.unmatched_sells],
            "recent_orders": [ZerodhaOrderService.serialize(o) for o in mode_orders[:25]],
        }
