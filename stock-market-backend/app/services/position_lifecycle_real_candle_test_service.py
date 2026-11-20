from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.position_test_state import PositionTestStateHistory, PositionTestStateRecord
from app.repositories.market_candle_repository import MarketCandleRepository
from app.repositories.position_test_state_repository import PositionTestStateRepository
from app.repositories.stock_repository import StockRepository
from app.schemas.market import MarketTimeframe
from app.schemas.position_lifecycle import PersistentRealCandleMonitorStartRequest
from app.strategies.position_lifecycle import (
    PositionState,
    TERMINAL_POSITION_STATES,
    evaluate_long_position_candle,
)
from app.strategies.position_persistence import classify_monitoring_candle


class PositionLifecycleRealCandleTestService:
    """#15D-3/#15D-4 isolated validation against real market_candle rows.

    This service deliberately uses position_test_state / position_test_state_history
    only. It never mutates production position_state tables and never calls a broker.
    """

    TEST_MODE = "CONTROLLED_REAL_CANDLE_MONITORING"
    EXECUTION_MODE = "ANALYSIS_ONLY"
    PERSISTENCE_MODE = "ISOLATED_TEST_TABLES"
    MONITORING_MODE = "REAL_MARKET_CANDLES_ISOLATED_TEST"

    @staticmethod
    def _validate_start(request: PersistentRealCandleMonitorStartRequest) -> MarketTimeframe:
        try:
            timeframe = MarketTimeframe(request.timeframe)
        except ValueError as exc:
            raise ValueError(f"Unsupported timeframe: {request.timeframe}") from exc

        if request.entry_price <= 0:
            raise ValueError("entry_price must be greater than zero")
        if request.initial_stop <= 0 or request.initial_stop >= request.entry_price:
            raise ValueError("initial_stop must be below entry_price for a long position")
        if request.target_1 is not None and request.target_1 <= request.entry_price:
            raise ValueError("target_1 must be above entry_price")
        if request.target_2 is not None:
            if request.target_1 is None:
                raise ValueError("target_2 requires target_1")
            if request.target_2 <= request.target_1:
                raise ValueError("target_2 must be above target_1")
        return timeframe

    @staticmethod
    def start_and_monitor(
        db: Session,
        symbol: str,
        request: PersistentRealCandleMonitorStartRequest,
        *,
        now_utc: datetime | None = None,
    ) -> dict:
        timeframe = PositionLifecycleRealCandleTestService._validate_start(request)
        symbol = symbol.strip().upper()
        stock = StockRepository.find_by_symbol(db, symbol)
        if stock is None:
            raise ValueError(f"Stock not found: {symbol}")

        run_id = str(uuid4())
        risk = request.entry_price - request.initial_stop
        record = PositionTestStateRecord(
            test_run_id=run_id,
            stock_id=stock.stock_id,
            symbol=symbol,
            timeframe=timeframe.value,
            state=PositionState.POSITION_OPEN.value,
            previous_state=None,
            last_event="TEST_POSITION_OPENED_FOR_REAL_CANDLE_MONITORING",
            reason="Isolated analytical test position opened for #15D real-candle monitoring validation",
            entry_price=request.entry_price,
            initial_stop=request.initial_stop,
            active_stop=request.initial_stop,
            target_1=request.target_1,
            target_2=request.target_2,
            initial_risk_per_share=risk,
            target_1_hit=False,
            target_2_hit=False,
            opened_at=request.opened_at,
            last_evaluated_candle_time=request.opened_at,
            version=1,
            analytics_candle_source="MARKET_CANDLE",
        )
        db.add(record)
        db.flush()
        db.add(
            PositionTestStateHistory(
                position_test_state_id=record.position_test_state_id,
                test_run_id=run_id,
                from_state=None,
                to_state=PositionState.POSITION_OPEN.value,
                event="TEST_POSITION_OPENED_FOR_REAL_CANDLE_MONITORING",
                reason=record.reason,
                candle_time=request.opened_at,
                observed_price=request.entry_price,
                active_stop=request.initial_stop,
            )
        )
        db.commit()
        db.refresh(record)

        return PositionLifecycleRealCandleTestService._monitor(
            db,
            record,
            trigger="CREATE_AND_MONITOR",
            now_utc=now_utc,
            created_this_call=True,
        )

    @staticmethod
    def monitor_existing_test_run(
        db: Session,
        symbol: str,
        test_run_id: str,
        *,
        now_utc: datetime | None = None,
    ) -> dict:
        symbol = symbol.strip().upper()
        record = PositionTestStateRepository.find(db, test_run_id)
        if record is None or record.symbol != symbol:
            raise ValueError(f"Persistent test run not found: {test_run_id}")

        return PositionLifecycleRealCandleTestService._monitor(
            db,
            record,
            trigger="REMONITOR",
            now_utc=now_utc,
            created_this_call=False,
        )

    @staticmethod
    def _monitor(
        db: Session,
        record: PositionTestStateRecord,
        *,
        trigger: str,
        now_utc: datetime | None,
        created_this_call: bool,
    ) -> dict:
        stock = StockRepository.find_by_symbol(db, record.symbol)
        if stock is None:
            raise ValueError(f"Stock not found: {record.symbol}")

        try:
            timeframe = MarketTimeframe(record.timeframe)
        except ValueError as exc:
            raise ValueError(f"Unsupported timeframe: {record.timeframe}") from exc

        latest = MarketCandleRepository.find_latest(db, stock.stock_id, timeframe.value)
        current_price = float(latest.close_price) if latest is not None else None

        # Terminal state is sticky and is not scanned or mutated again.
        if PositionState(record.state) in TERMINAL_POSITION_STATES:
            return PositionLifecycleRealCandleTestService._serialize(
                record,
                trigger=trigger,
                status="TERMINAL_STICKY",
                test_database_mutated=created_this_call,
                processed_candles=0,
                ignored_out_of_session_candles=0,
                ignored_incomplete_candles=0,
                duplicate_candles_skipped=0,
                new_candles_found=0,
                rows_scanned=0,
                current_price=current_price,
            )

        if latest is None or record.last_evaluated_candle_time is None:
            return PositionLifecycleRealCandleTestService._serialize(
                record,
                trigger=trigger,
                status="WAITING_FOR_CANDLES",
                test_database_mutated=created_this_call,
                processed_candles=0,
                ignored_out_of_session_candles=0,
                ignored_incomplete_candles=0,
                duplicate_candles_skipped=0,
                new_candles_found=0,
                rows_scanned=0,
                current_price=current_price,
            )

        rows = MarketCandleRepository.find_by_range(
            db,
            stock.stock_id,
            timeframe.value,
            record.last_evaluated_candle_time,
            latest.candle_time,
        )
        now_utc = now_utc or datetime.now(timezone.utc)

        processed_candles = 0
        ignored_out_of_session_candles = 0
        ignored_incomplete_candles = 0
        duplicate_candles_skipped = 0
        new_candles_found = 0
        lifecycle_mutated = False

        for candle in rows:
            classification = classify_monitoring_candle(
                candle.candle_time,
                last_evaluated_candle_time=record.last_evaluated_candle_time,
                timeframe=timeframe.value,
                now=now_utc,
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
            before_stop = float(record.active_stop)
            observation = evaluate_long_position_candle(
                state=previous_state,
                candle_high=float(candle.high_price),
                candle_low=float(candle.low_price),
                candle_close=float(candle.close_price),
                entry_price=float(record.entry_price),
                initial_stop=float(record.initial_stop),
                active_stop=before_stop,
                target_1=float(record.target_1) if record.target_1 is not None else None,
                target_2=float(record.target_2) if record.target_2 is not None else None,
                target_1_hit=bool(record.target_1_hit),
                initial_risk_per_share=float(record.initial_risk_per_share),
            )

            # Exactly-once eligible-candle semantics: even NO_STATE_CHANGE advances
            # the cursor. A second monitor call can never re-apply this candle.
            record.last_evaluated_candle_time = candle.candle_time
            record.active_stop = observation.active_stop
            record.target_1_hit = observation.target_1_hit
            record.target_2_hit = observation.target_2_hit
            processed_candles += 1
            lifecycle_mutated = True

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
                    PositionTestStateHistory(
                        position_test_state_id=record.position_test_state_id,
                        test_run_id=record.test_run_id,
                        from_state=previous_state.value,
                        to_state=observation.state.value,
                        event=observation.event,
                        reason=observation.reason,
                        candle_time=candle.candle_time,
                        observed_price=float(candle.close_price),
                        active_stop=observation.active_stop,
                    )
                )

            if observation.state in TERMINAL_POSITION_STATES:
                break

        if lifecycle_mutated:
            db.commit()
            db.refresh(record)

        if PositionState(record.state) in TERMINAL_POSITION_STATES:
            status = "TERMINAL_REACHED" if lifecycle_mutated else "TERMINAL_STICKY"
        elif processed_candles:
            status = "UPDATED"
        elif ignored_incomplete_candles:
            status = "WAITING_FOR_COMPLETED_CANDLE"
        else:
            status = "NO_NEW_ELIGIBLE_CANDLES"

        return PositionLifecycleRealCandleTestService._serialize(
            record,
            trigger=trigger,
            status=status,
            test_database_mutated=created_this_call or lifecycle_mutated,
            processed_candles=processed_candles,
            ignored_out_of_session_candles=ignored_out_of_session_candles,
            ignored_incomplete_candles=ignored_incomplete_candles,
            duplicate_candles_skipped=duplicate_candles_skipped,
            new_candles_found=new_candles_found,
            rows_scanned=len(rows),
            current_price=current_price,
        )

    @staticmethod
    def _serialize(
        record: PositionTestStateRecord,
        *,
        trigger: str,
        status: str,
        test_database_mutated: bool,
        processed_candles: int,
        ignored_out_of_session_candles: int,
        ignored_incomplete_candles: int,
        duplicate_candles_skipped: int,
        new_candles_found: int,
        rows_scanned: int,
        current_price: float | None,
    ) -> dict:
        unrealized_per_share = None
        unrealized_r = None
        if current_price is not None and record.entry_price is not None:
            unrealized_per_share = current_price - float(record.entry_price)
            risk = float(record.initial_risk_per_share)
            if risk > 0:
                unrealized_r = unrealized_per_share / risk

        return {
            "symbol": record.symbol,
            "timeframe": record.timeframe,
            "test_run_id": record.test_run_id,
            "test_mode": PositionLifecycleRealCandleTestService.TEST_MODE,
            "execution_mode": PositionLifecycleRealCandleTestService.EXECUTION_MODE,
            "persistence_mode": PositionLifecycleRealCandleTestService.PERSISTENCE_MODE,
            "monitoring_mode": PositionLifecycleRealCandleTestService.MONITORING_MODE,
            "monitoring_trigger": trigger,
            "monitoring_status": status,
            "broker_order_submitted": False,
            "production_position_tables_mutated": False,
            "test_database_mutated": test_database_mutated,
            "state": record.state,
            "previous_state": record.previous_state,
            "last_event": record.last_event,
            "reason": record.reason,
            "entry_price": float(record.entry_price),
            "initial_stop": float(record.initial_stop),
            "active_stop": float(record.active_stop),
            "target_1": float(record.target_1) if record.target_1 is not None else None,
            "target_2": float(record.target_2) if record.target_2 is not None else None,
            "initial_risk_per_share": float(record.initial_risk_per_share),
            "target_1_hit": bool(record.target_1_hit),
            "target_2_hit": bool(record.target_2_hit),
            "terminal": PositionState(record.state) in TERMINAL_POSITION_STATES,
            "opened_at": record.opened_at,
            "last_evaluated_candle_time": record.last_evaluated_candle_time,
            "exit_price": float(record.exit_price) if record.exit_price is not None else None,
            "exit_reason": record.exit_reason,
            "closed_at": record.closed_at,
            "current_price": current_price,
            "unrealized_per_share": unrealized_per_share,
            "unrealized_r": unrealized_r,
            "rows_scanned": rows_scanned,
            "new_candles_found": new_candles_found,
            "processed_candles": processed_candles,
            "duplicate_candles_skipped": duplicate_candles_skipped,
            "ignored_out_of_session_candles": ignored_out_of_session_candles,
            "ignored_incomplete_candles": ignored_incomplete_candles,
            "version": record.version,
            "validation_status": "PASS",
        }
