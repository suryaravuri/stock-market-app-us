"""One-page answer to "why is the bot not buying?".

GET /api/v1/diagnostics/trading-readiness walks every gate an automatic
paper order must pass, top to bottom, and reports each as PASS / WARN / FAIL
with a one-line fix. Nothing here places or changes orders.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import local_scheduler
from app.core.config import settings
from app.market.sessions import US_SESSION, is_indian_exchange
from app.models.market_candle import MarketCandle
from app.models.stock import Stock
from app.models.watchlist import Watchlist, WatchlistStock
from app.services.decision_log import DecisionLog
from app.services.validation_run_service import ValidationRunService

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


def _check(name: str, status: str, detail: str, fix: str | None = None) -> dict:
    return {"name": name, "status": status, "detail": detail, "fix": fix if status != PASS else None}


def _age_minutes(value: datetime | None, now: datetime) -> float | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return round((now - value).total_seconds() / 60, 1)


class TradingReadinessService:

    @classmethod
    def evaluate(cls, db: Session, now: datetime | None = None, check_broker: bool = True) -> dict:
        # Imported lazily: trading_cycle_service imports the whole scan stack.
        from app.services.trading_cycle_service import LAST_CYCLE, TradingCycleService

        now = now or datetime.now(timezone.utc)
        checks: list[dict] = []
        us_open = TradingCycleService.market_window_open(US_SESSION, now)

        # 1. .env switches ------------------------------------------------
        switches = {
            "TRADING_ENABLED": (settings.trading_enabled, True),
            "PAPER_TRADING_ENABLED": (settings.paper_trading_enabled, True),
            "AUTO_TRADING_ENABLED": (settings.auto_trading_enabled, True),
            "LIVE_TRADING_ENABLED": (settings.live_trading_enabled, False),
        }
        for name, (value, wanted) in switches.items():
            checks.append(_check(
                f"Switch {name}",
                PASS if bool(value) == wanted else FAIL,
                f"{name}={str(bool(value)).lower()}",
                f"Set {name}={str(wanted).lower()} in .env and restart the backend",
            ))

        # 2. Market hours -------------------------------------------------
        checks.append(_check(
            "US market open",
            PASS if us_open else WARN,
            "Regular session (plus 20 min grace) is open" if us_open
            else "US market is closed now - no new orders until the next session",
            "Wait for 9:30 AM ET on a trading day",
        ))

        # 2b. Market mood (SPY/QQQ) ----------------------------------------
        if us_open and getattr(settings, "market_filter_enabled", False):
            from app.services.market_guard_service import market_mood

            mood_ok, mood_reason = market_mood()
            checks.append(_check(
                "Market mood filter", PASS if mood_ok else WARN, mood_reason,
                "Market is falling: new buys are paused until it stabilises (by design)",
            ))

        # 3. Scheduler ----------------------------------------------------
        state = dict(local_scheduler.STATE)
        interval = settings.local_scheduler_interval_minutes
        if not settings.local_scheduler_enabled:
            checks.append(_check(
                "Local scheduler", FAIL,
                "LOCAL_SCHEDULER_ENABLED=false - nothing runs the cycle automatically",
                "Set LOCAL_SCHEDULER_ENABLED=true in .env and restart (or call /jobs/trading-cycle)",
            ))
        elif not local_scheduler.is_alive():
            checks.append(_check(
                "Local scheduler", FAIL,
                "Enabled but its thread is not running (startup hook did not run?)",
                "Check main.py lifespan calls local_scheduler.start(); restart the backend",
            ))
        else:
            last_ok_age = _age_minutes(state.get("last_ok_at"), now)
            stale = us_open and (last_ok_age is None or last_ok_age > interval * 2 + 2)
            if state.get("last_error"):
                status = FAIL
                detail = f"Last run FAILED: {str(state['last_error']).strip().splitlines()[-1]}"
            elif stale:
                status = WARN
                detail = (f"Running, but no successful cycle in {last_ok_age} min"
                          if last_ok_age is not None else "Running, no cycle completed yet")
            else:
                status = PASS
                detail = f"Running every {interval} min; last OK {last_ok_age} min ago"
            checks.append(_check(
                "Local scheduler", status, detail,
                "See logs/trading.log for 'Local scheduler cycle failed'",
            ))

        # 4. Validation run ----------------------------------------------
        run = ValidationRunService.active(db)
        if run is None:
            checks.append(_check(
                "Active validation run", FAIL,
                "No ACTIVE validation run - every scan is skipped",
                "Create and start a validation run (Validation page)",
            ))
        else:
            baseline, note = ValidationRunService.baseline_status(run)
            checks.append(_check(
                "Active validation run",
                PASS if baseline == "MATCH" else FAIL,
                f"Run {run.validation_run_id} ({run.strategy_version}) baseline={baseline}",
                (note or "") + " Complete this run and create a new one.",
            ))

        # 5. Alpaca paper account ----------------------------------------
        if check_broker:
            try:
                from app.brokers.alpaca.trading_client import AlpacaPaperTradingClient

                account = AlpacaPaperTradingClient().get_account_summary()
                blocked = account.get("trading_blocked") or account.get("account_blocked")
                bp = float(account.get("buying_power") or 0)
                status = FAIL if blocked or bp <= 0 else PASS
                checks.append(_check(
                    "Alpaca paper account", status,
                    f"status={account.get('status')} buying_power={bp:,.0f} "
                    f"blocked={bool(blocked)}",
                    "Check the paper account on alpaca.markets / regenerate paper API keys",
                ))
            except Exception as exc:  # noqa: BLE001
                checks.append(_check(
                    "Alpaca paper account", FAIL,
                    f"Cannot reach Alpaca: {type(exc).__name__}: {str(exc)[:160]}",
                    "Check ALPACA_API_KEY / ALPACA_SECRET_KEY (paper keys) in .env",
                ))

        # 6. Watchlists / per-stock flags / candle freshness ---------------
        watchlists = cls._watchlists(db, now, us_open)
        us_total = sum(w["us_stocks"] for w in watchlists)
        us_enabled = sum(w["us_trading_enabled"] for w in watchlists)
        checks.append(_check(
            "Stocks enabled for trading",
            PASS if us_enabled else FAIL,
            f"{us_enabled} of {us_total} US watchlist stocks have trading_enabled=true",
            "Turn on 'Trading' for the stocks in Watchlist management (default is OFF)",
        ))
        indian = sum(w["indian_stocks"] for w in watchlists)
        if indian:
            checks.append(_check(
                "Indian stocks in watchlists", WARN,
                f"{indian} NSE/BSE stocks: they fail sync without Zerodha and are never auto-traded",
                "Disable analysis for them or move them to a separate watchlist",
            ))
        stale = [s for w in watchlists for s in w["stocks"] if s.get("stale")]
        if us_open:
            checks.append(_check(
                "15-minute candles fresh",
                PASS if not stale else WARN,
                "All US stocks have a recent 15Min candle" if not stale
                else f"{len(stale)} US stocks have candles older than 45 min: "
                     + ", ".join(s["symbol"] for s in stale[:8]),
                "The sync step is failing or not running - check the scheduler/logs",
            ))

        # 6b. Live 1-minute bounce entries --------------------------------
        live = {"enabled": bool(getattr(settings, "live_bounce_enabled", False))}
        if live["enabled"]:
            from app.services import live_bounce_service
            from app.services.early_alert_stream import early_alert_stream

            stream_alive = bool(early_alert_stream._thread and early_alert_stream._thread.is_alive())
            fresh = [p for p in live_bounce_service.plans_snapshot()
                     if now - p["created_at"] <= live_bounce_service.PLAN_MAX_AGE]
            live.update({"stream_alive": stream_alive, "symbols": early_alert_stream.symbols,
                         "fresh_plans": fresh})
            if not stream_alive:
                status, detail = FAIL, "LIVE_BOUNCE_ENABLED=true but the 1-minute stream is not running"
            elif us_open and not fresh:
                status, detail = WARN, "Stream running, but no fresh plans yet (wait for the next 15-min cycle)"
            else:
                status, detail = PASS, (f"Stream running for {len(early_alert_stream.symbols)} symbols, "
                                        f"{len(fresh)} stocks armed, {settings.live_bounce_bar_minutes}-min candles")
            checks.append(_check(
                "Live 1-minute bounce entries", status, detail,
                "Restart the backend; check logs/trading.log for 'stream stopped with an error'",
            ))

        # 7. Strategy settings -------------------------------------------
        checks.append(_check(
            "Strategy settings", PASS,
            f"ENTRY_MODE={getattr(settings, 'entry_mode', '?')} "
            f"RISK_MODEL={getattr(settings, 'risk_model', '?')} "
            f"BOUNCE_MIN_RR={getattr(settings, 'bounce_min_rr', '?')} "
            f"ACCOUNT_SIZE={settings.account_size} RISK_PERCENT={settings.risk_percent}",
        ))

        # 8. What recent scans decided -----------------------------------
        recent = DecisionLog.recent(limit=500)
        cutoff = (now - timedelta(hours=24)).isoformat()
        recent = [r for r in recent if str(r.get("evaluated_at") or "") >= cutoff]
        counts = DecisionLog.blocker_counts(recent)
        would_buy = sorted({r["symbol"] for r in recent if r.get("would_buy_if_enabled")})

        failing = [c for c in checks if c["status"] == FAIL]
        if failing:
            headline = f"Blocked: {failing[0]['name']} - {failing[0]['detail']}"
        elif would_buy:
            headline = "Strategy wanted to buy " + ", ".join(would_buy) + " but trading was off for them"
        elif counts:
            top = next(iter(counts))
            headline = f"Gates OK. Most common reason for no order (24h): {top}"
        else:
            headline = "Gates OK. No scans recorded yet since the backend started."

        return {
            "evaluated_at": now,
            "ready": not failing,
            "headline": headline,
            "checks": checks,
            "scheduler": state,
            "last_cycle": dict(LAST_CYCLE),
            "decisions_24h": {
                "count": len(recent),
                "blockers": counts,
                "would_buy_if_enabled": would_buy,
            },
            "watchlists": watchlists,
            "live_bounce": live,
        }

    @staticmethod
    def _watchlists(db: Session, now: datetime, us_open: bool) -> list[dict]:
        latest = (
            select(MarketCandle.stock_id, func.max(MarketCandle.candle_time).label("latest"))
            .where(MarketCandle.timeframe == "15Min")
            .group_by(MarketCandle.stock_id)
            .subquery()
        )
        out = []
        for wl in db.scalars(select(Watchlist).where(Watchlist.active.is_(True))).all():
            rows = db.execute(
                select(WatchlistStock, Stock, latest.c.latest)
                .join(Stock, Stock.stock_id == WatchlistStock.stock_id)
                .outerjoin(latest, latest.c.stock_id == Stock.stock_id)
                .where(
                    WatchlistStock.watchlist_id == wl.watchlist_id,
                    WatchlistStock.analysis_enabled.is_(True),
                    Stock.active.is_(True),
                )
                .order_by(Stock.symbol)
            ).all()
            stocks = []
            for ws, stock, last in rows:
                indian = is_indian_exchange(stock.exchange)
                age = _age_minutes(last, now)
                stocks.append({
                    "symbol": stock.symbol.strip().upper(),
                    "exchange": stock.exchange,
                    "trading_enabled": bool(ws.trading_enabled),
                    "holding_style": getattr(ws, "holding_style", None),
                    "latest_15min_candle": last,
                    "candle_age_minutes": age,
                    # 15Min bar start + 15 min to complete + 15 min slack
                    "stale": us_open and (not indian) and (age is None or age > 45),
                })
            us = [s for s in stocks if not is_indian_exchange(s["exchange"])]
            out.append({
                "watchlist_id": wl.watchlist_id,
                "name": wl.name,
                "user_id": wl.user_id,
                "us_stocks": len(us),
                "us_trading_enabled": sum(s["trading_enabled"] for s in us),
                "indian_stocks": len(stocks) - len(us),
                "stocks": stocks,
            })
        return out
