"""Support-bounce entries for live scans and backtests.

Levels come from the timeframe that matches the holding style:

    INTRADAY        -> 15-minute candles (about 2 weeks)
    WEEKLY          -> 1-hour candles    (about 2-3 months)
    MONTHLY / SWING -> daily candles     (about a year)

The entry itself is judged on the latest COMPLETED 15-minute candle.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import detect_support_resistance
from app.core.config import settings
from app.indicators import calculate_atr
from app.models.market_candle import MarketCandle
from app.schemas.market import MarketTimeframe
from app.strategies.support_bounce import BounceDecision, BounceRules, evaluate_bounce
from app.trading.holding_style import HoldingStyle, parse_style

LEVEL_TIMEFRAME = {
    HoldingStyle.INTRADAY: MarketTimeframe.FIFTEEN_MINUTES,
    HoldingStyle.WEEKLY: MarketTimeframe.ONE_HOUR,
    HoldingStyle.MONTHLY: MarketTimeframe.ONE_DAY,
    HoldingStyle.SWING: MarketTimeframe.ONE_DAY,
}
LEVEL_CANDLES = 250


def rules_from_settings() -> BounceRules:
    return BounceRules(
        zone_atr=settings.bounce_zone_atr,
        min_rr=settings.bounce_min_rr,
        min_stop_atr=settings.risk_min_stop_atr,
        min_trend_score=settings.bounce_min_trend_score,
        level_zone_atr=getattr(settings, "bounce_level_zone_atr", 0.0),
        confirm_bars=getattr(settings, "bounce_confirm_bars", 1),
    )


def entry_mode_allows(mode: str, entry_type: str) -> bool:
    mode = (mode or "BOTH").upper()
    return mode == "BOTH" or mode == entry_type


def _candles(db: Session, stock_id: int, timeframe: MarketTimeframe, cutoff: datetime | None, limit: int):
    stmt = (
        select(MarketCandle)
        .where(MarketCandle.stock_id == stock_id, MarketCandle.timeframe == timeframe.value)
        .order_by(MarketCandle.candle_time.desc())
        .limit(limit)
    )
    if cutoff is not None:
        stmt = stmt.where(MarketCandle.candle_time <= cutoff)
    rows = list(db.scalars(stmt).all())
    rows.reverse()
    return rows


class SupportBounceService:

    @staticmethod
    def evaluate(
        db: Session,
        stock,
        *,
        holding_style: str | None,
        trend_score: float | None,
        cutoffs: dict[str, datetime | None] | None = None,
        rules: BounceRules | None = None,
    ) -> dict:
        """cutoffs: latest COMPLETED candle start per timeframe value
        ('15Min', '1Hour', '1Day'); prevents using a forming candle."""
        cutoffs = cutoffs or {}
        style = parse_style(holding_style)
        level_tf = LEVEL_TIMEFRAME[style]

        entry_candles = _candles(
            db, stock.stock_id, MarketTimeframe.FIFTEEN_MINUTES,
            cutoffs.get(MarketTimeframe.FIFTEEN_MINUTES.value), 120,
        )
        if len(entry_candles) < 20:
            return {"triggered": False, "reasons": ["Not enough 15-minute candles"]}

        level_candles = _candles(
            db, stock.stock_id, level_tf, cutoffs.get(level_tf.value), LEVEL_CANDLES
        )
        if len(level_candles) < 20:
            return {"triggered": False, "reasons": [f"Not enough {level_tf.value} candles for levels"]}

        def series(rows, attr):
            return [float(getattr(r, attr)) for r in rows]

        level_atr = calculate_atr(
            highs=series(level_candles, "high_price"),
            lows=series(level_candles, "low_price"),
            closes=series(level_candles, "close_price"),
            period=14,
        )[-1]
        detected = detect_support_resistance(
            highs=series(level_candles, "high_price"),
            lows=series(level_candles, "low_price"),
            closes=series(level_candles, "close_price"),
            atr=level_atr,
            swing_window=3,
            cluster_threshold_atr=0.35,
            max_levels=8,
        )
        levels = [lvl.price for lvl in detected["supports"]] + [lvl.price for lvl in detected["resistances"]]

        entry_atr = calculate_atr(
            highs=series(entry_candles, "high_price"),
            lows=series(entry_candles, "low_price"),
            closes=series(entry_candles, "close_price"),
            period=14,
        )[-1]
        last = entry_candles[-1]
        decision: BounceDecision = evaluate_bounce(
            open_=float(last.open_price),
            high=float(last.high_price),
            low=float(last.low_price),
            close=float(last.close_price),
            levels=levels,
            atr=entry_atr,
            trend_score=trend_score,
            rules=rules or rules_from_settings(),
            level_atr=level_atr,
            prev_lows=[float(c.low_price) for c in reversed(entry_candles[-3:-1])],
        )
        return {
            "triggered": decision.triggered,
            "reasons": decision.reasons,
            "entry_type": "SUPPORT_BOUNCE",
            "holding_style": style.value,
            "level_timeframe": level_tf.value,
            "candle_time": last.candle_time,
            "support": decision.support,
            "resistance": decision.resistance,
            "entry_atr": entry_atr,
            "level_atr": level_atr,
            "trend_score": trend_score,
            "entry": decision.entry,
            "stop_loss": decision.stop_loss,
            "target_1": decision.target_1,
            "target_2": decision.target_2,
            "rr_1": decision.rr_1,
            "levels": sorted(round(x, 4) for x in levels),
        }

    @staticmethod
    def as_setup(bounce: dict, base_setup: dict) -> dict:
        """Shape a triggered bounce like a setup, so the normal paper-trading
        path (all safety checks, sizing, bracket order, holding-style exits)
        is reused unchanged."""
        return {
            **base_setup,
            "entry_type": "SUPPORT_BOUNCE",
            "action": "BUY_SUPPORT_BOUNCE",
            "actionable": True,
            "decision_reasons": bounce["reasons"],
            "signal_lifecycle": {
                **(base_setup.get("signal_lifecycle") or {}),
                "state": "ENTRY_CONFIRMED",
            },
            "risk_reward": {
                "available": True,
                "entry": bounce["entry"],
                "stop_loss": bounce["stop_loss"],
                "target_1": bounce["target_1"],
                "target_2": bounce["target_2"],
                "rr_1": bounce["rr_1"],
                "quality": "GOOD",
            },
        }
