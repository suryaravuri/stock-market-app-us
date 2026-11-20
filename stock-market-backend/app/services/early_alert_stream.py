"""Alpaca 1-minute bar stream: early-breakout alerts + live bounce entries.

Starts when EARLY_ALERTS_ENABLED=true (alerts only) and/or
LIVE_BOUNCE_ENABLED=true (support-bounce paper orders within minutes,
see live_bounce_service.py).

Enable alerts with EARLY_ALERTS_ENABLED=true. On startup it subscribes to Alpaca
1-minute bars for every active, analysis-enabled US stock in any watchlist,
builds the forming 15-minute candle, and records a MarketAlert when the
early-breakout rules trigger (app.trading.early_breakout).

Notes:
  * Needs the backend running during market hours; restart it after changing
    watchlists so the subscription picks up new symbols.
  * The free Alpaca plan allows one market-data websocket connection.
  * Breakout levels come from the stored 15-minute candles, so keep the
    trading-cycle scheduler (market-data sync) running too.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.indicators.atr import calculate_atr
from app.market.sessions import US_SESSION, is_indian_exchange
from app.models.market_candle import MarketCandle
from app.models.stock import Stock
from app.models.watchlist import WatchlistStock
from app.schemas.market import MarketTimeframe
from app.services.breakout_service import BreakoutService
from app.services import live_bounce_service
from app.services.market_alert_service import MarketAlertService
from app.trading.early_breakout import (
    Baseline,
    EarlyRules,
    FormingCandle,
    baseline_is_current,
    bucket_start,
    evaluate,
)

logger = logging.getLogger(__name__)

_BASELINE_RETRY = timedelta(seconds=60)


def _load_symbols() -> list[str]:
    db = SessionLocal()
    try:
        rows = db.execute(
            select(Stock.symbol, Stock.exchange, WatchlistStock.trading_enabled,
                   WatchlistStock.priority)
            .join(WatchlistStock, WatchlistStock.stock_id == Stock.stock_id)
            .where(Stock.active.is_(True), WatchlistStock.analysis_enabled.is_(True))
        ).all()
        best: dict[str, tuple] = {}
        for symbol, exchange, trading, priority in rows:
            if is_indian_exchange(exchange):
                continue
            key = (bool(trading), priority or 0)
            if symbol not in best or key > best[symbol]:
                best[symbol] = key
        ranked = sorted(best, key=lambda s: (not best[s][0], -best[s][1], s))
        limit = max(1, int(getattr(settings, "live_stream_max_symbols", 30) or 30))
        if len(ranked) > limit:
            logger.warning(
                "1-minute stream: %d symbols, streaming the top %d (LIVE_STREAM_MAX_SYMBOLS); "
                "not streamed: %s", len(ranked), limit, ", ".join(ranked[limit:]))
        return sorted(ranked[:limit])
    finally:
        db.close()


def _build_baseline(symbol: str, forming_start: datetime) -> Baseline | None:
    """Breakout level and average volume from the previous 20 completed candles."""
    lookback = BreakoutService.LOOKBACK
    db = SessionLocal()
    try:
        stock = db.scalar(select(Stock).where(Stock.symbol == symbol))
        if stock is None:
            return None
        recent = list(db.scalars(
            select(MarketCandle)
            .where(
                MarketCandle.stock_id == stock.stock_id,
                MarketCandle.timeframe == MarketTimeframe.FIFTEEN_MINUTES.value,
                MarketCandle.candle_time < forming_start,
            )
            .order_by(MarketCandle.candle_time.desc())
            .limit(lookback + 100)
        ).all())
    finally:
        db.close()

    recent.reverse()
    eligible = [c for c in recent if BreakoutService._base_eligible(c, US_SESSION)]
    if len(eligible) < lookback:
        return None
    atr = calculate_atr(
        highs=[float(c.high_price) for c in eligible],
        lows=[float(c.low_price) for c in eligible],
        closes=[float(c.close_price) for c in eligible],
        period=14,
    )[-1]
    if not atr:
        return None
    prior = eligible[-lookback:]
    volumes = [float(c.volume or 0) for c in prior if (c.volume or 0) > 0]
    if not volumes:
        return None
    return Baseline(
        confirmation_price=max(float(c.high_price) for c in prior) + atr * BreakoutService.ATR_BUFFER,
        average_volume=sum(volumes) / len(volumes),
        last_completed_start=eligible[-1].candle_time,
    )


class EarlyAlertStream:

    def __init__(self) -> None:
        self.rules = EarlyRules(
            min_volume_ratio=BreakoutService.MIN_VOLUME_RATIO,
            min_elapsed_minutes=settings.early_alert_min_elapsed_minutes,
            min_close_location=BreakoutService.MIN_CLOSE_LOCATION,
        )
        self._candles: dict[str, FormingCandle] = {}
        self._baselines: dict[tuple[str, datetime], tuple[Baseline | None, datetime]] = {}
        self._alerted: set[tuple[str, datetime]] = set()
        self._stream = None
        self._thread: threading.Thread | None = None
        self.symbols: list[str] = []
        self._minutes = live_bounce_service.MinuteAggregator(
            minutes=max(1, int(settings.live_bounce_bar_minutes))
        )

    # ---------------------------------------------------------- lifecycle
    def start(self) -> None:
        wanted = settings.early_alerts_enabled or settings.live_bounce_enabled
        if not wanted or (self._thread and self._thread.is_alive()):
            if not wanted:
                logger.info("1-minute stream off (EARLY_ALERTS_ENABLED and LIVE_BOUNCE_ENABLED are false)")
            return
        from alpaca.data.enums import DataFeed
        from alpaca.data.live import StockDataStream

        self.symbols = _load_symbols()
        if not self.symbols:
            logger.warning("Early alerts enabled but no analysis-enabled US stocks in any watchlist")
            return
        self._stream = StockDataStream(
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
            feed=DataFeed(settings.alpaca_data_feed.lower()),
        )
        self._stream.subscribe_bars(self._on_bar, *self.symbols)
        self._thread = threading.Thread(target=self._run, name="early-alert-stream", daemon=True)
        self._thread.start()
        logger.info(
            "1-minute stream started for %d symbols (early alerts=%s, live bounce=%s every %s min)",
            len(self.symbols), settings.early_alerts_enabled, settings.live_bounce_enabled,
            settings.live_bounce_bar_minutes,
        )

    def _run(self) -> None:
        try:
            self._stream.run()
        except Exception:  # noqa: BLE001
            logger.exception("Early alert stream stopped with an error")

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
            except Exception:  # noqa: BLE001
                logger.warning("Early alert stream did not stop cleanly", exc_info=True)

    # ------------------------------------------------------------- bars
    async def _on_bar(self, bar) -> None:
        try:
            ts = bar.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if not US_SESSION.is_regular(ts):
                return
            symbol = str(bar.symbol).upper()
            live_bounce_service.set_live_price(symbol, bar.close, ts + timedelta(minutes=1))

            if settings.live_bounce_enabled:
                for done in self._minutes.add(symbol, ts, bar.open, bar.high, bar.low,
                                              bar.close, bar.volume):
                    await asyncio.to_thread(
                        live_bounce_service.handle_completed_candle, symbol, done
                    )

            if not settings.early_alerts_enabled:
                return
            start = bucket_start(ts)

            candle = self._candles.get(symbol)
            if candle is None or candle.start != start:
                candle = FormingCandle.from_bar(start, ts, bar.open, bar.high, bar.low, bar.close, bar.volume)
                self._candles[symbol] = candle
            else:
                candle.add(ts, bar.open, bar.high, bar.low, bar.close, bar.volume)

            key = (symbol, start)
            if key in self._alerted or candle.elapsed_minutes < self.rules.min_elapsed_minutes:
                return

            baseline = await self._baseline(symbol, start)
            if baseline is None:
                return
            signal = evaluate(candle, baseline, self.rules)
            if not signal.triggered:
                return

            self._alerted.add(key)
            message = (
                f"Early breakout: {symbol} {candle.close:.2f} above {baseline.confirmation_price:.2f}, "
                f"projected volume {signal.projected_volume_ratio:.2f}x after "
                f"{candle.elapsed_minutes} min. Alert only - wait for the candle to close."
            )
            await asyncio.to_thread(
                self._save, symbol, start, candle.close, baseline.confirmation_price,
                signal.projected_volume_ratio, message, signal.reasons,
            )
            logger.info(message)
        except Exception:  # noqa: BLE001 - never kill the stream on one bad bar
            logger.exception("Early alert processing failed")

    async def _baseline(self, symbol: str, start: datetime) -> Baseline | None:
        now = datetime.now(timezone.utc)
        cached = self._baselines.get((symbol, start))
        if cached:
            baseline, fetched_at = cached
            if baseline is not None and baseline_is_current(baseline, start):
                return baseline
            if now - fetched_at < _BASELINE_RETRY:
                return None
        baseline = await asyncio.to_thread(_build_baseline, symbol, start)
        # keep only the current candle's entries
        self._baselines = {k: v for k, v in self._baselines.items() if k[1] >= start}
        self._baselines[(symbol, start)] = (baseline, now)
        if baseline is None or not baseline_is_current(baseline, start):
            return None
        return baseline

    @staticmethod
    def _save(symbol, start, price, level, ratio, message, reasons) -> None:
        db = SessionLocal()
        try:
            MarketAlertService.record(
                db,
                source="EARLY_BREAKOUT",
                symbol=symbol,
                candle_start=start,
                price=price,
                level=level,
                volume_ratio=ratio,
                message=message,
                payload={"reasons": reasons},
            )
        finally:
            db.close()


early_alert_stream = EarlyAlertStream()
