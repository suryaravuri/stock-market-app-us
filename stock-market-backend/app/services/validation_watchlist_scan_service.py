from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.market.sessions import is_indian_exchange, session_for_stock
from app.services.support_bounce_service import (
    SupportBounceService,
    entry_mode_allows,
    rules_from_settings,
)
from app.models.stock import Stock
from app.models.validation_run import ValidationRun
from app.models.watchlist import Watchlist, WatchlistStock
from app.schemas.market import MarketTimeframe
from app.services.setup_service import SetupService
from app.services.validation_market_data_service import ValidationMarketDataService
from app.services.validation_run_service import ValidationRunService
from app.services.completed_candle_guard import CompletedCandleGuard
from app.services.auto_paper_execution_service import AutoPaperExecutionService
from app.core.config import settings
from app.market.app_market import exchange_allowed
from app.services.decision_log import DecisionLog, breakout_summary
from app.services.live_bounce_service import BouncePlan, apply_live_check, remember_plan


def _switches() -> dict[str, bool]:
    """The .env switches that must all be ON for an automatic paper order."""
    return {
        "TRADING_ENABLED": bool(settings.trading_enabled),
        "PAPER_TRADING_ENABLED": bool(settings.paper_trading_enabled),
        "AUTO_TRADING_ENABLED": bool(settings.auto_trading_enabled),
        "LIVE_TRADING_DISABLED": not bool(settings.live_trading_enabled),
    }


def _decision_base(run, watchlist, watchlist_stock, stock, evaluated_at, market_status, eligible, q) -> dict:
    return {
        "evaluated_at": evaluated_at,
        "validation_run_id": run.validation_run_id,
        "watchlist_id": watchlist.watchlist_id,
        "symbol": stock.symbol.strip().upper(),
        "exchange": stock.exchange,
        "indian_stock": is_indian_exchange(stock.exchange),
        "trading_enabled": bool(watchlist_stock.trading_enabled),
        "holding_style": getattr(watchlist_stock, "holding_style", None),
        "entry_mode": settings.entry_mode,
        "switches": _switches(),
        "data_status": market_status,
        "eligible": eligible,
        "data_reasons": list(q.get("reasons", [])) if q else ["MARKET_DATA_VALIDATION_MISSING"],
        "latest_candle": q.get("latest_regular_session_candle") if q else None,
        "freshness_lag_bars": q.get("freshness_lag_bars") if q else None,
        "expected_candle": q.get("expected_latest_completed_candle") if q else None,
    }


# A 15-minute candle is "fresh" if it closed at most this long ago.
SIGNAL_MAX_AGE = timedelta(minutes=20)


def _signal_is_fresh(candle_start, now, bar=timedelta(minutes=15)) -> bool:
    if candle_start is None:
        return False
    if candle_start.tzinfo is None:
        candle_start = candle_start.replace(tzinfo=timezone.utc)
    return timedelta(0) <= now - (candle_start + bar) <= SIGNAL_MAX_AGE


class ValidationWatchlistScanService:
    """Frozen-V1 watchlist scan for Phase 16 real analytical validation.

    Only symbols that pass #16B market-data validation are allowed to invoke the
    existing SetupService.  SetupService may advance the persisted analytical
    signal/position lifecycle; no broker call is performed here.
    """

    EXECUTION_MODE = "ANALYSIS_ONLY"

    @classmethod
    def scan(
            cls,
            db: Session,
            validation_run_id: int,
            watchlist_id: int = 1,
            timeframe: MarketTimeframe = MarketTimeframe.FIFTEEN_MINUTES,
    ) -> dict:
        if timeframe != MarketTimeframe.FIFTEEN_MINUTES:
            raise ValueError("#16C frozen V1 scanner currently supports timeframe=15Min only")

        run = db.get(ValidationRun, validation_run_id)
        if run is None:
            raise ValueError(f"Validation run not found: {validation_run_id}")
        if run.status != "ACTIVE":
            raise ValueError(
                f"Validation run {validation_run_id} is {run.status}; frozen-V1 scan requires ACTIVE"
            )

        baseline_status, baseline_note = ValidationRunService.baseline_status(run)
        if baseline_status != "MATCH":
            raise ValueError(baseline_note or "BASELINE_MISMATCH")

        evaluated_at = datetime.now(timezone.utc)

        market_validation = ValidationMarketDataService.validate_watchlist(
            db=db,
            validation_run_id=validation_run_id,
            watchlist_id=watchlist_id,
            timeframe=timeframe,
            now=evaluated_at,
        )
        quality_by_stock_id = {item["stock_id"]: item for item in market_validation["results"]}

        watchlist = db.get(Watchlist, watchlist_id)
        if watchlist is None:
            raise ValueError(f"Watchlist '{watchlist_id}' not found")

        stmt = (
            select(WatchlistStock, Stock)
            .join(Stock, Stock.stock_id == WatchlistStock.stock_id)
            .where(
                WatchlistStock.watchlist_id == watchlist_id,
                WatchlistStock.analysis_enabled.is_(True),
                Stock.active.is_(True),
            )
            .order_by(WatchlistStock.priority.desc(), Stock.symbol.asc())
        )
        rows = [row for row in db.execute(stmt).all() if exchange_allowed(row[1].exchange)]

        results: list[dict] = []
        scanned = blocked = failures = actionable = entry_confirmed = 0
        signal_mutations = position_mutations = 0
        paper_orders_submitted = 0
        paper_execution_attempts = 0

        for watchlist_stock, stock in rows:
            q = quality_by_stock_id.get(stock.stock_id)
            market_status = q["status"] if q else "FAIL"
            eligible = bool(q and q["eligible_for_signal_analysis"])

            base = {
                "stock_id": stock.stock_id,
                "symbol": stock.symbol.strip().upper(),
                "company_name": stock.company_name,
                "exchange": stock.exchange,
                "priority": watchlist_stock.priority,
                "market_data_status": market_status,
                "eligible_for_signal_analysis": eligible,
            }

            decision = _decision_base(
                run, watchlist, watchlist_stock, stock, evaluated_at, market_status, eligible, q
            )

            if not eligible:
                blocked += 1
                reasons = list(q.get("reasons", [])) if q else ["MARKET_DATA_VALIDATION_MISSING"]
                blocked_record = DecisionLog.record(decision)
                results.append({
                    **base,
                    "scan_status": "DATA_QUALITY_BLOCKED",
                    "action": "UNAVAILABLE",
                    "actionable": False,
                    "decision_reasons": reasons,
                    "decision": {
                        "outcome": blocked_record["outcome"],
                        "blocker": blocked_record["blocker"],
                        "would_buy_if_enabled": False,
                    },
                    "error": None,
                })
                continue

            try:
                analysis_as_of = q.get("expected_latest_completed_candle")
                cutoffs = {
                    MarketTimeframe.FIFTEEN_MINUTES.value: analysis_as_of,
                    MarketTimeframe.ONE_HOUR.value: ValidationMarketDataService.expected_latest_completed_candle(
                        MarketTimeframe.ONE_HOUR.value, evaluated_at, session_for_stock(stock)
                    ),
                    MarketTimeframe.ONE_DAY.value: ValidationMarketDataService.expected_latest_completed_candle(
                        MarketTimeframe.ONE_DAY.value, evaluated_at, session_for_stock(stock)
                    ),
                }
                latest_stored = CompletedCandleGuard.latest_stored_candle(
                    db, stock.stock_id, timeframe.value
                )
                with CompletedCandleGuard.enforce(db, cutoffs):
                    setup = SetupService.get_setup(db=db, symbol=stock.symbol)
                scanned += 1
                lifecycle = setup.get("signal_lifecycle") or {}
                position = setup.get("position_lifecycle") or {}
                breakout = setup.get("breakout_confirmation") or {}
                multi = setup.get("multi_timeframe") or {}
                risk = setup.get("risk_reward") or {}

                state_changed = bool(lifecycle.get("state_changed"))
                position_db_mutated = bool(position.get("database_mutated"))
                signal_mutations += int(state_changed)
                position_mutations += int(position_db_mutated)

                is_entry_confirmed = lifecycle.get("state") == "ENTRY_CONFIRMED"
                entry_confirmed += int(is_entry_confirmed)
                actionable += int(bool(setup.get("actionable")))

                # Only trade a candle that just closed. At 9:31 AM the newest
                # completed 15-min candle is YESTERDAY's 3:45 PM candle; acting
                # on it bought AVGO on 2026-11-18 from a stale 4:16 PM signal.
                fresh_signal = _signal_is_fresh(analysis_as_of, evaluated_at)
                entry_setup = setup if (
                    entry_mode_allows(settings.entry_mode, "BREAKOUT") and fresh_signal
                ) else {
                    **setup, "actionable": False,
                }
                paper_execution = AutoPaperExecutionService.process_entry(
                    db=db,
                    symbol=stock.symbol,
                    setup=entry_setup,
                    watchlist_stock=watchlist_stock,
                    stock=stock,
                    user_id=watchlist.user_id,
                    now=evaluated_at,
                )

                # Support-bounce entry: buy near support, sell at resistance.
                bounce = None
                if (
                    not paper_execution.get("submitted")
                    and entry_mode_allows(settings.entry_mode, "SUPPORT_BOUNCE")
                    and not is_indian_exchange(stock.exchange)
                ):
                    try:
                        session = session_for_stock(stock)
                        bounce = SupportBounceService.evaluate(
                            db,
                            stock,
                            holding_style=watchlist_stock.holding_style,
                            trend_score=multi.get("overall_score"),
                            cutoffs={
                                tf.value: ValidationMarketDataService.expected_latest_completed_candle(
                                    tf.value, evaluated_at, session
                                )
                                for tf in (
                                    MarketTimeframe.FIFTEEN_MINUTES,
                                    MarketTimeframe.ONE_HOUR,
                                    MarketTimeframe.ONE_DAY,
                                )
                            },
                        )
                        # Prepare the live 1-minute path (live_bounce_service):
                        # levels/ATR/trend for this stock until the next cycle.
                        if (
                            bounce.get("entry_atr")
                            and watchlist_stock.trading_enabled
                            and settings.live_bounce_enabled
                        ):
                            remember_plan(BouncePlan(
                                symbol=stock.symbol.strip().upper(),
                                stock_id=stock.stock_id,
                                watchlist_id=watchlist.watchlist_id,
                                user_id=watchlist.user_id,
                                holding_style=watchlist_stock.holding_style,
                                levels=list(bounce.get("levels") or []),
                                entry_atr=float(bounce["entry_atr"]),
                                trend_score=multi.get("overall_score"),
                                base_setup=setup,
                                created_at=evaluated_at,
                                level_atr=bounce.get("level_atr"),
                            ))

                        # Re-check against the live price: the candle closed a
                        # few minutes ago and price may already be back at support.
                        if bounce["triggered"] and not fresh_signal:
                            bounce = {**bounce, "triggered": False,
                                      "live_check": "STALE_SIGNAL_CANDLE"}
                            paper_execution = {
                                "attempted": False,
                                "submitted": False,
                                "symbol": stock.symbol.strip().upper(),
                                "mode": "PAPER",
                                "reason": "LIVE_CHECK_FAILED:STALE_SIGNAL_CANDLE "
                                          f"(candle {analysis_as_of})",
                            }
                        if bounce["triggered"]:
                            bounce = apply_live_check(bounce, stock.symbol.strip().upper(),
                                                      rules_from_settings())
                            if not bounce["triggered"]:
                                paper_execution = {
                                    "attempted": False,
                                    "submitted": False,
                                    "symbol": stock.symbol.strip().upper(),
                                    "mode": "PAPER",
                                    "reason": f"LIVE_CHECK_FAILED:{bounce.get('live_check')}",
                                }

                        # Evaluated even when trading is disabled for the stock
                        # so the decision log can say "would have bought";
                        # process_entry still refuses to order in that case.
                        if bounce["triggered"]:
                            paper_execution = AutoPaperExecutionService.process_entry(
                                db=db,
                                symbol=stock.symbol,
                                setup=SupportBounceService.as_setup(bounce, setup),
                                watchlist_stock=watchlist_stock,
                                stock=stock,
                                user_id=watchlist.user_id,
                                now=evaluated_at,
                            )
                            paper_execution["entry_type"] = "SUPPORT_BOUNCE"
                    except Exception as exc:  # noqa: BLE001 - never break the scan
                        db.rollback()
                        bounce = {"triggered": False, "reasons": [f"{type(exc).__name__}: {exc}"]}

                paper_execution_attempts += int(
                    bool(paper_execution.get("attempted"))
                )

                paper_orders_submitted += int(
                    bool(paper_execution.get("submitted"))
                )

                decision.update({
                    "signal_state": lifecycle.get("state"),
                    "action": setup.get("action"),
                    "actionable": bool(setup.get("actionable")),
                    "score": multi.get("overall_score"),
                    "rr_quality": risk.get("quality"),
                    "rr_1": risk.get("rr_1"),
                    "price": setup.get("current_price"),
                    "breakout_ready": bool(
                        is_entry_confirmed and setup.get("actionable")
                        and entry_mode_allows(settings.entry_mode, "BREAKOUT")
                    ),
                    "breakout_summary": breakout_summary(setup),
                    "breakout_reasons": list(setup.get("decision_reasons") or [])[:4],
                    "bounce_evaluated": bounce is not None,
                    "bounce_triggered": bool(bounce and bounce.get("triggered")),
                    "bounce_summary": (
                        "not evaluated" if bounce is None
                        else "; ".join(str(r) for r in (bounce.get("reasons") or [])[:2])
                    ),
                    "bounce_support": (bounce or {}).get("support"),
                    "entry_type": paper_execution.get("entry_type") or (
                        "BREAKOUT" if paper_execution.get("submitted") else None
                    ),
                    "order_attempted": bool(paper_execution.get("attempted")),
                    "order_submitted": bool(paper_execution.get("submitted")),
                    "order_reason": paper_execution.get("reason"),
                    "order_id": paper_execution.get("order_id"),
                })
                decision_record = DecisionLog.record(decision)

                results.append({
                    **base,
                    "scan_status": "SCANNED",
                    # Why an order was / wasn't placed (previously not returned).
                    "paper_execution": paper_execution,
                    "support_bounce": bounce,
                    "decision": {
                        "outcome": decision_record["outcome"],
                        "blocker": decision_record["blocker"],
                        "would_buy_if_enabled": decision_record["would_buy_if_enabled"],
                    },
                    "current_price": setup.get("current_price"),
                    "overall_score": multi.get("overall_score"),
                    "overall_classification": multi.get("overall_classification"),
                    "risk_reward_quality": risk.get("quality"),
                    "rr_1": risk.get("rr_1"),
                    "rr_2": risk.get("rr_2"),
                    "entry": risk.get("entry"),
                    "stop_loss": risk.get("stop_loss"),
                    "target_1": risk.get("target_1"),
                    "target_2": risk.get("target_2"),
                    "action": setup.get("action") or "UNAVAILABLE",
                    "actionable": bool(setup.get("actionable")),
                    "decision_reasons": list(setup.get("decision_reasons") or []),
                    "breakout_status": breakout.get("status"),
                    "breakout_confirmed": bool(breakout.get("confirmed")),
                    "signal_state": lifecycle.get("state"),
                    "signal_previous_state": lifecycle.get("previous_state"),
                    "signal_event": lifecycle.get("last_event"),
                    "signal_state_changed": state_changed,
                    "signal_cycle_number": lifecycle.get("cycle_number"),
                    "signal_candle_time": lifecycle.get("signal_candle_time"),
                    "analysis_as_of": analysis_as_of,
                    "latest_stored_candle": latest_stored,
                    "completed_candle_enforcement": True,
                    "used_incomplete_candle": bool(
                        lifecycle.get("signal_candle_time") is not None
                        and analysis_as_of is not None
                        and lifecycle.get("signal_candle_time") > analysis_as_of
                    ),
                    "position_state": position.get("state"),
                    "position_opening_gate_passed": bool(position.get("opening_gate_passed")),
                    "position_database_mutated": position_db_mutated,
                    "error": None,
                })
            except ValueError as exc:
                failures += 1
                failed_record = DecisionLog.record({**decision, "analysis_error": str(exc)[:200]})
                results.append({
                    **base,
                    "scan_status": "ANALYSIS_FAILED",
                    "action": "UNAVAILABLE",
                    "actionable": False,
                    "decision_reasons": [str(exc)],
                    "decision": {
                        "outcome": failed_record["outcome"],
                        "blocker": failed_record["blocker"],
                        "would_buy_if_enabled": False,
                    },
                    "error": str(exc),
                })

        # Keep actionable/confirmed names near the top while preserving score/priority.
        results.sort(
            key=lambda item: (
                item.get("scan_status") != "SCANNED",
                item.get("signal_state") != "ENTRY_CONFIRMED",
                not bool(item.get("actionable")),
                -(item.get("overall_score") if item.get("overall_score") is not None else -999),
                -item.get("priority", 0),
            )
        )

        if failures:
            scan_status = "PARTIAL"
        elif blocked:
            scan_status = "DATA_QUALITY_BLOCKED"
        else:
            scan_status = "PASS"

        return {
            "validation_run_id": run.validation_run_id,
            "strategy_version": run.strategy_version,
            "validation_phase": run.validation_phase,
            "execution_mode": cls.EXECUTION_MODE,
            "baseline_status": baseline_status,
            "watchlist_id": watchlist.watchlist_id,
            "watchlist_name": watchlist.name,
            "timeframe": timeframe.value,
            "scan_status": scan_status,
            "symbols_checked": len(rows),
            "symbols_eligible": sum(bool(r.get("eligible_for_signal_analysis")) for r in results),
            "symbols_scanned": scanned,
            "symbols_blocked_by_data_quality": blocked,
            "symbols_failed_analysis": failures,
            "actionable_count": actionable,
            "entry_confirmed_count": entry_confirmed,
            "evaluated_at": evaluated_at,
            "stocks": results,
            "signal_state_mutations": signal_mutations,
            "position_state_mutations": position_mutations,
            "database_mutated": bool(signal_mutations or position_mutations),
            "production_position_tables_mutated": bool(position_mutations),
            "paper_execution_enabled": bool(
                settings.auto_trading_enabled
                and settings.paper_trading_enabled
                and not settings.live_trading_enabled
            ),
            "paper_execution_attempts": paper_execution_attempts,
            "paper_orders_submitted": paper_orders_submitted,
            "broker_order_submitted": paper_orders_submitted > 0,
        }
