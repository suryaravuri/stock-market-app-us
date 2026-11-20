from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.position_state import PositionStateHistory
from app.repositories.market_candle_repository import MarketCandleRepository
from app.repositories.position_state_repository import PositionStateRepository
from app.repositories.stock_repository import StockRepository
from app.schemas.market import MarketTimeframe
from app.services.position_lifecycle_service import PositionLifecycleService
from app.strategies.position_lifecycle import (
    PositionState,
    TERMINAL_POSITION_STATES,
    evaluate_long_position_candle,
)
from app.strategies.position_persistence import classify_monitoring_candle
from app.market.sessions import session_for_stock


class PositionMonitoringService:
    """Improvement #15D real persistent analytical position monitor.

    This service never opens a position and never submits a broker order. It can
    only advance an already-persisted analytical position using new, completed,
    regular-session market candles.
    """

    MONITORING_MODE = "REAL_MARKET_CANDLES"
    EXECUTION_MODE = "ANALYSIS_ONLY"

    @staticmethod
    def monitor_existing(
        db: Session,
        symbol: str,
        timeframe: MarketTimeframe,
        *,
        trigger: str = "MANUAL",
        now_utc: datetime | None = None,
    ) -> dict:
        symbol = symbol.strip().upper()
        stock = StockRepository.find_by_symbol(db, symbol)
        if stock is None:
            raise ValueError(f"Stock not found: {symbol}")

        record = PositionStateRepository.find_latest(db, stock.stock_id, timeframe.value)
        latest = MarketCandleRepository.find_latest(db, stock.stock_id, timeframe.value)
        current_price = float(latest.close_price) if latest is not None else None

        if record is None:
            result = PositionLifecycleService._not_open(
                symbol=symbol,
                timeframe=timeframe,
                cycle_number=0,
                current_price=current_price,
                reason="No persistent analytical position exists; real monitoring does not create positions",
                opening_gate_passed=False,
            )
            return PositionMonitoringService._decorate(
                result,
                trigger=trigger,
                status="NO_POSITION",
                new_candles_found=0,
                duplicate_candles_skipped=0,
            )

        if PositionState(record.state) in TERMINAL_POSITION_STATES:
            result = PositionLifecycleService._serialize(
                symbol,
                record,
                False,
                current_price,
                database_mutated=False,
                opening_gate_passed=True,
                opening_gate_reason="Existing persistent position is terminal and immutable",
                processed_candles=0,
                ignored_out_of_session_candles=0,
                ignored_incomplete_candles=0,
            )
            return PositionMonitoringService._decorate(
                result,
                trigger=trigger,
                status="TERMINAL_STICKY",
                new_candles_found=0,
                duplicate_candles_skipped=0,
            )

        if latest is None or record.last_evaluated_candle_time is None:
            result = PositionLifecycleService._serialize(
                symbol,
                record,
                False,
                current_price,
                database_mutated=False,
                opening_gate_passed=True,
                opening_gate_reason="Persistent position exists; waiting for post-entry market candles",
                processed_candles=0,
                ignored_out_of_session_candles=0,
                ignored_incomplete_candles=0,
            )
            return PositionMonitoringService._decorate(
                result,
                trigger=trigger,
                status="WAITING_FOR_CANDLES",
                new_candles_found=0,
                duplicate_candles_skipped=0,
            )

        rows = MarketCandleRepository.find_by_range(
            db,
            stock.stock_id,
            timeframe.value,
            record.last_evaluated_candle_time,
            latest.candle_time,
        )
        now_utc = now_utc or datetime.now(timezone.utc)

        state_changed = False
        database_mutated = False
        processed_candles = 0
        ignored_out_of_session_candles = 0
        ignored_incomplete_candles = 0
        duplicate_candles_skipped = 0
        new_candles_found = 0

        for candle in rows:
            classification = classify_monitoring_candle(
                candle.candle_time,
                last_evaluated_candle_time=record.last_evaluated_candle_time,
                timeframe=timeframe.value,
                now=now_utc,
                session=session_for_stock(stock),
            )
            if classification == "DUPLICATE_OR_ALREADY_EVALUATED":
                duplicate_candles_skipped += 1
                continue

            new_candles_found += 1
            if classification == "OUT_OF_SESSION":
                ignored_out_of_session_candles += 1
                continue
            if classification == "INCOMPLETE":
                ignored_incomplete_candles += 1
                continue

            previous_state = PositionState(record.state)
            observation = evaluate_long_position_candle(
                state=previous_state,
                candle_high=float(candle.high_price),
                candle_low=float(candle.low_price),
                candle_close=float(candle.close_price),
                entry_price=float(record.entry_price),
                initial_stop=float(record.initial_stop),
                active_stop=float(record.active_stop),
                target_1=float(record.target_1) if record.target_1 is not None else None,
                target_2=float(record.target_2) if record.target_2 is not None else None,
                target_1_hit=bool(record.target_1_hit),
                initial_risk_per_share=float(record.initial_risk_per_share),
            )

            # Advancing this cursor is what gives #15D its exactly-once candle
            # semantics. Even a NO_STATE_CHANGE completed candle is consumed once.
            record.last_evaluated_candle_time = candle.candle_time
            record.active_stop = observation.active_stop
            record.target_1_hit = observation.target_1_hit
            record.target_2_hit = observation.target_2_hit
            processed_candles += 1
            database_mutated = True

            if observation.changed:
                record.previous_state = previous_state.value
                record.state = observation.state.value
                record.last_event = observation.event
                record.reason = observation.reason
                record.version += 1
                if observation.exit_price is not None:
                    record.exit_price = observation.exit_price
                    record.exit_reason = observation.exit_reason
                    record.closed_at = candle.candle_time
                db.add(
                    PositionStateHistory(
                        position_state_id=record.position_state_id,
                        stock_id=stock.stock_id,
                        timeframe=timeframe.value,
                        signal_cycle_number=record.signal_cycle_number,
                        from_state=previous_state.value,
                        to_state=observation.state.value,
                        event=observation.event,
                        reason=observation.reason,
                        candle_time=candle.candle_time,
                        observed_price=float(candle.close_price),
                        active_stop=observation.active_stop,
                    )
                )
                state_changed = True

            if observation.state in TERMINAL_POSITION_STATES:
                break

        if database_mutated:
            db.commit()
            db.refresh(record)

        latest = MarketCandleRepository.find_latest(db, stock.stock_id, timeframe.value)
        current_price = float(latest.close_price) if latest is not None else current_price
        status = "UPDATED" if processed_candles else (
            "WAITING_FOR_COMPLETED_CANDLE" if ignored_incomplete_candles else "NO_NEW_ELIGIBLE_CANDLES"
        )
        if PositionState(record.state) in TERMINAL_POSITION_STATES:
            status = "TERMINAL_REACHED" if state_changed else "TERMINAL_STICKY"

        result = PositionLifecycleService._serialize(
            symbol,
            record,
            state_changed,
            current_price,
            database_mutated=database_mutated,
            opening_gate_passed=True,
            opening_gate_reason="Monitoring an existing persistent analytical position; no new position was opened",
            processed_candles=processed_candles,
            ignored_out_of_session_candles=ignored_out_of_session_candles,
            ignored_incomplete_candles=ignored_incomplete_candles,
        )
        return PositionMonitoringService._decorate(
            result,
            trigger=trigger,
            status=status,
            new_candles_found=new_candles_found,
            duplicate_candles_skipped=duplicate_candles_skipped,
        )

    @staticmethod
    def _decorate(
        result: dict,
        *,
        trigger: str,
        status: str,
        new_candles_found: int,
        duplicate_candles_skipped: int,
    ) -> dict:
        result.update(
            {
                "monitoring_mode": PositionMonitoringService.MONITORING_MODE,
                "monitoring_trigger": trigger,
                "monitoring_status": status,
                "new_candles_found": new_candles_found,
                "duplicate_candles_skipped": duplicate_candles_skipped,
            }
        )
        return result
