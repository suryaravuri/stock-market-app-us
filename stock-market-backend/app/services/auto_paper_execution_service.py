import logging
import threading
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.market.sessions import is_indian_exchange, session_for_stock
from app.models.auto_trade import AutoTrade
from app.services.paper_trading_service import PaperTradingService
from app.trading.holding_style import (
    HoldingStyle,
    exit_deadline,
    intraday_entry_allowed,
    parse_style,
)

from app.services.market_guard_service import market_mood, sector_check  # noqa: E402

logger = logging.getLogger(__name__)


def regular_session_open(session, now: datetime) -> bool:
    """True between the open and the real close (holidays and half days
    come from the exchange calendar)."""
    local = session.local(now)
    day = local.date()
    if not session.is_session_day(day):
        return False
    close = session.close_time_on(day) if hasattr(session, "close_time_on") else session.close
    return session.open <= local.time().replace(tzinfo=None) < close

# The 15-minute cycle and the live 1-minute stream run in different threads
# of the same process; this keeps "check daily limit -> submit -> record"
# atomic so they can't both buy the same stock at the same moment.
ORDER_LOCK = threading.Lock()


class AutoPaperExecutionService:
    """
    Automatic STOCK paper-trading execution bridge.

    This service must never submit a LIVE order.
    It is invoked only by an intentional automated workflow after
    SetupService has completed signal/setup evaluation.
    """

    @staticmethod
    def _skip(symbol: str, reason: str) -> dict:
        return {
            "attempted": False,
            "submitted": False,
            "symbol": symbol,
            "mode": "PAPER",
            "reason": reason,
        }

    @staticmethod
    def process_entry(
        *,
        db: Session,
        symbol: str,
        setup: dict,
        current_daily_pnl: float = 0.0,
        max_daily_loss_percent: float = 2.0,
        watchlist_stock=None,
        stock=None,
        user_id: int | None = None,
        now: datetime | None = None,
    ) -> dict:

        symbol = symbol.strip().upper()

        # Holdings managed by the Holdings Guard are bought/sold only by it.
        from app.services.holdings_guard_service import is_guarded

        if is_guarded(symbol):
            return AutoPaperExecutionService._skip(symbol, "MANAGED_BY_HOLDINGS_GUARD")
        skip = AutoPaperExecutionService._skip

        # 1. Automatic execution master switch
        if not settings.auto_trading_enabled:
            return skip(symbol, "AUTO_TRADING_DISABLED")

        # 2. Paper trading must explicitly be enabled
        if not settings.paper_trading_enabled:
            return skip(symbol, "PAPER_TRADING_DISABLED")

        # 3. Fail closed if LIVE trading is enabled.
        if settings.live_trading_enabled:
            return skip(symbol, "LIVE_TRADING_MUST_BE_DISABLED")

        # 4. Signal must have reached ENTRY_CONFIRMED
        lifecycle = setup.get("signal_lifecycle") or {}
        signal_state = str(lifecycle.get("state") or "").upper()

        if signal_state != "ENTRY_CONFIRMED":
            return skip(
                symbol,
                f"SIGNAL_NOT_ENTRY_CONFIRMED:{signal_state or 'UNKNOWN'}",
            )

        # 5. Strategy must independently mark setup actionable
        if not bool(setup.get("actionable")):
            return skip(symbol, "SETUP_NOT_ACTIONABLE")

        # 5a. The user must have enabled trading for this stock.
        if watchlist_stock is not None and not watchlist_stock.trading_enabled:
            return skip(symbol, "TRADING_NOT_ENABLED_FOR_STOCK")

        # 5b. Automatic paper orders go to Alpaca, which only has US stocks.
        if stock is not None and is_indian_exchange(stock.exchange):
            return skip(symbol, "AUTO_TRADING_US_ONLY")

        now = now or datetime.now(timezone.utc)
        style = parse_style(
            getattr(watchlist_stock, "holding_style", None) if watchlist_stock else None
        )
        session = session_for_stock(stock) if stock is not None else None

        # 5b2. New entries only during regular hours. The cycle keeps running
        #      20 minutes after the close to process the last candle, but a
        #      market order sent then would fill at the NEXT morning's open
        #      (AVGO signal at 4:16 PM ET on 2026-11-17).
        if session is not None and not regular_session_open(session, now):
            return skip(symbol, "MARKET_CLOSED_NO_NEW_ENTRIES")

        # 5c. No new INTRADAY entries close to the close.
        if style is HoldingStyle.INTRADAY and session is not None:
            if not intraday_entry_allowed(now, session, settings.intraday_entry_cutoff_minutes):
                return skip(symbol, "TOO_LATE_FOR_INTRADAY_ENTRY")

        with ORDER_LOCK:
            return AutoPaperExecutionService._limited_submit(
                db=db, symbol=symbol, setup=setup, session=session, style=style, now=now,
                current_daily_pnl=current_daily_pnl,
                max_daily_loss_percent=max_daily_loss_percent,
                watchlist_stock=watchlist_stock, stock=stock, user_id=user_id,
            )

    @staticmethod
    def _limited_submit(*, db, symbol, setup, session, style, now, current_daily_pnl,
                        max_daily_loss_percent, watchlist_stock, stock, user_id) -> dict:
        skip = AutoPaperExecutionService._skip

        # 5d. Limit automatic entries per stock per day. Stops the bot from
        #     re-buying a support it was just stopped out of (NXPI 2026-11-16).
        limit = int(getattr(settings, "max_auto_entries_per_symbol_per_day", 0) or 0)
        if limit > 0 and session is not None:
            local_now = session.local(now)
            day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
            entries_today = db.scalar(
                select(func.count(AutoTrade.id)).where(
                    AutoTrade.symbol == symbol,
                    AutoTrade.submitted_at >= day_start.astimezone(timezone.utc),
                )
            ) or 0
            if entries_today >= limit:
                return skip(symbol, f"MAX_ENTRIES_PER_DAY_REACHED:{entries_today}")

        # 5e. Broad market falling -> no new buys (cached 60 s).
        mood_ok, mood_reason = market_mood()
        if not mood_ok:
            return skip(symbol, mood_reason)

        # 5f. At most N open positions per sector.
        sector_ok, sector_reason = sector_check(
            symbol, getattr(stock, "sector", None) if stock is not None else None
        )
        if not sector_ok:
            return skip(symbol, sector_reason)

        # 6. Submit through existing service, re-using the setup that was
        #    just evaluated (no second SetupService run).
        #
        #    Broker/network errors are caught here so one failing symbol
        #    returns a reason instead of aborting the whole watchlist scan.
        risk = setup.get("risk_reward") or {}
        logger.info(
            "Submitting PAPER order %s entry_type=%s style=%s entry=%s stop=%s t1=%s",
            symbol, setup.get("entry_type") or "BREAKOUT", style.value,
            risk.get("entry"), risk.get("stop_loss"), risk.get("target_1"),
        )
        try:
            result = PaperTradingService.submit_order(
                db=db,
                symbol=symbol,
                account_size=settings.account_size,
                risk_percent=settings.risk_percent,
                current_daily_pnl=current_daily_pnl,
                max_daily_loss_percent=max_daily_loss_percent,
                setup=setup,
            )
        except Exception as exc:  # noqa: BLE001 - surface any broker error
            logger.exception("Paper order failed for %s", symbol)
            return {
                "attempted": True,
                "submitted": False,
                "symbol": symbol,
                "mode": "PAPER",
                "reason": f"BROKER_ERROR:{type(exc).__name__}: {exc}",
            }

        if not result.get("submitted"):
            result["reason"] = "; ".join(result.get("reasons") or []) or "NOT_SUBMITTED"
            logger.warning("PAPER order NOT submitted for %s: %s", symbol, result["reason"])
        elif stock is not None:
            logger.info("PAPER order submitted for %s: order_id=%s shares=%s",
                        symbol, result.get("order_id"), result.get("shares"))
            result["holding_style"] = style.value
            result["auto_trade"] = AutoPaperExecutionService._record(
                db=db,
                result=result,
                stock=stock,
                watchlist_stock=watchlist_stock,
                user_id=user_id,
                style=style,
                session=session,
                now=now,
                entry_type=str(setup.get("entry_type") or "BREAKOUT"),
            )

        return {
            "attempted": True,
            **result,
        }

    @staticmethod
    def _record(*, db, result, stock, watchlist_stock, user_id, style, session, now,
                entry_type: str = "BREAKOUT") -> dict:
        """Remember why/when this position was opened. Never raises: the
        order is already at the broker, so a bookkeeping failure must not
        hide that from the caller."""
        try:
            deadline = (
                exit_deadline(style, now, session, settings.time_exit_buffer_minutes)
                if session is not None
                else None
            )
            row = AutoTrade(
                user_id=user_id,
                watchlist_id=getattr(watchlist_stock, "watchlist_id", None),
                stock_id=stock.stock_id,
                symbol=stock.symbol.strip().upper(),
                broker="ALPACA_PAPER",
                broker_order_id=result.get("order_id"),
                holding_style=style.value,
                entry_type=entry_type,
                quantity=int(result.get("shares") or 0),
                stop_loss_price=result.get("stop_loss_price"),
                take_profit_price=result.get("take_profit_price"),
                trail_percent=getattr(watchlist_stock, "loss_limit_percent", None),
                submitted_at=now,
                exit_deadline=deadline,
                status="OPEN",
            )
            db.add(row)
            db.commit()
            return {"id": row.id, "exit_deadline": deadline}
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("Could not record auto trade for %s", stock.symbol)
            return {"error": f"{type(exc).__name__}: {exc}"}
