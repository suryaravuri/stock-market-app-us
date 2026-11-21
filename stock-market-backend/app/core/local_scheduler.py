"""In-process scheduler for running the trading cycle without Cloud Scheduler.

Enable with LOCAL_SCHEDULER_ENABLED=true in .env. Every
LOCAL_SCHEDULER_INTERVAL_MINUTES (default 15) - aligned to the clock, one
minute after each boundary so the just-finished candle is available - it
runs TradingCycleService for all markets. The cycle itself decides whether
a market is open, and its PostgreSQL advisory lock prevents overlaps.

Notes:
  * Runs only while this backend process is running (laptop on, uvicorn up).
  * Enable it in ONE process only. With `uvicorn --reload` the reloader's
    parent process doesn't run startup hooks, so that is fine.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging_config import setup_logging

logger = logging.getLogger(__name__)

_OFFSET = timedelta(minutes=1)
_stop = threading.Event()
_thread: threading.Thread | None = None

# Heartbeat for GET /api/v1/diagnostics/trading-readiness
STATE: dict = {
    "enabled": False,
    "interval_minutes": None,
    "started_at": None,
    "next_run_at": None,
    "last_run_at": None,
    "last_ok_at": None,
    "last_error": None,
    "runs": 0,
    "failures": 0,
}


def is_alive() -> bool:
    return bool(_thread and _thread.is_alive())


def next_run_after(now: datetime, interval_minutes: int) -> datetime:
    """Next clock-aligned boundary (e.g. :00, :15, :30, :45) plus the offset."""
    interval = max(1, interval_minutes)
    floored = now.replace(second=0, microsecond=0) - timedelta(minutes=now.minute % interval)
    candidate = floored + _OFFSET
    while candidate <= now:
        candidate += timedelta(minutes=interval)
    return candidate


def _run_once() -> None:
    # Imported here so app startup doesn't import the whole trading stack twice.
    from app.services.trading_cycle_service import TradingCycleService

    STATE["last_run_at"] = datetime.now(timezone.utc)
    STATE["runs"] += 1
    db = SessionLocal()
    try:
        result = TradingCycleService.run(db=db)
        STATE["last_ok_at"] = datetime.now(timezone.utc)
        STATE["last_error"] = None
        logger.info(
            "Local scheduler cycle: ran=%s reason=%s markets_open=%s paper_orders=%s",
            result.get("ran"),
            result.get("reason"),
            result.get("markets_open"),
            result.get("paper_orders_submitted"),
        )
    except Exception:  # noqa: BLE001 - never let the scheduler thread die
        logger.exception("Local scheduler cycle failed")
        STATE["failures"] += 1
        import traceback
        STATE["last_error"] = traceback.format_exc(limit=3)[-1500:]
        from app.services import alert_service

        alert_service.send(
            "❌ Trading cycle crashed: " + STATE["last_error"].strip().splitlines()[-1][:300],
            key="cycle_crash", cooldown_minutes=30,
        )
        try:
            db.rollback()
        except Exception:  # noqa: BLE001 - connection may be dead
            pass
    finally:
        db.close()


def _loop() -> None:
    interval = settings.local_scheduler_interval_minutes
    logger.info("Local scheduler started (every %s min)", interval)
    while not _stop.is_set():
        now = datetime.now(timezone.utc)
        next_run = next_run_after(now, interval)
        STATE["next_run_at"] = next_run
        logger.debug("Local scheduler: next cycle at %s", next_run.isoformat())
        wait = (next_run - now).total_seconds()
        if _stop.wait(timeout=wait):
            break
        _run_once()
    logger.info("Local scheduler stopped")


def start() -> None:
    global _thread
    setup_logging()
    STATE["enabled"] = bool(settings.local_scheduler_enabled)
    STATE["interval_minutes"] = settings.local_scheduler_interval_minutes
    if not settings.local_scheduler_enabled:
        logger.warning(
            "Local scheduler is DISABLED (LOCAL_SCHEDULER_ENABLED=false): nothing will "
            "sync/scan/trade automatically unless something calls /api/v1/jobs/trading-cycle"
        )
        return
    if _thread and _thread.is_alive():
        return
    STATE["started_at"] = datetime.now(timezone.utc)
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="local-trading-scheduler", daemon=True)
    _thread.start()

    from app.services.alert_service import watchdog

    watchdog.start()


def stop() -> None:
    _stop.set()
    from app.services.alert_service import watchdog

    watchdog.stop()
