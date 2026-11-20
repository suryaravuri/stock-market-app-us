"""Live support-bounce entries (LIVE_BOUNCE_ENABLED=true).

Problem it solves: the 15-minute cycle only sees a bounce after the
15-minute candle closes and then orders a few minutes later, by which time
price may already be back at support (NXPI 2026-11-16: signal 260.45,
filled 259.61, support 259.54).

How it works:
  1. Every 15-minute cycle, the scan computes support/resistance levels,
     the 15-minute ATR and the trend score for each trading-enabled US stock
     and stores them here as a "plan" (remember_plan). That part is slow
     (database + indicators), so it runs once per 15 minutes.
  2. The Alpaca 1-minute stream (early_alert_stream.py) feeds every bar to
     on_minute_bar(). Bars are grouped into LIVE_BOUNCE_BAR_MINUTES-minute
     candles (default 5). When one completes, the SAME bounce rules as the
     15-minute cycle are applied (evaluate_bounce) using the plan's levels.
  3. If it triggers, the live price is re-checked (reprice_bounce) and the
     order goes through AutoPaperExecutionService.process_entry - the same
     switches, per-stock flag, daily entry limit, safety checks, sizing and
     bracket order as every other automatic entry.

Plans older than PLAN_MAX_AGE are ignored, so if the 15-minute cycle stops
(market closed, validation run not active, scheduler crashed) the live path
stops too.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.strategies.support_bounce import (
    BounceDecision,
    BounceRules,
    evaluate_bounce,
    reprice_bounce,
)

logger = logging.getLogger(__name__)

PLAN_MAX_AGE = timedelta(minutes=35)
LIVE_PRICE_MAX_AGE = timedelta(minutes=2)

_lock = threading.Lock()
_plans: dict[str, "BouncePlan"] = {}
_live_prices: dict[str, tuple[float, datetime]] = {}
_fired: set[tuple[str, datetime]] = set()


# --------------------------------------------------------------- plans
@dataclass
class BouncePlan:
    symbol: str
    stock_id: int
    watchlist_id: int
    user_id: int | None
    holding_style: str | None
    levels: list[float]
    entry_atr: float
    trend_score: float | None
    base_setup: dict
    created_at: datetime
    level_atr: float | None = None


def remember_plan(plan: BouncePlan) -> None:
    with _lock:
        _plans[plan.symbol] = plan


def get_plan(symbol: str, now: datetime | None = None) -> BouncePlan | None:
    now = now or datetime.now(timezone.utc)
    with _lock:
        plan = _plans.get(symbol.upper())
    if plan is None or now - plan.created_at > PLAN_MAX_AGE:
        return None
    return plan


def plans_snapshot() -> list[dict]:
    with _lock:
        plans = list(_plans.values())
    return [
        {
            "symbol": p.symbol,
            "created_at": p.created_at,
            "levels": p.levels,
            "entry_atr": round(p.entry_atr, 4),
            "trend_score": p.trend_score,
            "holding_style": p.holding_style,
        }
        for p in sorted(plans, key=lambda x: x.symbol)
    ]


# ---------------------------------------------------------- live price
def set_live_price(symbol: str, price: float, ts: datetime) -> None:
    with _lock:
        _live_prices[symbol.upper()] = (float(price), ts)


def latest_price(symbol: str, now: datetime | None = None) -> float | None:
    """Last 1-minute close from the stream if fresh, else Alpaca's latest
    trade (REST). None if neither is available."""
    now = now or datetime.now(timezone.utc)
    symbol = symbol.upper()
    with _lock:
        cached = _live_prices.get(symbol)
    if cached and now - cached[1] <= LIVE_PRICE_MAX_AGE:
        return cached[0]
    try:
        from alpaca.data.enums import DataFeed
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest

        client = StockHistoricalDataClient(settings.alpaca_api_key, settings.alpaca_secret_key)
        trades = client.get_stock_latest_trade(
            StockLatestTradeRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
        )
        trade = trades.get(symbol) if isinstance(trades, dict) else trades
        return float(trade.price) if trade is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Live price unavailable for %s: %s", symbol, exc)
        return None


def apply_live_check(bounce: dict, symbol: str, rules: BounceRules) -> dict:
    """Re-check a triggered bounce dict against the live price. Returns a
    new dict; 'triggered' may become False with the reason why."""
    if not bounce.get("triggered") or not settings.live_price_check_enabled:
        return bounce
    price = latest_price(symbol)
    if price is None or not bounce.get("entry_atr") or bounce.get("support") is None:
        # Fail closed: without a live price we can't know whether the
        # bounce still holds, so don't buy.
        return {**bounce, "triggered": False, "live_check": "NO_LIVE_PRICE"}
    decision = reprice_bounce(
        support=float(bounce["support"]),
        resistance=bounce.get("resistance") or bounce.get("target_1"),
        target_2=bounce.get("target_2"),
        live_price=price,
        atr=float(bounce["entry_atr"]),
        rules=rules,
    )
    signal_reason = (bounce.get("reasons") or [""])[0]
    updated = {
        **bounce,
        "triggered": decision.triggered,
        "signal_entry": bounce.get("entry"),
        "live_price": price,
        "live_check": decision.reasons[0],
        "reasons": [signal_reason, *decision.reasons],
    }
    if decision.triggered:
        updated.update({
            "entry": price,
            "stop_loss": decision.stop_loss,
            "target_1": decision.target_1,
            "target_2": decision.target_2,
            "rr_1": decision.rr_1,
        })
    return updated


# ------------------------------------------------------ minute candles
@dataclass
class LiveCandle:
    start: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    last_bar: datetime
    emitted: bool = False


@dataclass
class MinuteAggregator:
    """Groups 1-minute bars into N-minute candles aligned to the clock
    (N=5: :00, :05, :10 ...). add() returns candles that just completed:
    either the bar was the bucket's last minute, or a bar for a later bucket
    arrived (IEX can skip minutes with no trades)."""
    minutes: int = 5
    _current: dict[str, LiveCandle] = field(default_factory=dict)

    def _bucket(self, ts: datetime) -> datetime:
        floored = ts.replace(second=0, microsecond=0)
        return floored - timedelta(minutes=floored.minute % self.minutes)

    def add(self, symbol: str, ts: datetime, o, h, l, c, v) -> list[LiveCandle]:
        done: list[LiveCandle] = []
        start = self._bucket(ts)
        candle = self._current.get(symbol)
        if candle is not None and start > candle.start:
            if not candle.emitted:
                candle.emitted = True
                done.append(candle)
            candle = None
        if candle is None:
            candle = LiveCandle(start, float(o), float(h), float(l), float(c), float(v), ts)
            self._current[symbol] = candle
        elif ts > candle.last_bar and not candle.emitted:
            candle.high = max(candle.high, float(h))
            candle.low = min(candle.low, float(l))
            candle.close = float(c)
            candle.volume += float(v)
            candle.last_bar = ts
        else:
            return done  # duplicate / late bar
        if ts + timedelta(minutes=1) >= start + timedelta(minutes=self.minutes) and not candle.emitted:
            candle.emitted = True
            done.append(candle)
        return done


_prev_lows: dict[str, list[float]] = {}   # most recent first, max 2


def evaluate_live_candle(plan: BouncePlan, candle: LiveCandle, rules: BounceRules,
                         prev_lows: list[float] | None = None) -> BounceDecision:
    return evaluate_bounce(
        open_=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        levels=plan.levels,
        atr=plan.entry_atr,
        trend_score=plan.trend_score,
        rules=rules,
        level_atr=plan.level_atr,
        prev_lows=prev_lows,
    )


# ------------------------------------------------------------ execution
def handle_completed_candle(symbol: str, candle: LiveCandle, now: datetime | None = None) -> dict | None:
    """Called from the stream thread (via asyncio.to_thread). Returns the
    order result when an order was attempted, else None."""
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.stock import Stock
    from app.models.watchlist import WatchlistStock
    from app.services.auto_paper_execution_service import AutoPaperExecutionService
    from app.services.decision_log import DecisionLog
    from app.services.support_bounce_service import SupportBounceService, rules_from_settings

    now = now or datetime.now(timezone.utc)
    plan = get_plan(symbol, now)
    if plan is None:
        return None
    key = (symbol, candle.start)
    rules = rules_from_settings()
    with _lock:
        prev_lows = list(_prev_lows.get(symbol, []))
        _prev_lows[symbol] = [candle.low, *prev_lows][:2]
    decision = evaluate_live_candle(plan, candle, rules, prev_lows)
    if not decision.triggered:
        logger.debug("LIVE %s %s-min candle %s: %s", symbol, settings.live_bounce_bar_minutes,
                     candle.start.isoformat(), decision.reasons[:1])
        return None
    with _lock:
        if key in _fired:
            return None
        _fired.add(key)

    bounce = {
        "triggered": True,
        "reasons": decision.reasons,
        "entry_type": "SUPPORT_BOUNCE",
        "support": decision.support,
        "resistance": decision.resistance,
        "entry_atr": plan.entry_atr,
        "entry": decision.entry,
        "stop_loss": decision.stop_loss,
        "target_1": decision.target_1,
        "target_2": decision.target_2,
        "rr_1": decision.rr_1,
        "candle_time": candle.start,
        "source": "LIVE_STREAM",
    }
    set_live_price(symbol, candle.close, candle.last_bar + timedelta(minutes=1))
    bounce = apply_live_check(bounce, symbol, rules)
    logger.info("LIVE bounce signal %s on %s-min candle %s: %s", symbol,
                settings.live_bounce_bar_minutes, candle.start.isoformat(), bounce["reasons"])

    db = SessionLocal()
    try:
        stock = db.get(Stock, plan.stock_id)
        watchlist_stock = db.scalar(
            select(WatchlistStock).where(
                WatchlistStock.watchlist_id == plan.watchlist_id,
                WatchlistStock.stock_id == plan.stock_id,
            )
        )
        if stock is None or watchlist_stock is None:
            return None

        if bounce["triggered"]:
            result = AutoPaperExecutionService.process_entry(
                db=db,
                symbol=symbol,
                setup=SupportBounceService.as_setup(bounce, plan.base_setup),
                watchlist_stock=watchlist_stock,
                stock=stock,
                user_id=plan.user_id,
                now=now,
            )
            result["entry_type"] = "SUPPORT_BOUNCE"
        else:
            result = {
                "attempted": False,
                "submitted": False,
                "reason": f"LIVE_CHECK_FAILED:{bounce.get('live_check')}",
            }

        DecisionLog.record({
            "evaluated_at": now,
            "source": "LIVE_STREAM",
            "watchlist_id": plan.watchlist_id,
            "symbol": symbol,
            "exchange": stock.exchange,
            "indian_stock": False,
            "trading_enabled": bool(watchlist_stock.trading_enabled),
            "holding_style": watchlist_stock.holding_style,
            "entry_mode": settings.entry_mode,
            "switches": {
                "TRADING_ENABLED": bool(settings.trading_enabled),
                "PAPER_TRADING_ENABLED": bool(settings.paper_trading_enabled),
                "AUTO_TRADING_ENABLED": bool(settings.auto_trading_enabled),
                "LIVE_TRADING_DISABLED": not bool(settings.live_trading_enabled),
            },
            "data_status": "PASS",
            "eligible": True,
            "price": bounce.get("live_price") or candle.close,
            "score": plan.trend_score,
            "breakout_summary": "n/a (live stream)",
            "bounce_evaluated": True,
            "bounce_triggered": True,
            "bounce_summary": "; ".join(str(r) for r in bounce["reasons"][:2]),
            "bounce_support": bounce.get("support"),
            "entry_type": "SUPPORT_BOUNCE",
            "order_attempted": bool(result.get("attempted")),
            "order_submitted": bool(result.get("submitted")),
            "order_reason": result.get("reason"),
            "order_id": result.get("order_id"),
        })
        return result
    except Exception:  # noqa: BLE001 - never kill the stream
        db.rollback()
        logger.exception("Live bounce execution failed for %s", symbol)
        return None
    finally:
        db.close()


def reset_day_state(today_start: datetime) -> None:
    """Forget fired keys from previous days (called by the stream)."""
    with _lock:
        for key in [k for k in _fired if k[1] < today_start]:
            _fired.discard(key)
