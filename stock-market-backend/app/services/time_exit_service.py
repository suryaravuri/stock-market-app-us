"""Closes automatic paper positions whose holding period is over.

Runs inside the trading cycle (US market only, because automatic orders go
to Alpaca). For every OPEN auto_trade row:

  * position already gone at the broker  -> mark CLOSED / BROKER_EXIT
    (stop loss, take profit or trailing stop was hit there)
  * holding deadline reached             -> cancel the bracket legs and
    market-sell the position (SESSION_CLOSE for INTRADAY, TIME_EXIT otherwise)

Exits are only sent while the regular session is open, so a market order
can never be queued overnight and fill at the next day's open.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brokers.alpaca.trading_client import AlpacaPaperTradingClient
from app.market.sessions import US_SESSION
from app.models.auto_trade import AutoTrade
from app.trading.holding_style import exit_reason_for

logger = logging.getLogger(__name__)

# A just-submitted buy may not be filled yet; don't call it "closed" too early.
_FILL_GRACE = timedelta(minutes=30)


class TimeExitService:

    @staticmethod
    def _close_row(row: AutoTrade, reason: str, note: str, now: datetime) -> None:
        row.status = "CLOSED"
        row.exit_reason = reason
        row.exit_note = note
        row.closed_at = now

    @classmethod
    def sync(cls, db: Session, *, now: datetime | None = None, dry_run: bool = False) -> dict:
        now = now or datetime.now(timezone.utc)
        rows = db.scalars(
            select(AutoTrade).where(
                AutoTrade.status == "OPEN",
                AutoTrade.broker == "ALPACA_PAPER",
            )
        ).all()
        if not rows:
            return {"checked": 0, "closed_by_broker": 0, "time_exits": 0, "results": []}

        session_open = US_SESSION.is_session_day(
            now.astimezone(US_SESSION.tz).date()
        ) and US_SESSION.is_regular(now)

        client = AlpacaPaperTradingClient()
        results: list[dict] = []
        closed_by_broker = time_exits = 0

        from app.services.holdings_guard_service import is_guarded

        for row in rows:
            if is_guarded(row.symbol):
                continue  # a guarded holding is never time-exited
            item = {
                "id": row.id,
                "symbol": row.symbol,
                "holding_style": row.holding_style,
                "exit_deadline": row.exit_deadline,
            }
            try:
                qty = client.get_position_quantity(row.symbol)

                if qty <= 0:
                    pending_buy = client.has_open_buy_order(row.symbol)
                    if pending_buy or now - row.submitted_at < _FILL_GRACE:
                        item["action"] = "WAITING_FOR_FILL"
                    else:
                        if not dry_run:
                            cls._close_row(row, "BROKER_EXIT", "Position no longer open at broker", now)
                        closed_by_broker += 1
                        item["action"] = "MARKED_CLOSED_BY_BROKER"
                    results.append(item)
                    continue

                if row.exit_deadline is None or now < row.exit_deadline:
                    item["action"] = "HOLD"
                    results.append(item)
                    continue

                if not session_open:
                    item["action"] = "DEADLINE_PASSED_MARKET_CLOSED"
                    results.append(item)
                    continue

                reason = exit_reason_for(row.holding_style)
                if not dry_run:
                    cancelled = client.cancel_open_orders(row.symbol)
                    try:
                        client.close_position(row.symbol)
                    except Exception as exc:  # noqa: BLE001
                        # Bracket legs can take a moment to cancel and still hold
                        # the shares; the next cycle retries the close.
                        logger.warning("Close %s failed, will retry: %s", row.symbol, exc)
                        item["action"] = "CLOSE_RETRY_NEXT_CYCLE"
                        item["cancelled_orders"] = cancelled
                        item["error"] = f"{type(exc).__name__}: {exc}"
                        results.append(item)
                        continue
                    cls._close_row(row, reason, f"Holding period ended ({row.holding_style})", now)
                time_exits += 1
                item["action"] = reason
                results.append(item)

            except Exception as exc:  # noqa: BLE001 - keep other symbols going
                logger.exception("Time exit check failed for %s", row.symbol)
                item["action"] = "ERROR"
                item["error"] = f"{type(exc).__name__}: {exc}"
                results.append(item)

        if not dry_run:
            db.commit()

        return {
            "checked": len(rows),
            "closed_by_broker": closed_by_broker,
            "time_exits": time_exits,
            "dry_run": dry_run,
            "results": results,
        }
