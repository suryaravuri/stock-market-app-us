"""Breakout diagnostics for one stock: why a breakout was / wasn't confirmed."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.indicators.atr import calculate_atr
from app.market.sessions import is_indian_exchange, session_for_stock
from app.models.market_candle import MarketCandle
from app.repositories.stock_repository import StockRepository
from app.schemas.market import MarketTimeframe
from app.services.breakout_service import BreakoutService
from app.trading.breakout_diagnostics import Thresholds, diagnose, summarize


class BreakoutDiagnosticsService:

    @staticmethod
    def analyze(db: Session, symbol: str, rows: int = 30) -> dict:
        stock = StockRepository.find_by_symbol(db, symbol.strip().upper())
        if stock is None:
            raise ValueError(f"Stock not found: {symbol}")
        session = session_for_stock(stock)

        thresholds = Thresholds(
            lookback=BreakoutService.LOOKBACK,
            atr_buffer=BreakoutService.ATR_BUFFER,
            min_volume_ratio=BreakoutService.MIN_VOLUME_RATIO,
            min_body_ratio=BreakoutService.MIN_BODY_RATIO,
            min_close_location=BreakoutService.MIN_CLOSE_LOCATION,
            max_upper_wick_ratio=BreakoutService.MAX_UPPER_WICK_RATIO,
        )

        fetch = rows + thresholds.lookback + 80   # extra history for ATR warm-up
        recent = list(db.scalars(
            select(MarketCandle)
            .where(
                MarketCandle.stock_id == stock.stock_id,
                MarketCandle.timeframe == MarketTimeframe.FIFTEEN_MINUTES.value,
            )
            .order_by(MarketCandle.candle_time.desc())
            .limit(fetch)
        ).all())
        recent.reverse()

        # Same eligibility as the strategy (regular session, valid, non-zero range...).
        eligible = [c for c in recent if BreakoutService._base_eligible(c, session)]
        if len(eligible) <= thresholds.lookback:
            raise ValueError(
                f"Not enough 15-minute candles for {stock.symbol}; run the market-data sync first"
            )

        atr = calculate_atr(
            highs=[float(c.high_price) for c in eligible],
            lows=[float(c.low_price) for c in eligible],
            closes=[float(c.close_price) for c in eligible],
            period=14,
        )
        candles = [
            {
                "time": session.local(c.candle_time).strftime("%a %d %b %H:%M"),
                "open": c.open_price,
                "high": c.high_price,
                "low": c.low_price,
                "close": c.close_price,
                "volume": c.volume or 0,
            }
            for c in eligible
        ]
        diagnosed = diagnose(candles, atr, rows=rows, thresholds=thresholds)
        diagnosed.reverse()  # newest first for display

        feed = "Zerodha (NSE/BSE)" if is_indian_exchange(stock.exchange) else (
            f"Alpaca {settings.alpaca_data_feed.upper()}"
        )
        feed_note = (
            "IEX is a single exchange carrying only a small share of total US volume, "
            "so volume and volume ratios here can differ a lot from charts that show "
            "consolidated volume from all exchanges."
            if settings.alpaca_data_feed.lower() == "iex" and not is_indian_exchange(stock.exchange)
            else None
        )

        return {
            "symbol": stock.symbol,
            "timeframe": MarketTimeframe.FIFTEEN_MINUTES.value,
            "session_timezone": session.timezone_name,
            "data_feed": feed,
            "data_feed_note": feed_note,
            "rules": {
                "lookback_candles": thresholds.lookback,
                "breakout_level": f"highest high of the previous {thresholds.lookback} candles",
                "confirmation_buffer": f"{thresholds.atr_buffer:.0%} of ATR(14) above the level",
                "min_volume_ratio": thresholds.min_volume_ratio,
                "min_body_ratio": thresholds.min_body_ratio,
                "min_close_location": thresholds.min_close_location,
                "max_upper_wick_ratio": thresholds.max_upper_wick_ratio,
                "note": "A confirmed breakout still needs the NEXT completed candle to hold "
                        "the level (follow-through) before the setup becomes actionable.",
            },
            "summary": summarize(diagnosed, thresholds),
            "candles": diagnosed,
        }
