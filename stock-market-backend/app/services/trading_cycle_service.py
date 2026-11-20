"""One automated trading cycle: sync candles -> scan signals -> paper orders.

Nothing in the app ran this on its own before. Cloud Scheduler calls
POST /api/v1/jobs/trading-cycle every 15 minutes during market hours,
and this service does what a user would otherwise do by clicking:

  1. WatchlistMarketSyncService.sync      (fetch the newest candles)
  2. ValidationWatchlistScanService.scan  (evaluate signals; when
     AUTO_TRADING_ENABLED and PAPER_TRADING_ENABLED are true it submits
     paper orders through AutoPaperExecutionService)
  3. TrailingStopService.sync             (profit protection)

A PostgreSQL advisory lock makes sure two overlapping cycles never run at
the same time, so a slow cycle can't cause duplicate orders.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.market.sessions import (
    INDIA_SESSION,
    US_SESSION,
    MarketSession,
    session_for_stock,
)
from app.models.stock import Stock
from app.models.user import AppUser
from app.models.watchlist import Watchlist, WatchlistStock
from app.services.time_exit_service import TimeExitService
from app.services.trailing_stop_service import TrailingStopService
from app.services.validation_run_service import ValidationRunService
from app.services.validation_watchlist_scan_service import (
    ValidationWatchlistScanService,
)
from app.services.watchlist_market_sync_service import WatchlistMarketSyncService

logger = logging.getLogger(__name__)

# Heartbeat of the most recent cycle (scheduler OR manual job call), shown by
# GET /api/v1/diagnostics/trading-readiness.
LAST_CYCLE: dict = {}

# Arbitrary constant id for pg_try_advisory_lock
_CYCLE_LOCK_ID = 846_215_001

# Keep running this long after the close so the final candle is picked up.
_AFTER_CLOSE_GRACE = timedelta(minutes=20)

MARKETS: dict[str, MarketSession] = {"US": US_SESSION, "IN": INDIA_SESSION}


class TradingCycleService:

    @staticmethod
    def market_window_open(session: MarketSession, now_utc: datetime) -> bool:
        """True from the open until 20 minutes after the actual close.

        Uses the exchange calendar's real close, so half days
        (e.g. day after Thanksgiving, 1:00 PM ET) are handled.
        """
        local = now_utc.astimezone(session.tz)
        day = local.date()
        if not session.is_session_day(day):
            return False
        open_local = datetime.combine(day, session.open, tzinfo=session.tz)
        close_local = datetime.combine(day, session.close_time_on(day), tzinfo=session.tz)
        return open_local <= local < close_local + _AFTER_CLOSE_GRACE

    @staticmethod
    def _watchlist_markets(db: Session, watchlist_id: int) -> set[str]:
        stocks = db.scalars(
            select(Stock)
            .join(WatchlistStock, WatchlistStock.stock_id == Stock.stock_id)
            .where(
                WatchlistStock.watchlist_id == watchlist_id,
                WatchlistStock.analysis_enabled.is_(True),
                Stock.active.is_(True),
            )
        ).all()
        return {session_for_stock(stock).code for stock in stocks}

    @classmethod
    def run(
        cls,
        db: Session,
        market: str | None = None,
        force: bool = False,
        now: datetime | None = None,
    ) -> dict:
        setup_logging()
        now_utc = now or datetime.now(timezone.utc)
        started = datetime.now(timezone.utc)
        LAST_CYCLE.update({"started_at": started, "finished_at": None, "error": None})

        # The lock lives on its OWN connection. Advisory locks belong to the
        # database connection, and the cycle's session hands its connection
        # back to the pool on every commit - unlocking through the session
        # often ran on a different connection, so the lock leaked and later
        # cycles were randomly skipped (2026-11-20: 12:46, 13:01, 13:16).
        lock_conn = db.get_bind().connect()
        try:
            locked = lock_conn.execute(
                text("SELECT pg_try_advisory_lock(:id)"), {"id": _CYCLE_LOCK_ID}
            ).scalar()
            lock_conn.commit()
        except Exception:
            lock_conn.close()
            raise
        if not locked:
            lock_conn.close()
            logger.warning("Trading cycle skipped: previous cycle still running")
            return {"ran": False, "reason": "PREVIOUS_CYCLE_STILL_RUNNING"}

        try:
            summary = cls._run_locked(db, market, force, now_utc)
            LAST_CYCLE.update({
                "finished_at": datetime.now(timezone.utc),
                "markets_open": summary.get("markets_open"),
                "reason": summary.get("reason"),
                "paper_orders_submitted": summary.get("paper_orders_submitted"),
                "blockers": summary.get("blockers"),
                "would_buy_if_enabled": summary.get("would_buy_if_enabled"),
            })
            return summary
        except Exception as exc:
            LAST_CYCLE.update({
                "finished_at": datetime.now(timezone.utc),
                "error": f"{type(exc).__name__}: {exc}",
            })
            logger.exception("Trading cycle crashed")
            raise
        finally:
            try:
                lock_conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": _CYCLE_LOCK_ID})
                lock_conn.commit()
            finally:
                lock_conn.close()

    @classmethod
    def _run_locked(
        cls,
        db: Session,
        market: str | None,
        force: bool,
        now_utc: datetime,
    ) -> dict:
        wanted = {market.upper()} if market else set(MARKETS)
        open_markets = {
            code for code in wanted
            if force or cls.market_window_open(MARKETS[code], now_utc)
        }

        summary: dict = {
            "ran": True,
            "evaluated_at": now_utc,
            "markets_requested": sorted(wanted),
            "markets_open": sorted(open_markets),
            "watchlists": [],
            "paper_orders_submitted": 0,
            "trailing_stops": None,
            "time_exits": None,
            "holdings_guard": None,
            # Counts of the main reason no order was placed, across watchlists.
            "blockers": {},
            # Stocks where the strategy said BUY but a switch / per-stock flag stopped it.
            "would_buy_if_enabled": [],
        }

        logger.info(
            "Trading cycle start: requested=%s open=%s force=%s switches: TRADING=%s PAPER=%s "
            "AUTO=%s LIVE=%s ENTRY_MODE=%s RISK_MODEL=%s",
            sorted(wanted), sorted(open_markets), force,
            settings.trading_enabled, settings.paper_trading_enabled,
            settings.auto_trading_enabled, settings.live_trading_enabled,
            getattr(settings, "entry_mode", "?"), getattr(settings, "risk_model", "?"),
        )

        if not open_markets:
            summary["reason"] = "MARKETS_CLOSED"
            logger.info("Trading cycle: markets closed (%s)", sorted(wanted))
            return summary

        active_run = ValidationRunService.active(db)
        if active_run is None:
            logger.warning("Trading cycle: no ACTIVE validation run; scans will be skipped "
                           "-> NO ORDERS CAN BE PLACED")
            summary["blockers"]["NO_ACTIVE_VALIDATION_RUN"] = 1
        else:
            baseline, note = ValidationRunService.baseline_status(active_run)
            logger.info("Validation run %s (%s) baseline=%s",
                        active_run.validation_run_id, active_run.strategy_version, baseline)
            if baseline != "MATCH":
                logger.warning("Baseline %s: every scan will fail -> NO ORDERS. %s", baseline, note)

        watchlists = db.scalars(
            select(Watchlist).where(Watchlist.active.is_(True))
        ).all()

        for watchlist in watchlists:
            item: dict = {
                "watchlist_id": watchlist.watchlist_id,
                "name": watchlist.name,
            }
            summary["watchlists"].append(item)

            markets = cls._watchlist_markets(db, watchlist.watchlist_id)
            if not markets & open_markets:
                item["skipped"] = "NO_STOCKS_IN_OPEN_MARKETS"
                logger.info("Watchlist %s skipped: no stocks in open markets", watchlist.watchlist_id)
                continue

            owner = db.get(AppUser, watchlist.user_id)
            if owner is None:
                item["skipped"] = "OWNER_NOT_FOUND"
                continue

            # 1. Fetch the newest candles as the watchlist's owner
            #    (Indian stocks use that owner's daily Zerodha login).
            try:
                sync = WatchlistMarketSyncService.sync(
                    db=db, watchlist_id=watchlist.watchlist_id, current_user=owner
                )
                logger.info(
                    "Watchlist %s sync: ok=%s failed=%s",
                    watchlist.watchlist_id, sync["successful_stocks"], sync["failed_stocks"],
                )
                item["sync"] = {
                    "successful_stocks": sync["successful_stocks"],
                    "failed_stocks": sync["failed_stocks"],
                    "errors": [
                        {"symbol": s["symbol"], "errors": s["errors"]}
                        for s in sync["stocks"]
                        if s["errors"]
                    ],
                }
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                logger.exception("Sync failed for watchlist %s", watchlist.watchlist_id)
                item["sync_error"] = f"{type(exc).__name__}: {exc}"
                continue

            # 2. Evaluate signals; submits paper orders when enabled.
            if active_run is None:
                item["scan_skipped"] = "NO_ACTIVE_VALIDATION_RUN"
                continue
            try:
                scan = ValidationWatchlistScanService.scan(
                    db=db,
                    validation_run_id=active_run.validation_run_id,
                    watchlist_id=watchlist.watchlist_id,
                )
                submitted = int(scan.get("paper_orders_submitted") or 0)
                summary["paper_orders_submitted"] += submitted
                item["scan"] = {
                    key: scan.get(key)
                    for key in (
                        "scan_status",
                        "symbols_checked",
                        "symbols_scanned",
                        "symbols_blocked_by_data_quality",
                        "actionable_count",
                        "entry_confirmed_count",
                        "paper_execution_enabled",
                        "paper_execution_attempts",
                        "paper_orders_submitted",
                    )
                }
                # Why each blocked symbol was blocked, e.g. STALE_DATA:3_BAR_LAG
                item["blocked"] = {
                    stock["symbol"]: stock.get("decision_reasons")
                    for stock in scan.get("stocks", [])
                    if stock.get("scan_status") == "DATA_QUALITY_BLOCKED"
                }
                # Why each stock did / didn't get an order this cycle.
                item["decisions"] = {
                    stock["symbol"]: (stock.get("decision") or {}).get("blocker") or "ORDER_SUBMITTED"
                    for stock in scan.get("stocks", [])
                }
                for stock in scan.get("stocks", []):
                    decision = stock.get("decision") or {}
                    key = str(decision.get("blocker") or "ORDER_SUBMITTED").split(":")[0]
                    summary["blockers"][key] = summary["blockers"].get(key, 0) + 1
                    if decision.get("would_buy_if_enabled"):
                        summary["would_buy_if_enabled"].append(stock["symbol"])
                logger.info(
                    "Watchlist %s scan: status=%s scanned=%s actionable=%s entry_confirmed=%s "
                    "attempts=%s submitted=%s",
                    watchlist.watchlist_id, scan.get("scan_status"), scan.get("symbols_scanned"),
                    scan.get("actionable_count"), scan.get("entry_confirmed_count"),
                    scan.get("paper_execution_attempts"), submitted,
                )
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                logger.exception("Scan failed for watchlist %s", watchlist.watchlist_id)
                item["scan_error"] = f"{type(exc).__name__}: {exc}"

        # 3. Profit protection for open Alpaca paper positions (US only).
        if "US" in open_markets:
            try:
                summary["trailing_stops"] = TrailingStopService.sync(db, dry_run=False)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                logger.exception("Trailing stop sync failed")
                summary["trailing_stops"] = {"error": f"{type(exc).__name__}: {exc}"}

            # 4. Holding-style exits (INTRADAY square-off, WEEKLY/MONTHLY time exits)
            try:
                summary["time_exits"] = TimeExitService.sync(db, now=now_utc)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                logger.exception("Time exit sync failed")
                summary["time_exits"] = {"error": f"{type(exc).__name__}: {exc}"}

            # 5. Holdings Guard: trailing stop on holdings, buy back at support
            try:
                from app.services.holdings_guard_service import HoldingsGuardService

                summary["holdings_guard"] = HoldingsGuardService.run(db, now_utc)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                logger.exception("Holdings guard failed")
                summary["holdings_guard"] = {"error": f"{type(exc).__name__}: {exc}"}

        logger.info(
            "Trading cycle done: markets=%s watchlists=%d paper_orders=%d blockers=%s",
            sorted(open_markets),
            len(summary["watchlists"]),
            summary["paper_orders_submitted"],
            summary["blockers"],
        )
        if summary["would_buy_if_enabled"]:
            logger.warning(
                "Strategy said BUY but trading was disabled for: %s "
                "(enable trading for these stocks or check the .env switches)",
                ", ".join(summary["would_buy_if_enabled"]),
            )
        return summary
