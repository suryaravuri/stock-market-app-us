"""One record per stock per scan: did the bot buy, and if not, why not.

Every scan (manual or from the trading cycle) calls DecisionLog.record()
for each stock. The record is

  * written as one readable INFO line to the console / logs/trading.log
  * appended as JSON to logs/decisions.jsonl (rotated at 10 MB)
  * kept in memory (last 3000) for GET /api/v1/diagnostics/decisions

`blocker` is the single most important reason no order was placed, in the
order a trader would check things:

  DATA_BLOCKED:*            candles missing / stale
  ANALYSIS_FAILED:*         setup could not be computed
  SWITCH_OFF:*              a .env switch (AUTO/PAPER/TRADING/LIVE)
  INDIAN_STOCK_NOT_AUTO_TRADED
  TRADING_NOT_ENABLED_FOR_STOCK   watchlist_stock.trading_enabled = false
  MAX_ENTRIES_PER_DAY_REACHED:*  already traded this stock today
  LIVE_CHECK_FAILED:*       signal fired but the live price no longer fits
  MARKET_FILTER:*           SPY/QQQ falling - no new buys
  SECTOR_LIMIT:*            already enough positions in that sector
  ORDER_REJECTED:*          reached the broker step but was refused
                            (safety check, sizing, duplicate order, Alpaca error)
  NO_ENTRY_SIGNAL           neither breakout nor support bounce fired today

`would_buy_if_enabled` is true when the strategy said BUY but a switch or
the per-stock flag stopped it - the most common "silent" no-buy.
"""
from __future__ import annotations

import json
import logging
import threading
from collections import deque
from datetime import date, datetime
from logging.handlers import RotatingFileHandler

from app.core.logging_config import log_dir, setup_logging

logger = logging.getLogger("app.decisions")

_SWITCH_REASONS = {
    "AUTO_TRADING_DISABLED",
    "PAPER_TRADING_DISABLED",
    "LIVE_TRADING_MUST_BE_DISABLED",
}
_RECENT: deque[dict] = deque(maxlen=3000)
_LOCK = threading.Lock()
_json_logger: logging.Logger | None = None


def _jsonable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, float):
        return round(value, 4)
    return value


def _json_sink() -> logging.Logger:
    global _json_logger
    if _json_logger is None:
        sink = logging.getLogger("app.decisions.jsonl")
        sink.propagate = False
        sink.setLevel(logging.INFO)
        for old in list(sink.handlers):
            sink.removeHandler(old)
            old.close()
        try:
            handler = RotatingFileHandler(
                log_dir() / "decisions.jsonl",
                maxBytes=10 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            sink.addHandler(handler)
        except OSError:
            sink.addHandler(logging.NullHandler())
        _json_logger = sink
    return _json_logger


def breakout_summary(setup: dict | None) -> str:
    """Short text: what the breakout strategy thinks right now."""
    if not setup:
        return "no setup"
    lifecycle = setup.get("signal_lifecycle") or {}
    risk = setup.get("risk_reward") or {}
    breakout = setup.get("breakout_confirmation") or {}
    rr = risk.get("rr_1")
    rr_text = f"{rr:.2f}" if isinstance(rr, (int, float)) else "-"
    return (
        f"{setup.get('action') or 'UNAVAILABLE'}"
        f" (signal={lifecycle.get('state') or '-'}"
        f", breakout={breakout.get('status') or '-'}"
        f", rr={risk.get('quality') or '-'} {rr_text})"
    )


def primary_blocker(d: dict) -> str | None:
    """Pure function (unit tested): the main reason no order was placed."""
    if d.get("order_submitted"):
        return None
    if d.get("data_status") and not d.get("eligible", True):
        reasons = d.get("data_reasons") or ["UNKNOWN"]
        return f"DATA_BLOCKED:{reasons[0]}"
    if d.get("analysis_error"):
        return f"ANALYSIS_FAILED:{d['analysis_error']}"

    switches_off = [name for name, on in (d.get("switches") or {}).items() if not on]
    if switches_off:
        return "SWITCH_OFF:" + ",".join(switches_off)
    order_reason = str(d.get("order_reason") or "")
    if order_reason in _SWITCH_REASONS:
        return f"SWITCH_OFF:{order_reason}"

    if d.get("indian_stock"):
        return "INDIAN_STOCK_NOT_AUTO_TRADED"
    if not d.get("trading_enabled"):
        return "TRADING_NOT_ENABLED_FOR_STOCK"
    if d.get("order_attempted"):
        return f"ORDER_REJECTED:{order_reason or 'UNKNOWN'}"
    if order_reason == "TOO_LATE_FOR_INTRADAY_ENTRY" or order_reason.startswith(
        ("MAX_ENTRIES_PER_DAY_REACHED", "LIVE_CHECK_FAILED", "MARKET_CLOSED_NO_NEW_ENTRIES",
         "MARKET_FILTER", "SECTOR_LIMIT", "MANAGED_BY_HOLDINGS_GUARD")
    ):
        return order_reason
    return "NO_ENTRY_SIGNAL"


def strategy_said_buy(d: dict) -> bool:
    return bool(d.get("breakout_ready") or d.get("bounce_triggered"))


class DecisionLog:

    @staticmethod
    def record(decision: dict) -> dict:
        setup_logging()
        decision = dict(decision)
        decision["blocker"] = primary_blocker(decision)
        decision["would_buy_if_enabled"] = bool(
            decision["blocker"] is not None
            and strategy_said_buy(decision)
            and (
                decision["blocker"].startswith("SWITCH_OFF")
                or decision["blocker"] == "TRADING_NOT_ENABLED_FOR_STOCK"
            )
        )
        decision["outcome"] = "ORDER_SUBMITTED" if decision.get("order_submitted") else "NO_ORDER"
        record = _jsonable(decision)

        with _LOCK:
            _RECENT.append(record)
        try:
            _json_sink().info(json.dumps(record, default=str))
        except Exception:  # noqa: BLE001 - logging must never break a scan
            pass

        if record["outcome"] == "ORDER_SUBMITTED":
            logger.info(
                "BUY  %-8s %s order_id=%s",
                record.get("symbol"), record.get("entry_type"), record.get("order_id"),
            )
        else:
            level = logging.WARNING if record["would_buy_if_enabled"] else logging.INFO
            logger.log(
                level,
                "SKIP %-8s blocker=%s | breakout=%s | bounce=%s%s",
                record.get("symbol"),
                record["blocker"],
                record.get("breakout_summary"),
                record.get("bounce_summary"),
                " | WOULD HAVE BOUGHT" if record["would_buy_if_enabled"] else "",
            )
        return record

    @staticmethod
    def recent(symbol: str | None = None, limit: int = 200, only_blocked: bool = False) -> list[dict]:
        with _LOCK:
            items = list(_RECENT)
        if not items:
            items = DecisionLog._read_file()
        if symbol:
            wanted = symbol.strip().upper()
            items = [i for i in items if str(i.get("symbol", "")).upper() == wanted]
        if only_blocked:
            items = [i for i in items if i.get("outcome") != "ORDER_SUBMITTED"]
        return list(reversed(items[-limit:]))

    @staticmethod
    def _read_file(max_lines: int = 3000) -> list[dict]:
        """After a restart memory is empty; fall back to the JSON file."""
        path = log_dir() / "decisions.jsonl"
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()[-max_lines:]
        except OSError:
            return []
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    @staticmethod
    def blocker_counts(items: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            key = str(item.get("blocker") or "ORDER_SUBMITTED").split(":")[0]
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    @staticmethod
    def _clear_for_tests() -> None:
        with _LOCK:
            _RECENT.clear()
