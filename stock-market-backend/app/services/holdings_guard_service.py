"""Holdings Guard: trailing stop on part of each holding, buy back at support.

For long-term holdings (HOLDINGS_GUARD_SYMBOLS, Alpaca paper only):

  GUARDING       A GTC trailing-stop SELL order (Alpaca-native, follows the
                 high automatically) protects the TRADE part of the holding
                 (HOLDINGS_GUARD_TRADE_PCT, default 40%). The CORE part is
                 never sold. Any other sell orders on the symbol (e.g. bracket
                 legs from an auto-trade) are cancelled once when the guard
                 takes over, so only the guard manages it.
  WAITING_REBUY  The trailing stop filled. Buy the same number of shares back
                 when, in order of preference:
                   a) the support-bounce rule fires below the sell price
                      (and the market-mood filter is OK), or
                   b) price recovers to sell price + REBUY_ABOVE_PCT
                      (so a quick rebound doesn't leave you out), or
                   c) REBUY_MAX_DAYS pass (it's a holding - get back in).
                 Then back to GUARDING with a fresh trailing stop.

Runs as a step of every 15-minute trading cycle, only in regular hours.
State is kept in logs/holdings_guard_state.json so a restart doesn't lose
"sold, waiting to buy back".
"""
from __future__ import annotations

import json
import logging
import math
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.logging_config import log_dir

logger = logging.getLogger(__name__)
_lock = threading.Lock()

GUARDING = "GUARDING"
WAITING_REBUY = "WAITING_REBUY"


def guarded_symbols() -> set[str]:
    if not getattr(settings, "holdings_guard_enabled", False):
        return set()
    raw = getattr(settings, "holdings_guard_symbols", "") or ""
    return {s.strip().upper() for s in raw.split(",") if s.strip()}


def is_guarded(symbol: str) -> bool:
    return (symbol or "").strip().upper() in guarded_symbols()


# ------------------------------------------------------------ pure logic
def trade_quantity(position_qty: float, trade_pct: float) -> int:
    """Whole shares in the trade part; at least 1 if the position allows."""
    qty = math.floor(position_qty * trade_pct / 100)
    if qty < 1 and position_qty >= 1:
        qty = 1
    return int(qty)


def auto_trail_percent(daily_atr_pct: float | None, minimum: float = 4.0, maximum: float = 12.0) -> float:
    """2.5 x the stock's normal daily move, kept between 4% and 12%: wide
    enough to ignore normal noise (AMD needs more room than KO)."""
    if not daily_atr_pct:
        return 8.0
    return round(min(max(2.5 * daily_atr_pct, minimum), maximum), 1)


@dataclass
class RebuyDecision:
    buy: bool
    reason: str


def rebuy_decision(
    *,
    sold_price: float,
    sold_at: datetime,
    now: datetime,
    price: float,
    bounce_triggered: bool,
    market_ok: bool,
    rebuy_above_pct: float,
    max_days: int,
) -> RebuyDecision:
    if bounce_triggered and price < sold_price and market_ok:
        return RebuyDecision(True, f"REBUY_AT_SUPPORT: bounce at {price:.2f} (sold {sold_price:.2f})")
    if price >= sold_price * (1 + rebuy_above_pct / 100):
        return RebuyDecision(True, f"REBUY_RECOVERY: {price:.2f} is {rebuy_above_pct}% above sell {sold_price:.2f}")
    if now - sold_at >= timedelta(days=max_days):
        return RebuyDecision(True, f"REBUY_MAX_DAYS: out for {max_days} days")
    gap = (price / sold_price - 1) * 100
    return RebuyDecision(False, f"Waiting: price {price:.2f} ({gap:+.1f}% vs sell {sold_price:.2f})")


# ------------------------------------------------------------- state file
def _state_path():
    return log_dir() / "holdings_guard_state.json"


def load_state() -> dict:
    try:
        return json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    path = _state_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------- runner
class HoldingsGuardService:

    @classmethod
    def run(cls, db, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        symbols = sorted(guarded_symbols())
        if not symbols:
            return {"enabled": False}

        from app.brokers.alpaca.trading_client import AlpacaPaperTradingClient
        from app.services.auto_paper_execution_service import regular_session_open
        from app.market.sessions import US_SESSION

        if not regular_session_open(US_SESSION, now):
            return {"enabled": True, "skipped": "MARKET_CLOSED"}

        client = AlpacaPaperTradingClient()
        results = []
        with _lock:
            state = load_state()
            for symbol in symbols:
                try:
                    results.append(cls._run_symbol(db, client, symbol, state.setdefault(symbol, {}), now))
                except Exception as exc:  # noqa: BLE001 - keep other holdings going
                    logger.exception("Holdings guard failed for %s", symbol)
                    results.append({"symbol": symbol, "action": "ERROR", "reason": str(exc)[:200]})
            save_state(state)
        return {"enabled": True, "results": results}

    @classmethod
    def _run_symbol(cls, db, client, symbol: str, s: dict, now: datetime) -> dict:
        s.setdefault("state", GUARDING)
        if s["state"] == WAITING_REBUY:
            return cls._waiting(db, client, symbol, s, now)

        # ---- GUARDING
        order_id = s.get("trail_order_id")
        if order_id:
            order = client.client.get_order_by_id(order_id)
            status = str(getattr(order.status, "value", order.status)).lower()
            if status == "filled":
                s.update({
                    "state": WAITING_REBUY,
                    "sold_qty": float(order.filled_qty),
                    "sold_price": float(order.filled_avg_price),
                    "sold_at": (order.filled_at or now).isoformat(),
                    "trail_order_id": None,
                })
                logger.warning("HOLDINGS GUARD %s: trailing stop SOLD %s @ %.2f - waiting to buy back",
                               symbol, s["sold_qty"], s["sold_price"])
                return {"symbol": symbol, "action": "SOLD", **s}
            if status in ("new", "accepted", "held", "pending_new", "partially_filled"):
                return {"symbol": symbol, "action": "GUARDING", "trail_order_id": order_id,
                        "trail_percent": s.get("trail_percent")}
            s["trail_order_id"] = None  # cancelled/expired/rejected -> place a new one

        qty = client.get_position_quantity(symbol)
        if qty <= 0:
            return {"symbol": symbol, "action": "NO_POSITION"}

        # Take over exits once: other sell orders (bracket legs) hold the
        # shares, and Alpaca would reject the trailing stop otherwise.
        if client.get_open_sell_orders(symbol):
            cancelled = client.cancel_open_orders(symbol)
            logger.info("HOLDINGS GUARD %s: cancelled %d existing exit orders to take over", symbol, cancelled)
            return {"symbol": symbol, "action": "TOOK_OVER_EXITS", "cancelled": cancelled}

        trade_qty = trade_quantity(qty, settings.holdings_guard_trade_pct)
        if trade_qty < 1:
            return {"symbol": symbol, "action": "TOO_SMALL", "position_qty": qty}
        trail = settings.holdings_guard_trail_pct or auto_trail_percent(cls._daily_atr_pct(db, symbol))

        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import TrailingStopOrderRequest

        order = client.client.submit_order(TrailingStopOrderRequest(
            symbol=symbol, qty=trade_qty, side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC, trail_percent=trail,
        ))
        s.update({"state": GUARDING, "trail_order_id": str(order.id), "trail_percent": trail,
                  "trade_qty": trade_qty, "core_qty": qty - trade_qty, "since": now.isoformat()})
        logger.info("HOLDINGS GUARD %s: trailing stop %.1f%% on %d of %s shares (core %s never sold)",
                    symbol, trail, trade_qty, qty, qty - trade_qty)
        return {"symbol": symbol, "action": "TRAIL_PLACED", **s}

    @classmethod
    def _waiting(cls, db, client, symbol: str, s: dict, now: datetime) -> dict:
        from app.services.decision_log import DecisionLog
        from app.services.live_bounce_service import latest_price
        from app.services.market_guard_service import market_mood

        price = latest_price(symbol, now)
        if price is None:
            return {"symbol": symbol, "action": "WAITING_REBUY", "reason": "NO_LIVE_PRICE"}
        recent = DecisionLog.recent(symbol=symbol, limit=3)
        cutoff = (now - timedelta(minutes=20)).isoformat()
        bounce = any(r.get("bounce_triggered") and str(r.get("evaluated_at")) >= cutoff for r in recent)
        decision = rebuy_decision(
            sold_price=float(s["sold_price"]),
            sold_at=datetime.fromisoformat(str(s["sold_at"])),
            now=now,
            price=price,
            bounce_triggered=bounce,
            market_ok=market_mood()[0],
            rebuy_above_pct=settings.holdings_guard_rebuy_above_pct,
            max_days=settings.holdings_guard_rebuy_max_days,
        )
        if not decision.buy:
            return {"symbol": symbol, "action": "WAITING_REBUY", "reason": decision.reason}

        qty = int(s["sold_qty"])
        order = client.submit_market_buy(symbol, qty)
        logger.warning("HOLDINGS GUARD %s: BUY BACK %d - %s", symbol, qty, decision.reason)
        s.update({"state": GUARDING, "trail_order_id": None, "last_rebuy": {
            "at": now.isoformat(), "qty": qty, "price_seen": price, "reason": decision.reason,
            "order_id": str(getattr(order, "id", "")), "sold_price": s.get("sold_price"),
        }})
        for key in ("sold_qty", "sold_price", "sold_at"):
            s.pop(key, None)
        return {"symbol": symbol, "action": "BOUGHT_BACK", "reason": decision.reason}

    @staticmethod
    def _daily_atr_pct(db, symbol: str) -> float | None:
        from sqlalchemy import func, select

        from app.indicators.atr import calculate_atr
        from app.models.market_candle import MarketCandle
        from app.models.stock import Stock

        stock = db.scalar(select(Stock).where(func.upper(Stock.symbol) == symbol))
        if stock is None:
            return None
        rows = list(reversed(db.scalars(
            select(MarketCandle).where(MarketCandle.stock_id == stock.stock_id,
                                       MarketCandle.timeframe == "1Day")
            .order_by(MarketCandle.candle_time.desc()).limit(30)
        ).all()))
        if len(rows) < 15:
            return None
        atr = calculate_atr([float(r.high_price) for r in rows], [float(r.low_price) for r in rows],
                            [float(r.close_price) for r in rows])[-1]
        return atr / float(rows[-1].close_price) * 100 if atr else None

    @staticmethod
    def status() -> dict:
        return {"symbols": sorted(guarded_symbols()), "state": load_state()}
