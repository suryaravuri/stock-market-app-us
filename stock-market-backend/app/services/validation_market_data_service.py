from __future__ import annotations

import exchange_calendars as xcals
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.market.sessions import US_SESSION, MarketSession, session_for_stock
from app.models.market_candle import MarketCandle
from app.models.stock import Stock
from app.models.validation_run import ValidationRun
from app.models.watchlist import Watchlist, WatchlistStock
from app.schemas.market import MarketTimeframe
from app.services.market_data_quality_service import MarketDataQualityService
from app.services.validation_run_service import ValidationRunService
from app.strategies.position_persistence import (
    REGULAR_SESSION_CLOSE,
    REGULAR_SESSION_OPEN,
    SESSION_TZ,
    TIMEFRAME_MINUTES,
    aware_utc,
    is_completed_candle,
    is_regular_session_candle,
)
from app.models.user import AppUser
from app.services.watchlist_service import WatchlistService

class ValidationMarketDataService:
    """Phase #16B market-data qualification for a frozen validation run.

    This service is deliberately read-only.  A symbol is eligible to enter the
    frozen V1 signal pipeline only when its market data receives PASS.  DEGRADED
    and FAIL remain visible diagnostically but do not qualify for signal
    advancement.
    """

    EXECUTION_MODE = "ANALYSIS_ONLY"
    REQUIRED_HISTORY_CANDLES = 50  # EMA50 is part of the frozen selection engine.
    QUERY_LIMIT = 350
    DEGRADED_MAX_LAG_BARS = 1
    SESSION_TIMEZONE = "America/New_York"
    NYSE_CALENDAR = xcals.get_calendar("XNYS")

    @staticmethod
    def _previous_weekday(value: date) -> date:
        candidate = value - timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate -= timedelta(days=1)
        return candidate

    @classmethod
    def _previous_session_date(cls, value: date, session: MarketSession = US_SESSION) -> date:
        candidate = value - timedelta(days=1)

        while not session.is_session_day(candidate):
            candidate -= timedelta(days=1)

        return candidate

    @staticmethod
    def _bar_start_for_close(
        session_date: date,
        minutes: int,
        session: MarketSession = US_SESSION,
    ) -> datetime:
        close_local = datetime.combine(
            session_date, session.close_time_on(session_date), tzinfo=session.tz
        )
        return close_local - timedelta(minutes=minutes)

    @classmethod
    def expected_latest_completed_candle(
        cls,
        timeframe: str,
        now: datetime | None = None,
        session: MarketSession = US_SESSION,
    ) -> datetime | None:
        """Return expected latest completed regular-session bar start in UTC."""

        now_utc = aware_utc(now or datetime.now(timezone.utc))
        now_et = now_utc.astimezone(session.tz)
        today = now_et.date()
        local_clock = now_et.time().replace(tzinfo=None)

        is_session = session.is_session_day(today)
        # Real close for today: earlier than session.close on half days.
        today_close = session.close_time_on(today) if is_session else session.close

        # Daily timeframe
        if timeframe == "1Day":
            if is_session and local_clock >= today_close:
                session_date = today
            else:
                session_date = cls._previous_session_date(today, session)

            return datetime.combine(
                session_date,
                session.open,
                tzinfo=session.tz,
            ).astimezone(timezone.utc)

        # Intraday timeframes
        minutes = TIMEFRAME_MINUTES.get(timeframe)
        if minutes is None:
            return None

        # Weekend or exchange holiday
        if not is_session:
            session_date = cls._previous_session_date(today, session)
            return cls._bar_start_for_close(session_date, minutes, session).astimezone(timezone.utc)

        # Before today's market opens
        if local_clock < session.open:
            session_date = cls._previous_session_date(today, session)
            return cls._bar_start_for_close(session_date, minutes, session).astimezone(timezone.utc)

        # After today's market closes
        if local_clock >= today_close:
            return cls._bar_start_for_close(today, minutes, session).astimezone(timezone.utc)

        # During regular market session
        open_local = datetime.combine(
            today,
            session.open,
            tzinfo=session.tz,
        )

        elapsed_seconds = (now_et - open_local).total_seconds()
        completed_bars = int(elapsed_seconds // (minutes * 60))

        if completed_bars <= 0:
            session_date = cls._previous_session_date(today, session)
            return cls._bar_start_for_close(session_date, minutes, session).astimezone(timezone.utc)

        expected_start = open_local + timedelta(
            minutes=(completed_bars - 1) * minutes
        )

        return expected_start.astimezone(timezone.utc)

    @staticmethod
    def _intraday_gap_count(
        candles: list[MarketCandle],
        timeframe: str,
        session: MarketSession = US_SESSION,
    ) -> int:
        minutes = TIMEFRAME_MINUTES.get(timeframe)
        if minutes is None or len(candles) < 2:
            return 0
        expected = timedelta(minutes=minutes)
        gaps = 0
        for previous, current in zip(candles, candles[1:]):
            prev_et = aware_utc(previous.candle_time).astimezone(session.tz)
            curr_et = aware_utc(current.candle_time).astimezone(session.tz)
            # Overnight/weekend boundaries are not data gaps.
            if prev_et.date() != curr_et.date():
                continue
            if aware_utc(current.candle_time) - aware_utc(previous.candle_time) != expected:
                gaps += 1
        return gaps

    @classmethod
    def _session_distance(
        cls,
        start: date,
        end: date,
        session: MarketSession = US_SESSION,
    ) -> int:
        """Count actual exchange trading sessions between two dates."""

        if start >= end:
            return 0

        count = 0
        cursor = start

        while cursor < end:
            cursor += timedelta(days=1)

            if session.is_session_day(cursor):
                count += 1

        return count


    @classmethod
    def _lag_bars(
        cls,
        latest: datetime,
        expected: datetime,
        timeframe: str,
        session: MarketSession = US_SESSION,
    ) -> int | None:
        latest_utc = aware_utc(latest)
        expected_utc = aware_utc(expected)

        if latest_utc >= expected_utc:
            return 0

        minutes = TIMEFRAME_MINUTES.get(timeframe)

        if minutes is None:
            return 1

        latest_et = latest_utc.astimezone(session.tz)
        expected_et = expected_utc.astimezone(session.tz)

        if latest_et.date() != expected_et.date():
            return cls._session_distance(
                latest_et.date(),
                expected_et.date(),
                session,
            ) * 100

        delta_minutes = (
            expected_utc - latest_utc
        ).total_seconds() / 60

        return max(
            1,
            int(round(delta_minutes / minutes)),
        )

    @staticmethod
    def _session_timezones(stocks: list[Stock]) -> str:
        names = sorted({session_for_stock(stock).timezone_name for stock in stocks})
        return ", ".join(names) if names else ValidationMarketDataService.SESSION_TIMEZONE

    @classmethod
    def _validate_symbol(
        cls,
        db: Session,
        stock: Stock,
        timeframe: MarketTimeframe,
        now_utc: datetime,
    ) -> dict:
        stmt = (
            select(MarketCandle)
            .where(
                MarketCandle.stock_id == stock.stock_id,
                MarketCandle.timeframe == timeframe.value,
            )
            .order_by(MarketCandle.candle_time.desc())
            .limit(cls.QUERY_LIMIT)
        )
        raw = list(db.scalars(stmt).all())
        raw.reverse()
        session = session_for_stock(stock)

        reasons: list[str] = []
        if not raw:
            return {
                "stock_id": stock.stock_id,
                "symbol": stock.symbol.strip().upper(),
                "timeframe": timeframe.value,
                "status": "FAIL",
                "eligible_for_signal_analysis": False,
                "latest_regular_session_candle": None,
                "expected_latest_completed_candle": cls.expected_latest_completed_candle(
                    timeframe.value, now_utc, session
                ),
                "freshness_lag_bars": None,
                "candles_examined": 0,
                "valid_regular_completed_candles": 0,
                "required_history_candles": cls.REQUIRED_HISTORY_CANDLES,
                "indicator_ready": False,
                "duplicate_timestamp_count": 0,
                "intraday_gap_count": 0,
                "latest_candle_valid": None,
                "latest_candle_issues": [],
                "reasons": ["NO_MARKET_CANDLES"],
            }

        timestamp_counts = Counter(aware_utc(c.candle_time) for c in raw)
        duplicate_count = sum(count - 1 for count in timestamp_counts.values() if count > 1)

        regular_completed = [
            c for c in raw
            if is_regular_session_candle(c.candle_time, session)
            and is_completed_candle(c.candle_time, timeframe.value, now_utc, session)
        ]

        valid_regular: list[MarketCandle] = []
        validations = {}
        for candle in regular_completed:
            validation = MarketDataQualityService.validate_candle(candle)
            validations[candle.candle_id] = validation
            if validation.valid:
                valid_regular.append(candle)

        expected = cls.expected_latest_completed_candle(timeframe.value, now_utc, session)
        latest = regular_completed[-1] if regular_completed else None
        latest_validation = validations.get(latest.candle_id) if latest is not None else None
        lag = (
            cls._lag_bars(latest.candle_time, expected, timeframe.value, session)
            if latest is not None and expected is not None
            else None
        )
        gap_count = cls._intraday_gap_count(
            regular_completed[-cls.REQUIRED_HISTORY_CANDLES:], timeframe.value, session
        )
        indicator_ready = len(valid_regular) >= cls.REQUIRED_HISTORY_CANDLES

        hard_fail = False
        degraded = False

        if latest is None:
            hard_fail = True
            reasons.append("NO_COMPLETED_REGULAR_SESSION_CANDLE")
        elif latest_validation is not None and not latest_validation.valid:
            hard_fail = True
            reasons.append("LATEST_COMPLETED_CANDLE_INVALID")

        if not indicator_ready:
            hard_fail = True
            reasons.append(
                f"INSUFFICIENT_VALID_HISTORY:{len(valid_regular)}/{cls.REQUIRED_HISTORY_CANDLES}"
            )

        if duplicate_count:
            hard_fail = True
            reasons.append(f"DUPLICATE_TIMESTAMPS:{duplicate_count}")

        if gap_count > 1:
            hard_fail = True
            reasons.append(f"MULTIPLE_INTRADAY_GAPS:{gap_count}")
        elif gap_count == 1:
            degraded = True
            reasons.append("SINGLE_INTRADAY_GAP")

        if lag is None:
            hard_fail = True
            reasons.append("FRESHNESS_UNDETERMINED")
        elif lag > cls.DEGRADED_MAX_LAG_BARS:
            hard_fail = True
            reasons.append(f"STALE_DATA:{lag}_BAR_LAG")
        elif lag == 1:
            degraded = True
            reasons.append("ONE_BAR_DATA_LAG")

        # Historical malformed bars are visible even when the latest bar is good.
        invalid_history = len(regular_completed) - len(valid_regular)
        if invalid_history > 0:
            degraded = True
            reasons.append(f"INVALID_HISTORY_CANDLES:{invalid_history}")

        status = "FAIL" if hard_fail else ("DEGRADED" if degraded else "PASS")
        return {
            "stock_id": stock.stock_id,
            "symbol": stock.symbol.strip().upper(),
            "timeframe": timeframe.value,
            "status": status,
            "eligible_for_signal_analysis": status == "PASS",
            "latest_regular_session_candle": latest.candle_time if latest else None,
            "expected_latest_completed_candle": expected,
            "freshness_lag_bars": lag,
            "candles_examined": len(raw),
            "valid_regular_completed_candles": len(valid_regular),
            "required_history_candles": cls.REQUIRED_HISTORY_CANDLES,
            "indicator_ready": indicator_ready,
            "duplicate_timestamp_count": duplicate_count,
            "intraday_gap_count": gap_count,
            "latest_candle_valid": latest_validation.valid if latest_validation is not None else None,
            "latest_candle_issues": list(latest_validation.issues) if latest_validation is not None else [],
            "reasons": reasons,
        }

    @classmethod
    def monitor_watchlist(
            cls,
            db: Session,
            watchlist_id: int,
            current_user: AppUser,
            timeframe: MarketTimeframe = MarketTimeframe.FIFTEEN_MINUTES,
            now: datetime | None = None,
    ) -> dict:
        watchlist = WatchlistService.get_watchlist(
            db=db,
            watchlist_id=watchlist_id,
            current_user=current_user,
        )

        stmt = (
            select(Stock)
            .join(
                WatchlistStock,
                WatchlistStock.stock_id == Stock.stock_id,
            )
            .where(
                WatchlistStock.watchlist_id == watchlist_id,
                WatchlistStock.analysis_enabled.is_(True),
                Stock.active.is_(True),
            )
            .order_by(
                WatchlistStock.priority.desc(),
                Stock.symbol.asc(),
            )
        )

        stocks = list(db.scalars(stmt).all())

        if not stocks:
            raise ValueError(
                f"Watchlist '{watchlist_id}' has no active analysis-enabled stocks"
            )

        now_utc = aware_utc(now or datetime.now(timezone.utc))

        results = [
            cls._validate_symbol(
                db=db,
                stock=stock,
                timeframe=timeframe,
                now_utc=now_utc,
            )
            for stock in stocks
        ]

        passed = sum(r["status"] == "PASS" for r in results)
        degraded = sum(r["status"] == "DEGRADED" for r in results)
        failed = sum(r["status"] == "FAIL" for r in results)

        eligible = sum(
            bool(r["eligible_for_signal_analysis"])
            for r in results
        )

        if failed:
            data_status = "FAIL"
        elif degraded:
            data_status = "DEGRADED"
        else:
            data_status = "PASS"

        expected_candles = [
            r["expected_latest_completed_candle"]
            for r in results
            if r["expected_latest_completed_candle"] is not None
        ]

        latest_candles = [
            r["latest_regular_session_candle"]
            for r in results
            if r["latest_regular_session_candle"] is not None
        ]

        expected_latest_completed_candle = (
            max(expected_candles)
            if expected_candles
            else None
        )

        latest_available_candle = (
            min(latest_candles)
            if len(latest_candles) == len(results)
            else None
        )

        return {
            "watchlist_id": watchlist.watchlist_id,
            "watchlist_name": watchlist.name,
            "timeframe": timeframe.value,
            "execution_mode": cls.EXECUTION_MODE,
            "data_status": data_status,
            "symbols_checked": len(results),
            "symbols_passed": passed,
            "symbols_degraded": degraded,
            "symbols_failed": failed,
            "eligible_for_signal_analysis": eligible,
            "blocked_stocks": len(results) - eligible,
            "expected_latest_completed_candle": expected_latest_completed_candle,
            "latest_available_candle": latest_available_candle,
            "session_timezone": cls._session_timezones(stocks),
            "evaluated_at": now_utc,
            "broker_order_submitted": False,
            "database_mutated": False,
            "production_position_tables_mutated": False,
            "results": results,
        }

    @classmethod
    def validate_watchlist(
        cls,
        db: Session,
        validation_run_id: int,
        watchlist_id: int = 1,
        timeframe: MarketTimeframe = MarketTimeframe.FIFTEEN_MINUTES,
        now: datetime | None = None,
    ) -> dict:
        run = db.get(ValidationRun, validation_run_id)
        if run is None:
            raise ValueError(f"Validation run not found: {validation_run_id}")
        if run.status != "ACTIVE":
            raise ValueError(f"Validation run {validation_run_id} is {run.status}; market-data validation requires ACTIVE")

        baseline_status, baseline_note = ValidationRunService.baseline_status(run)
        if baseline_status != "MATCH":
            raise ValueError(baseline_note or "Frozen strategy baseline mismatch")

        watchlist = db.get(Watchlist, watchlist_id)
        if watchlist is None:
            raise ValueError(f"Watchlist '{watchlist_id}' not found")

        stmt = (
            select(Stock)
            .join(WatchlistStock, WatchlistStock.stock_id == Stock.stock_id)
            .where(
                WatchlistStock.watchlist_id == watchlist_id,
                WatchlistStock.analysis_enabled.is_(True),
                Stock.active.is_(True),
            )
            .order_by(WatchlistStock.priority.desc(), Stock.symbol.asc())
        )
        stocks = list(db.scalars(stmt).all())
        if not stocks:
            raise ValueError(f"Watchlist '{watchlist_id}' has no active analysis-enabled stocks")

        now_utc = aware_utc(now or datetime.now(timezone.utc))
        results = [cls._validate_symbol(db, stock, timeframe, now_utc) for stock in stocks]

        passed = sum(r["status"] == "PASS" for r in results)
        degraded = sum(r["status"] == "DEGRADED" for r in results)
        failed = sum(r["status"] == "FAIL" for r in results)
        eligible = sum(bool(r["eligible_for_signal_analysis"]) for r in results)

        if failed:
            overall = "FAIL"
        elif degraded:
            overall = "DEGRADED"
        else:
            overall = "PASS"

        return {
            "validation_run_id": run.validation_run_id,
            "strategy_version": run.strategy_version,
            "validation_phase": run.validation_phase,
            "execution_mode": cls.EXECUTION_MODE,
            "baseline_status": baseline_status,
            "watchlist_id": watchlist.watchlist_id,
            "watchlist_name": watchlist.name,
            "timeframe": timeframe.value,
            "validation_status": overall,
            "symbols_checked": len(results),
            "symbols_passed": passed,
            "symbols_degraded": degraded,
            "symbols_failed": failed,
            "eligible_for_signal_analysis": eligible,
            "session_timezone": cls._session_timezones(stocks),
            "evaluated_at": now_utc,
            "results": results,
            "broker_order_submitted": False,
            "database_mutated": False,
            "production_position_tables_mutated": False,
        }


    def cls_day_distance_in_sessions(start: date, end: date) -> int:
        """Count actual NYSE trading sessions between two dates."""
        if start >= end:
            return 0

        calendar = ValidationMarketDataService.NYSE_CALENDAR

        count = 0
        cursor = start

        while cursor < end:
            cursor += timedelta(days=1)

            if calendar.is_session(cursor.isoformat()):
                count += 1

        return count
