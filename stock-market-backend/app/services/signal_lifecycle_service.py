from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.market.sessions import US_SESSION, MarketSession, session_for_stock
from app.models.signal_state import SignalStateHistory, SignalStateRecord
from app.services.validation_run_service import ValidationRunService
from app.repositories.signal_state_repository import SignalStateRepository
from app.repositories.stock_repository import StockRepository
from app.repositories.market_candle_repository import MarketCandleRepository
from app.schemas.market import MarketTimeframe
from app.strategies.signal_lifecycle import (
    SignalState,
    SignalTransition,
    desired_signal_state,
    should_refresh_signal_candle_time,
    transition_signal_state,
)
from app.strategies.signal_rearm import evaluate_signal_rearm
from app.strategies.signal_staleness import evaluate_signal_staleness


class SignalLifecycleService:
    MAX_PENDING_CANDLES = 4

    @staticmethod
    def _pending_candle_count(
        db: Session,
        stock_id: int,
        timeframe: MarketTimeframe,
        current,
        session: MarketSession = US_SESSION,
    ) -> int:
        if current is None or current.state not in {"BREAKOUT_PENDING", "FOLLOW_THROUGH_PENDING"}:
            return 0
        transition = SignalStateRepository.latest_transition_to_state(
            db, stock_id, timeframe.value, current.state
        )
        if transition is None or transition.signal_candle_time is None:
            return 0
        latest = MarketCandleRepository.find_latest(db, stock_id, timeframe.value)
        if latest is None or latest.candle_time <= transition.signal_candle_time:
            return 0
        rows = MarketCandleRepository.find_by_range(
            db, stock_id, timeframe.value, transition.signal_candle_time, latest.candle_time
        )
        count = 0
        for row in rows:
            if row.candle_time <= transition.signal_candle_time:
                continue
            if session.is_regular(row.candle_time):
                count += 1
        return count

    @staticmethod
    def advance(
        *,
        db: Session,
        symbol: str,
        timeframe: MarketTimeframe,
        overall_score: int,
        decision_action: str,
        breakout: dict,
        confirmed_entry_price: float | None,
    ) -> dict:
        symbol = symbol.strip().upper()
        stock = StockRepository.find_by_symbol(db, symbol)
        if stock is None:
            raise ValueError(f"Stock not found: {symbol}")

        timeframe_value = timeframe.value
        current = SignalStateRepository.find_current(db, stock.stock_id, timeframe_value)
        previous = SignalState(current.state) if current is not None else None
        previous_signal_candle_time = current.signal_candle_time if current is not None else None

        desired_state, desired_event, desired_reason = desired_signal_state(
            overall_score=overall_score,
            decision_action=decision_action,
            breakout_status=breakout.get("status"),
            breakout_detected=bool(breakout.get("breakout_detected")),
            breakout_confirmed=bool(breakout.get("confirmed")),
        )
        transition = transition_signal_state(
            previous_state=previous,
            desired_state=desired_state,
            desired_event=desired_event,
            desired_reason=desired_reason,
        )

        market_session = session_for_stock(stock)
        pending_candles = SignalLifecycleService._pending_candle_count(
            db, stock.stock_id, timeframe, current, market_session
        )
        staleness = evaluate_signal_staleness(
            state=(previous.value if previous else transition.state.value),
            timeframe=timeframe,
            signal_candle_time=breakout.get("timestamp"),
            pending_candles=pending_candles,
            max_pending_candles=SignalLifecycleService.MAX_PENDING_CANDLES,
            session=market_session,
        )

        # Improvement #14: terminal pre-entry cycles may re-arm only when a
        # genuinely newer market session supplies a fresh, non-invalidated
        # signal. Re-reading the same historical candle can never resurrect a
        # terminal signal.
        candidate_staleness = evaluate_signal_staleness(
            state=desired_state.value,
            timeframe=timeframe,
            signal_candle_time=breakout.get("timestamp"),
            pending_candles=0,
            max_pending_candles=SignalLifecycleService.MAX_PENDING_CANDLES,
            session=market_session,
        )
        rearm = evaluate_signal_rearm(
            previous_state=previous,
            previous_signal_candle_time=previous_signal_candle_time,
            candidate_signal_candle_time=breakout.get("timestamp"),
            desired_state=desired_state,
            candidate_is_fresh=not candidate_staleness.expired,
            session=market_session,
        )
        rearmed = False
        if rearm.allowed:
            transition = SignalTransition(
                previous_state=previous,
                state=desired_state,
                event="SIGNAL_REARMED_NEW_SESSION",
                changed=True,
                reason=rearm.reason,
            )
            staleness = candidate_staleness
            pending_candles = 0
            rearmed = True

        if (
            not rearmed
            and staleness.expired
            and previous not in {SignalState.ENTRY_CONFIRMED, SignalState.INVALIDATED, SignalState.EXPIRED}
        ):
            transition = transition_signal_state(
                previous_state=previous,
                desired_state=SignalState.EXPIRED,
                desired_event="SIGNAL_EXPIRED",
                desired_reason=staleness.reason or "Signal expired",
            )

        active_validation = ValidationRunService.active(db)
        if active_validation is not None:
            baseline_status, _ = ValidationRunService.baseline_status(active_validation)
            if baseline_status != "MATCH":
                raise ValueError("BASELINE_MISMATCH: frozen strategy source changed during the active validation run")

        if current is None:
            current = SignalStateRecord(
                validation_run_id=active_validation.validation_run_id if active_validation else None,
                strategy_version=active_validation.strategy_version if active_validation else None,
                stock_id=stock.stock_id,
                timeframe=timeframe_value,
                state=transition.state.value,
                previous_state=None,
                last_event=transition.event,
                reason=transition.reason,
                version=1,
                cycle_number=1,
                cycle_started_at=breakout.get("timestamp") or datetime.now(timezone.utc),
            )
            db.add(current)
            transition_changed = True
        else:
            transition_changed = transition.changed
            if transition.changed:
                current.previous_state = previous.value if previous else None
                current.state = transition.state.value
                current.last_event = transition.event
                current.reason = transition.reason
                current.version += 1
                if rearmed:
                    current.cycle_number = (current.cycle_number or 1) + 1
                    current.cycle_started_at = breakout.get("timestamp") or datetime.now(timezone.utc)

        # Observation fields are refreshed even when state is sticky/no-change.
        # However, signal_candle_time belongs to the lifecycle cycle itself.
        # A terminal cycle that rejects re-arming must retain the candle that
        # actually belongs to that expired/invalidated cycle; otherwise a fresh
        # observation can make an old terminal reason look as though it applies
        # to today's candle. Active cycles and real state transitions continue
        # to advance their signal candle normally.
        current.observed_breakout_status = breakout.get("status")
        current.breakout_level = breakout.get("breakout_level")
        current.confirmation_price = breakout.get("confirmation_price")
        current.confirmed_entry_price = confirmed_entry_price
        if should_refresh_signal_candle_time(
            state=SignalState(current.state),
            transition_changed=transition_changed,
        ):
            current.signal_candle_time = breakout.get("timestamp")

        if transition_changed:
            if active_validation is not None:
                current.validation_run_id = active_validation.validation_run_id
                current.strategy_version = active_validation.strategy_version
            db.add(
                SignalStateHistory(
                    validation_run_id=active_validation.validation_run_id if active_validation else None,
                    strategy_version=active_validation.strategy_version if active_validation else None,
                    stock_id=stock.stock_id,
                    timeframe=timeframe_value,
                    from_state=previous.value if previous else None,
                    to_state=transition.state.value,
                    event=transition.event,
                    reason=transition.reason,
                    observed_breakout_status=breakout.get("status"),
                    signal_candle_time=breakout.get("timestamp"),
                    cycle_number=current.cycle_number or 1,
                )
            )

        db.commit()
        db.refresh(current)
        return SignalLifecycleService._serialize(
            symbol,
            current,
            transition_changed,
            staleness,
            rearmed=rearmed,
            rearm_status=(rearm.status if previous in {SignalState.EXPIRED, SignalState.INVALIDATED} else "NOT_APPLICABLE"),
            rearm_reason=(rearm.reason if previous in {SignalState.EXPIRED, SignalState.INVALIDATED} else None),
        )

    @staticmethod
    def get_current(db: Session, symbol: str, timeframe: MarketTimeframe) -> dict:
        symbol = symbol.strip().upper()
        stock = StockRepository.find_by_symbol(db, symbol)
        if stock is None:
            raise ValueError(f"Stock not found: {symbol}")
        current = SignalStateRepository.find_current(db, stock.stock_id, timeframe.value)
        if current is None:
            raise ValueError(f"Signal lifecycle not initialized for {symbol} {timeframe.value}; call /setup first")
        market_session = session_for_stock(stock)
        pending_candles = SignalLifecycleService._pending_candle_count(
            db, stock.stock_id, timeframe, current, market_session
        )
        staleness = evaluate_signal_staleness(
            state=current.state,
            timeframe=timeframe,
            signal_candle_time=current.signal_candle_time,
            pending_candles=pending_candles,
            max_pending_candles=SignalLifecycleService.MAX_PENDING_CANDLES,
            session=market_session,
        )
        return SignalLifecycleService._serialize(symbol, current, False, staleness)

    @staticmethod
    def get_history(db: Session, symbol: str, timeframe: MarketTimeframe, limit: int = 50) -> dict:
        symbol = symbol.strip().upper()
        stock = StockRepository.find_by_symbol(db, symbol)
        if stock is None:
            raise ValueError(f"Stock not found: {symbol}")
        rows = SignalStateRepository.history(db, stock.stock_id, timeframe.value, limit)
        return {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "transitions": [
                {
                    "from_state": row.from_state,
                    "to_state": row.to_state,
                    "event": row.event,
                    "reason": row.reason,
                    "observed_breakout_status": row.observed_breakout_status,
                    "signal_candle_time": row.signal_candle_time,
                    "cycle_number": row.cycle_number,
                    "created_at": row.created_at,
                }
                for row in rows
            ],
        }

    @staticmethod
    def _serialize(
        symbol: str,
        current: SignalStateRecord,
        state_changed: bool,
        staleness,
        *,
        rearmed: bool = False,
        rearm_status: str = "NOT_APPLICABLE",
        rearm_reason: str | None = None,
    ) -> dict:
        terminal_staleness_status = staleness.status
        if current.state == SignalState.EXPIRED.value and staleness.status == "NOT_APPLICABLE":
            reason = (current.reason or "").lower()
            if "prior market session" in reason or "session ended" in reason:
                terminal_staleness_status = "SESSION_ENDED"
            elif "completed candles" in reason:
                terminal_staleness_status = "PENDING_TIMEOUT"
            elif "freshness limit" in reason or "older than" in reason:
                terminal_staleness_status = "DATA_STALE"
            else:
                terminal_staleness_status = "EXPIRED"
        return {
            "symbol": symbol,
            "timeframe": current.timeframe,
            "state": current.state,
            "previous_state": current.previous_state,
            "last_event": current.last_event,
            "state_changed": state_changed,
            "reason": current.reason,
            "observed_breakout_status": current.observed_breakout_status,
            "breakout_level": float(current.breakout_level) if current.breakout_level is not None else None,
            "confirmation_price": float(current.confirmation_price) if current.confirmation_price is not None else None,
            "confirmed_entry_price": float(current.confirmed_entry_price) if current.confirmed_entry_price is not None else None,
            "signal_candle_time": current.signal_candle_time,
            "expired": current.state == SignalState.EXPIRED.value,
            "staleness_status": terminal_staleness_status,
            "expiration_reason": (current.reason if current.state == SignalState.EXPIRED.value else staleness.reason),
            "signal_age_minutes": staleness.signal_age_minutes,
            "max_signal_age_minutes": staleness.max_signal_age_minutes,
            "pending_candles": staleness.pending_candles,
            "max_pending_candles": staleness.max_pending_candles,
            "cycle_number": current.cycle_number or 1,
            "cycle_started_at": current.cycle_started_at,
            "rearmed": rearmed,
            "rearm_status": rearm_status,
            "rearm_reason": rearm_reason,
            "version": current.version,
            "created_at": current.created_at,
            "updated_at": current.updated_at,
        }
