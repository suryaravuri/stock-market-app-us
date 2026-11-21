"""Phone alerts through Telegram.

Setup (once):
  1. In Telegram, talk to @BotFather -> /newbot -> copy the bot token.
  2. Send any message (e.g. "hi") to your new bot.
  3. Put TELEGRAM_BOT_TOKEN in .env, then run
         python -m app.scripts.telegram_chat_id
     and put the printed TELEGRAM_CHAT_ID in .env. Restart the backend.

What you get:
  * BUY        when a paper order is placed
  * SELL       when a position closes (target, stop, trailing stop, time exit),
               with the trade's P&L
  * HOLDINGS   when the Holdings Guard sells or buys back
  * PROBLEM    when a cycle crashes, or no cycle succeeded for 35 min in
               market hours (stale data / stuck bot)
  * READY      at 9:20 AM ET on trading days: the bot is up and healthy.
               If this doesn't arrive, the bot is not running.
  * SUMMARY    at 4:25 PM ET: today's closed trades and P&L.

Sending never blocks or breaks trading: messages go out on a background
thread, failures are only logged, and repeated problems are rate-limited.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone

from app.core.config import settings
from app.core.logging_config import log_dir

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_last_sent: dict[str, float] = {}


def enabled() -> bool:
    return bool(
        getattr(settings, "alerts_enabled", True)
        and getattr(settings, "telegram_bot_token", "")
        and getattr(settings, "telegram_chat_id", "")
    )


def _post(text: str) -> bool:
    import requests

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        response = requests.post(
            url,
            json={"chat_id": settings.telegram_chat_id, "text": text[:4000],
                  "disable_web_page_preview": True},
            timeout=10,
        )
        if response.status_code != 200:
            # Never log the URL: it contains the bot token.
            logger.warning("Telegram alert failed: HTTP %s %s", response.status_code,
                           response.text[:200])
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram alert failed: %s", type(exc).__name__)
        return False


def send(text: str, *, key: str | None = None, cooldown_minutes: float = 0,
         wait: bool = False) -> bool:
    """Send a message. With key + cooldown, the same alert is sent at most
    once per cooldown. wait=True sends synchronously (tests, test endpoint)."""
    if not enabled():
        return False
    if key and cooldown_minutes > 0:
        now = time.monotonic()
        with _lock:
            last = _last_sent.get(key)
            if last is not None and now - last < cooldown_minutes * 60:
                return False
            _last_sent[key] = now
    if wait:
        return _post(text)
    threading.Thread(target=_post, args=(text,), name="telegram-alert", daemon=True).start()
    return True


# ------------------------------------------------------------- formatting
def _money(value: float | None) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def format_buy(symbol: str, result: dict, setup: dict | None) -> str:
    risk = (setup or {}).get("risk_reward") or {}
    entry_type = (setup or {}).get("entry_type") or result.get("entry_type") or "BREAKOUT"
    lines = [
        f"🟢 BUY {symbol} x{result.get('shares') or result.get('qty') or '?'} ({entry_type})",
        f"Entry ~{risk.get('entry')}  Stop {risk.get('stop_loss')}  Target {risk.get('target_1')}",
    ]
    if risk.get("rr_1") is not None:
        lines.append(f"Reward/risk {risk.get('rr_1')}")
    return "\n".join(lines)


def format_sell(trade: dict, exit_kind: str | None) -> str:
    pnl = trade.get("pnl")
    icon = "✅" if (pnl or 0) > 0 else "🔴"
    kind = f" ({exit_kind})" if exit_kind else ""
    return (
        f"{icon} SELL {trade['symbol']} x{trade['qty']:g}{kind}\n"
        f"{trade['entry_price']:.2f} -> {trade['exit_price']:.2f}  "
        f"P&L {_money(pnl)} ({trade.get('pnl_pct')}%)"
    )


def format_summary(trades: list[dict], open_positions: list[dict], day_label: str) -> str:
    realized = sum(t["pnl"] for t in trades)
    wins = sum(1 for t in trades if t["pnl"] > 0)
    unrealized = sum(p.get("unrealized_pnl", 0) for p in open_positions)
    lines = [f"📊 {day_label} summary",
             f"Closed trades: {len(trades)} ({wins} won)  Realized {_money(realized)}"]
    if trades:
        best = max(trades, key=lambda t: t["pnl"])
        worst = min(trades, key=lambda t: t["pnl"])
        lines.append(f"Best {best['symbol']} {_money(best['pnl'])}  Worst {worst['symbol']} {_money(worst['pnl'])}")
    lines.append(f"Open positions: {len(open_positions)}  Unrealized {_money(unrealized)}")
    return "\n".join(lines)


# --------------------------------------------------------------- state
def _state_path():
    return log_dir() / "alerts_state.json"


def load_state() -> dict:
    try:
        return json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    try:
        path = _state_path()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        logger.warning("Alert state not saved: %s", exc)


# ------------------------------------------------- closed-trade watcher
def check_closed_trades(now: datetime | None = None) -> int:
    """Alert for every round trip that closed since the last check.
    Called from each US trading cycle. Returns the number of alerts sent."""
    if not enabled():
        return 0
    from datetime import timedelta

    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    from app.analytics.performance import Fill, round_trips
    from app.brokers.alpaca.trading_client import AlpacaPaperTradingClient

    now = now or datetime.now(timezone.utc)
    state = load_state()
    since = state.get("last_fill_check")
    if not since:  # first run: start from now, don't replay history
        state["last_fill_check"] = now.isoformat()
        save_state(state)
        return 0
    since_dt = datetime.fromisoformat(since)

    client = AlpacaPaperTradingClient()
    orders = client.client.get_orders(filter=GetOrdersRequest(
        status=QueryOrderStatus.CLOSED, after=now - timedelta(days=30), limit=500, nested=False,
    ))
    fills, kinds = [], {}
    for o in orders:
        qty = float(o.filled_qty or 0)
        if qty <= 0 or not o.filled_avg_price or not o.filled_at:
            continue
        side = str(getattr(o.side, "value", o.side)).lower()
        filled_at = o.filled_at if o.filled_at.tzinfo else o.filled_at.replace(tzinfo=timezone.utc)
        fills.append(Fill(str(o.symbol).upper(), side, qty, float(o.filled_avg_price), filled_at))
        if side == "sell":
            kinds[(str(o.symbol).upper(), filled_at)] = str(getattr(o.type, "value", o.type)).replace("_", " ")

    sent = 0
    for trade in round_trips(fills):
        if trade["exit_time"] > since_dt:
            kind = kinds.get((trade["symbol"], trade["exit_time"]))
            label = {"stop": "stop loss", "limit": "target", "trailing stop": "trailing stop",
                     "market": "market/time exit"}.get(kind or "", kind)
            send(format_sell(trade, label))
            sent += 1
    state["last_fill_check"] = now.isoformat()
    save_state(state)
    return sent


# ------------------------------------------------------------- watchdog
class AlertWatchdog:
    """Background checks that work even when the trading cycle is stuck."""

    STALE_MINUTES = 35

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not enabled() or (self._thread and self._thread.is_alive()):
            if not enabled():
                logger.info("Telegram alerts off (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set)")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="alert-watchdog", daemon=True)
        self._thread.start()
        send("🤖 Trading bot started")
        logger.info("Telegram alerts on")

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(timeout=60):
            try:
                self.tick(datetime.now(timezone.utc))
            except Exception:  # noqa: BLE001
                logger.exception("Alert watchdog tick failed")

    def tick(self, now: datetime) -> None:
        from app.core import local_scheduler
        from app.market.sessions import US_SESSION
        from app.services.trading_cycle_service import TradingCycleService

        local = now.astimezone(US_SESSION.tz)
        today = local.date()
        if not US_SESSION.is_session_day(today):
            return
        state = load_state()
        hhmm = local.strftime("%H:%M")

        # Morning "ready" message.
        if "09:20" <= hhmm < "09:30" and state.get("ready_sent") != today.isoformat():
            alive = local_scheduler.is_alive()
            send(("✅ Bot ready for today's open" if alive
                  else "⚠️ Bot is running but its scheduler is NOT - check the backend"))
            state["ready_sent"] = today.isoformat()
            save_state(state)

        # Stuck / stale: no successful cycle for a while during market hours.
        if TradingCycleService.market_window_open(US_SESSION, now) and "09:50" <= hhmm:
            last_ok = local_scheduler.STATE.get("last_ok_at")
            age = (now - last_ok).total_seconds() / 60 if last_ok else None
            if age is None or age > self.STALE_MINUTES:
                send(f"⚠️ No successful trading cycle for "
                     f"{'ever' if age is None else f'{age:.0f} min'} - data will go stale. "
                     f"Last error: {str(local_scheduler.STATE.get('last_error') or '-').strip().splitlines()[-1][:200]}",
                     key="stale", cooldown_minutes=60)

        # End-of-day summary.
        if "16:25" <= hhmm < "16:35" and state.get("summary_sent") != today.isoformat():
            state["summary_sent"] = today.isoformat()
            save_state(state)
            self._send_summary(local)

    @staticmethod
    def _send_summary(local_now: datetime) -> None:
        try:
            from app.services.performance_service import PerformanceService

            report = PerformanceService.pnl_report("day", "1M")
            today = local_now.date()
            trades = [t for t in report["trades"]
                      if t["exit_time"].astimezone(local_now.tzinfo).date() == today]
            send(format_summary(trades, report["open_positions"], local_now.strftime("%a %b %d")))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Daily summary failed: %s", exc)


watchdog = AlertWatchdog()
