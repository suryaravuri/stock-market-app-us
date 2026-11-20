"""Logging for the trading bot.

Before this, nothing configured Python logging, so every logger.info(...)
in the app was silently dropped (Python's default level is WARNING and
uvicorn only configures its own loggers). That is why the terminal showed
SQL and HTTP lines but never a word about why a stock was or wasn't bought.

setup_logging() is idempotent and is called automatically by the local
scheduler and the trading cycle, so main.py does not need to change.

Output:
  console              INFO lines from the app.* loggers
  logs/trading.log     same lines, rotated (5 x 5 MB)
  logs/decisions.jsonl one JSON object per stock per cycle (see decision_log.py)

Environment variables (optional):
  APP_LOG_LEVEL=INFO|DEBUG      level for app.* loggers (default INFO)
  APP_LOG_DIR=logs              folder for the log files
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"


def log_dir() -> Path:
    path = Path(os.getenv("APP_LOG_DIR", "logs"))
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    level = getattr(logging, os.getenv("APP_LOG_LEVEL", "INFO").upper(), logging.INFO)
    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)
    # Don't also pass records to the root logger (avoids duplicate lines if
    # something else configures root later).
    app_logger.propagate = False

    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    app_logger.addHandler(console)

    try:
        file_handler = RotatingFileHandler(
            log_dir() / "trading.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        app_logger.addHandler(file_handler)
    except OSError as exc:  # read-only filesystem etc. - console still works
        app_logger.warning("File logging disabled: %s", exc)

    app_logger.info("Logging configured (level=%s, dir=%s)", logging.getLevelName(level), log_dir())
