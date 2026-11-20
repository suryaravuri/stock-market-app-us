"""Store and list alerts (early-breakout watcher and TradingView webhooks)."""
from __future__ import annotations

import hmac
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.market_alert import MarketAlert


def webhook_secret_ok(provided: str | None, expected: str | None) -> bool:
    """Constant-time comparison; an unset expected secret never matches."""
    if not expected or not provided:
        return False
    return hmac.compare_digest(str(provided), str(expected))


def normalize_tradingview_symbol(raw: str) -> str:
    """'NASDAQ:AAPL' or 'aapl' -> 'AAPL'; NSE tickers get the app's .NS suffix."""
    value = raw.strip().upper()
    exchange, _, ticker = value.rpartition(":")
    if exchange == "NSE":
        return f"{ticker}.NS"
    if exchange == "BSE":
        return f"{ticker}.BO"
    return ticker


class MarketAlertService:

    @staticmethod
    def record(
        db: Session,
        *,
        source: str,
        symbol: str,
        message: str,
        candle_start: datetime | None = None,
        price: float | None = None,
        level: float | None = None,
        volume_ratio: float | None = None,
        payload: dict | None = None,
    ) -> bool:
        """Insert an alert. Returns False if it was a duplicate (same source,
        symbol and candle)."""
        stmt = (
            insert(MarketAlert)
            .values(
                source=source,
                symbol=symbol,
                candle_start=candle_start,
                price=price,
                level=level,
                volume_ratio=volume_ratio,
                message=message,
                payload=payload,
            )
            .on_conflict_do_nothing(constraint="uq_market_alert_candle")
            .returning(MarketAlert.id)
        )
        inserted = db.execute(stmt).first() is not None
        db.commit()
        return inserted

    @staticmethod
    def record_tradingview(db: Session, body: dict) -> dict:
        if not settings.tradingview_webhook_secret:
            raise PermissionError("TradingView webhook is disabled (TRADINGVIEW_WEBHOOK_SECRET not set)")
        if not webhook_secret_ok(body.get("secret"), settings.tradingview_webhook_secret):
            raise PermissionError("Invalid webhook secret")

        raw_symbol = str(body.get("symbol") or body.get("ticker") or "").strip()
        if not raw_symbol:
            raise ValueError("symbol is required")

        price = body.get("price")
        try:
            price = float(price) if price not in (None, "") else None
        except (TypeError, ValueError):
            price = None

        payload = {k: v for k, v in body.items() if k != "secret"}   # never store the secret
        MarketAlertService.record(
            db,
            source="TRADINGVIEW",
            symbol=normalize_tradingview_symbol(raw_symbol),
            message=str(body.get("message") or "TradingView alert")[:2000],
            price=price,
            payload=payload,
        )
        return {"ok": True}

    @staticmethod
    def list(db: Session, limit: int = 50, source: str | None = None) -> list[dict]:
        stmt = select(MarketAlert).order_by(MarketAlert.created_at.desc()).limit(limit)
        if source:
            stmt = stmt.where(MarketAlert.source == source.upper())
        return [
            {
                "id": a.id,
                "created_at": a.created_at,
                "source": a.source,
                "symbol": a.symbol,
                "candle_start": a.candle_start,
                "price": a.price,
                "level": a.level,
                "volume_ratio": a.volume_ratio,
                "message": a.message,
                "payload": a.payload,
            }
            for a in db.scalars(stmt).all()
        ]
