"""Manual, real-money Zerodha orders with layered safety checks.

Order of checks for every placement:
  1. ZERODHA_TRADING_ENABLED master switch
  2. User is on ZERODHA_ALLOWED_USER_EMAILS
  3. User has a valid (today's) Zerodha login
  4. Pure rules: session hours, LIMIT price vs LTP, per-order value,
     per-day count, duplicate open order, no short selling
  5. ZERODHA_DRY_RUN: record but do not send

Every attempt, including rejections, is written to the zerodha_order table.
This service is NOT wired to the automatic strategy. Analysis of NSE/BSE
stocks is session-aware, but automatic real-money execution is a separate,
deliberate step that has not been enabled.
"""
from __future__ import annotations

from datetime import datetime, timezone

from kiteconnect import exceptions as kite_exceptions
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings, zerodha_allowed_emails
from app.market.sessions import broker_symbol
from app.models.user import AppUser
from app.models.zerodha import ZerodhaOrder, ZerodhaSession
from app.services.zerodha_auth_service import ZerodhaAuthService
from app.trading.zerodha_order_rules import (
    OPEN_ORDER_STATUSES,
    ist_day_bounds,
    validate_order,
)


class ZerodhaOrderService:

    @staticmethod
    def _normalise(req: dict) -> dict:
        return {
            "exchange": req["exchange"].strip().upper(),
            # Accept app symbols too: RELIANCE.NS -> RELIANCE
            "tradingsymbol": broker_symbol(req["tradingsymbol"]),
            "side": req["side"].strip().upper(),
            "product": req.get("product", "CNC").strip().upper(),
            "quantity": int(req["quantity"]),
            "limit_price": round(float(req["limit_price"]), 2),
        }

    @staticmethod
    def _access_reasons(user: AppUser) -> list[str]:
        reasons: list[str] = []
        if not settings.zerodha_trading_enabled:
            reasons.append("Zerodha trading is disabled (ZERODHA_TRADING_ENABLED=false)")
        if user.email.lower() not in zerodha_allowed_emails(settings.zerodha_allowed_user_emails):
            reasons.append("This user is not allowed to place Zerodha orders")
        return reasons

    @staticmethod
    def _orders_today(db: Session, user: AppUser, now: datetime) -> int:
        start, end = ist_day_bounds(now)
        return db.scalar(
            select(func.count(ZerodhaOrder.id)).where(
                ZerodhaOrder.user_id == user.id,
                ZerodhaOrder.status.in_(("SUBMITTED", "DRY_RUN", "UNKNOWN")),
                ZerodhaOrder.created_at >= start,
                ZerodhaOrder.created_at < end,
            )
        ) or 0

    @staticmethod
    def _evaluate(db: Session, user: AppUser, order: dict, now: datetime):
        client, session = ZerodhaAuthService.client_for(db, user)

        last_price = client.last_price(order["exchange"], order["tradingsymbol"])

        has_open = any(
            o.get("tradingsymbol") == order["tradingsymbol"]
            and o.get("exchange") == order["exchange"]
            and o.get("transaction_type") == order["side"]
            and str(o.get("status", "")).upper() in OPEN_ORDER_STATUSES
            for o in client.orders()
        )

        sellable = (
            client.sellable_quantity(order["exchange"], order["tradingsymbol"], order["product"])
            if order["side"] == "SELL"
            else 0
        )

        rules = validate_order(
            exchange=order["exchange"],
            side=order["side"],
            product=order["product"],
            quantity=order["quantity"],
            limit_price=order["limit_price"],
            last_price=last_price,
            now=now,
            max_order_value=settings.zerodha_max_order_value_inr,
            max_price_deviation_percent=settings.zerodha_max_price_deviation_percent,
            orders_placed_today=ZerodhaOrderService._orders_today(db, user, now),
            max_orders_per_day=settings.zerodha_max_orders_per_day,
            has_open_order_same_side=has_open,
            sellable_quantity=sellable,
        )
        return client, session, last_price, rules

    @staticmethod
    def preview(db: Session, user: AppUser, req: dict) -> dict:
        order = ZerodhaOrderService._normalise(req)
        now = datetime.now(timezone.utc)
        reasons = ZerodhaOrderService._access_reasons(user)
        last_price = None
        if not reasons:
            _, _, last_price, rules = ZerodhaOrderService._evaluate(db, user, order, now)
            reasons = rules.reasons
        return {
            **order,
            "last_price": last_price,
            "order_value": round(order["quantity"] * order["limit_price"], 2),
            "allowed": not reasons,
            "dry_run": settings.zerodha_dry_run,
            "reasons": reasons,
        }

    @staticmethod
    def place(db: Session, user: AppUser, req: dict) -> dict:
        order = ZerodhaOrderService._normalise(req)
        now = datetime.now(timezone.utc)

        access_reasons = ZerodhaOrderService._access_reasons(user)
        if access_reasons:
            return ZerodhaOrderService._record(db, user, order, None, None, "REJECTED", access_reasons)

        # Serialise placements per user so the daily limit cannot be raced.
        db.scalar(
            select(ZerodhaSession)
            .where(ZerodhaSession.user_id == user.id)
            .with_for_update()
        )

        client, session, last_price, rules = ZerodhaOrderService._evaluate(db, user, order, now)
        if not rules.allowed:
            return ZerodhaOrderService._record(
                db, user, order, session.kite_user_id, last_price, "REJECTED", rules.reasons
            )

        if settings.zerodha_dry_run:
            return ZerodhaOrderService._record(
                db, user, order, session.kite_user_id, last_price, "DRY_RUN",
                ["Dry run: all checks passed, order NOT sent to Zerodha"],
            )

        row = ZerodhaOrder(
            user_id=user.id,
            kite_user_id=session.kite_user_id,
            exchange=order["exchange"],
            tradingsymbol=order["tradingsymbol"],
            side=order["side"],
            product=order["product"],
            order_type="LIMIT",
            quantity=order["quantity"],
            limit_price=order["limit_price"],
            last_price=last_price,
            status="SENDING",
        )
        db.add(row)
        db.flush()

        try:
            kite_order_id = client.place_limit_order(
                exchange=order["exchange"],
                tradingsymbol=order["tradingsymbol"],
                side=order["side"],
                quantity=order["quantity"],
                price=order["limit_price"],
                product=order["product"],
                tag=f"smapp{row.id}"[:20],
            )
            row.status = "SUBMITTED"
            row.kite_order_id = str(kite_order_id)
        except kite_exceptions.NetworkException as exc:
            # The order may or may not have reached the exchange.
            row.status = "UNKNOWN"
            row.reasons = f"Network error, check the Kite order book before retrying: {exc}"
        except kite_exceptions.KiteException as exc:
            row.status = "FAILED"
            row.reasons = str(exc)
        except Exception as exc:  # e.g. connection reset mid-request
            row.status = "UNKNOWN"
            row.reasons = f"Unexpected error, check the Kite order book before retrying: {exc}"

        db.commit()
        db.refresh(row)
        return ZerodhaOrderService.serialize(row)

    @staticmethod
    def _record(db, user, order, kite_user_id, last_price, status, reasons) -> dict:
        row = ZerodhaOrder(
            user_id=user.id,
            kite_user_id=kite_user_id,
            exchange=order["exchange"],
            tradingsymbol=order["tradingsymbol"],
            side=order["side"],
            product=order["product"],
            order_type="LIMIT",
            quantity=order["quantity"],
            limit_price=order["limit_price"],
            last_price=last_price,
            status=status,
            reasons="; ".join(reasons),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return ZerodhaOrderService.serialize(row)

    @staticmethod
    def cancel(db: Session, user: AppUser, kite_order_id: str) -> dict:
        row = db.scalar(
            select(ZerodhaOrder).where(
                ZerodhaOrder.user_id == user.id,
                ZerodhaOrder.kite_order_id == kite_order_id,
            )
        )
        if row is None:
            raise ValueError(f"Order {kite_order_id} not found for this user")
        client, _ = ZerodhaAuthService.client_for(db, user)
        client.cancel_order(kite_order_id)
        row.status = "CANCEL_REQUESTED"
        db.commit()
        db.refresh(row)
        return ZerodhaOrderService.serialize(row)

    @staticmethod
    def history(db: Session, user: AppUser, limit: int = 50) -> list[dict]:
        rows = db.scalars(
            select(ZerodhaOrder)
            .where(ZerodhaOrder.user_id == user.id)
            .order_by(ZerodhaOrder.created_at.desc())
            .limit(limit)
        ).all()
        return [ZerodhaOrderService.serialize(r) for r in rows]

    @staticmethod
    def serialize(row: ZerodhaOrder) -> dict:
        return {
            "id": row.id,
            "kite_order_id": row.kite_order_id,
            "status": row.status,
            "exchange": row.exchange,
            "tradingsymbol": row.tradingsymbol,
            "side": row.side,
            "product": row.product,
            "order_type": row.order_type,
            "quantity": row.quantity,
            "limit_price": float(row.limit_price),
            "last_price": float(row.last_price) if row.last_price is not None else None,
            "reasons": row.reasons.split("; ") if row.reasons else [],
            "kite_status": row.kite_status,
            "kite_status_message": row.kite_status_message,
            "filled_quantity": row.filled_quantity,
            "average_price": float(row.average_price) if row.average_price is not None else None,
            "created_at": row.created_at,
        }
