"""Two checks before any automatic buy, for volatile markets.

1. Market mood: don't buy bounces while the broad market (SPY, QQQ) is
   falling - bounces in a falling market usually fail (NXPI 2026-11-16).
2. Sector limit: at most N open positions per sector, so one bad sector
   day (chips, 2026-11-16) can't hit five trades at once.

Both are called from AutoPaperExecutionService under its order lock and
apply to every entry type (breakout, 15-min bounce, live bounce).
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from app.core.config import settings
from app.market.sectors import sector_for

logger = logging.getLogger(__name__)


# ------------------------------------------------------------ pure logic
@dataclass
class IndexMove:
    symbol: str
    prev_close: float
    open: float
    last: float

    @property
    def day_pct(self) -> float:
        return (self.last / self.prev_close - 1) * 100 if self.prev_close else 0.0

    @property
    def from_open_pct(self) -> float:
        return (self.last / self.open - 1) * 100 if self.open else 0.0


def evaluate_market_mood(
    moves: list[IndexMove], max_day_drop_pct: float, max_from_open_drop_pct: float
) -> tuple[bool, str]:
    """(ok, reason). Not ok if any index is down too much."""
    if not moves:
        return False, "MARKET_FILTER:NO_INDEX_DATA"
    for m in moves:
        if m.day_pct <= -abs(max_day_drop_pct):
            return False, f"MARKET_FILTER:{m.symbol} {m.day_pct:+.2f}% today"
        if m.from_open_pct <= -abs(max_from_open_drop_pct):
            return False, f"MARKET_FILTER:{m.symbol} {m.from_open_pct:+.2f}% since open"
    summary = ", ".join(f"{m.symbol} {m.day_pct:+.2f}%" for m in moves)
    return True, f"Market OK ({summary})"


def evaluate_sector_limit(
    symbol: str,
    sector: str,
    held_symbols: set[str],
    sector_of,
    max_per_sector: int,
) -> tuple[bool, str]:
    """(ok, reason). held_symbols = open positions + pending buy orders."""
    if max_per_sector <= 0 or sector == "UNKNOWN":
        return True, f"Sector {sector}: no limit"
    same = sorted(s for s in held_symbols if s != symbol and sector_of(s) == sector)
    if len(same) >= max_per_sector:
        return False, f"SECTOR_LIMIT:{sector} already {len(same)} ({', '.join(same)})"
    return True, f"Sector {sector}: {len(same)}/{max_per_sector} used"


# ------------------------------------------------------------ live data
_mood_cache: dict = {"at": 0.0, "value": None}
_mood_lock = threading.Lock()
_MOOD_TTL_SECONDS = 60


def _fetch_moves(symbols: list[str]) -> list[IndexMove]:
    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockSnapshotRequest

    client = StockHistoricalDataClient(settings.alpaca_api_key, settings.alpaca_secret_key)
    snaps = client.get_stock_snapshot(
        StockSnapshotRequest(symbol_or_symbols=symbols, feed=DataFeed.IEX)
    )
    moves = []
    for symbol in symbols:
        snap = snaps.get(symbol) if isinstance(snaps, dict) else None
        if not snap or not snap.daily_bar or not snap.previous_daily_bar:
            continue
        last = snap.latest_trade.price if snap.latest_trade else snap.daily_bar.close
        moves.append(IndexMove(symbol, float(snap.previous_daily_bar.close),
                               float(snap.daily_bar.open), float(last)))
    return moves


def market_mood() -> tuple[bool, str]:
    """Cached for 60 s. Fails closed: no index data -> no new buys."""
    if not settings.market_filter_enabled:
        return True, "Market filter disabled"
    with _mood_lock:
        if _mood_cache["value"] and time.monotonic() - _mood_cache["at"] < _MOOD_TTL_SECONDS:
            return _mood_cache["value"]
    symbols = [s.strip().upper() for s in settings.market_filter_symbols.split(",") if s.strip()]
    try:
        moves = _fetch_moves(symbols)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Market filter: index data unavailable: %s", exc)
        moves = []
    value = evaluate_market_mood(
        moves, settings.market_filter_max_day_drop_pct, settings.market_filter_max_from_open_drop_pct
    )
    with _mood_lock:
        _mood_cache.update({"at": time.monotonic(), "value": value})
    if not value[0]:
        logger.info("Market filter blocking new buys: %s", value[1])
    return value


def sector_check(symbol: str, db_sector: str | None) -> tuple[bool, str]:
    limit = int(settings.max_open_positions_per_sector or 0)
    sector = sector_for(symbol, db_sector)
    if limit <= 0:
        return True, f"Sector {sector}: limit off"
    try:
        from app.brokers.alpaca.trading_client import AlpacaPaperTradingClient

        client = AlpacaPaperTradingClient()
        held = {str(p.symbol).upper() for p in client.get_open_positions()}
        for order in client.get_open_orders():
            if str(getattr(order, "side", "")).lower().endswith("buy"):
                held.add(str(order.symbol).upper())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Sector check: positions unavailable: %s", exc)
        return False, "SECTOR_LIMIT:POSITIONS_UNAVAILABLE"
    return evaluate_sector_limit(symbol.upper(), sector, held, sector_for, limit)
