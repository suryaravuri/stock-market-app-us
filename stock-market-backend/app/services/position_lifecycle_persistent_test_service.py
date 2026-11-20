from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.position_test_state import PositionTestCandleObservation, PositionTestStateHistory, PositionTestStateRecord
from app.repositories.position_test_state_repository import PositionTestStateRepository
from app.repositories.stock_repository import StockRepository
from app.schemas.position_lifecycle import PersistentPositionTestRequest
from app.strategies.position_lifecycle import PositionState, TERMINAL_POSITION_STATES, evaluate_long_position_candle


class PositionLifecyclePersistentTestService:
    TEST_MODE = "CONTROLLED_PERSISTENT_VALIDATION"
    EXECUTION_MODE = "ANALYSIS_ONLY"
    PERSISTENCE_MODE = "ISOLATED_TEST_TABLES"

    @staticmethod
    def _validate(request: PersistentPositionTestRequest) -> None:
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
        previous = request.opened_at
        for candle in request.candles:
            if candle.timestamp <= previous:
                raise ValueError("candle timestamps must be strictly increasing and after opened_at")
            if candle.low > candle.high or candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
                raise ValueError(f"Invalid OHLC candle at {candle.timestamp.isoformat()}")
            previous = candle.timestamp

    @staticmethod
    def run(db: Session, symbol: str, request: PersistentPositionTestRequest) -> dict:
        PositionLifecyclePersistentTestService._validate(request)
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
            timeframe=request.timeframe,
            state=PositionState.POSITION_OPEN.value,
            previous_state=None,
            last_event="TEST_POSITION_OPENED",
            reason="Controlled persistent analytical test position opened in isolated test tables",
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
            analytics_candle_source="SYNTHETIC_PERSISTED_CANDLES",
        )
        db.add(record)
        db.flush()
        db.add(PositionTestStateHistory(
            position_test_state_id=record.position_test_state_id,
            test_run_id=run_id,
            from_state=None,
            to_state=PositionState.POSITION_OPEN.value,
            event="TEST_POSITION_OPENED",
            reason=record.reason,
            candle_time=request.opened_at,
            observed_price=request.entry_price,
            active_stop=request.initial_stop,
        ))

        observations = []
        for candle in request.candles:
            previous_state = PositionState(record.state)
            before_stop = float(record.active_stop)
            observation = evaluate_long_position_candle(
                state=previous_state,
                candle_high=candle.high,
                candle_low=candle.low,
                candle_close=candle.close,
                entry_price=float(record.entry_price),
                initial_stop=float(record.initial_stop),
                active_stop=before_stop,
                target_1=float(record.target_1) if record.target_1 is not None else None,
                target_2=float(record.target_2) if record.target_2 is not None else None,
                target_1_hit=bool(record.target_1_hit),
                initial_risk_per_share=float(record.initial_risk_per_share),
            )
            record.last_evaluated_candle_time = candle.timestamp
            record.active_stop = observation.active_stop
            record.target_1_hit = observation.target_1_hit
            record.target_2_hit = observation.target_2_hit
            if observation.changed:
                record.previous_state = previous_state.value
                record.state = observation.state.value
                record.last_event = observation.event
                record.reason = observation.reason
                record.version += 1
                if observation.exit_price is not None:
                    record.exit_price = observation.exit_price
                    record.exit_reason = observation.exit_reason
                    record.closed_at = candle.timestamp
                db.add(PositionTestStateHistory(
                    position_test_state_id=record.position_test_state_id,
                    test_run_id=run_id,
                    from_state=previous_state.value,
                    to_state=observation.state.value,
                    event=observation.event,
                    reason=observation.reason,
                    candle_time=candle.timestamp,
                    observed_price=candle.close,
                    active_stop=observation.active_stop,
                ))
            db.add(PositionTestCandleObservation(
                position_test_state_id=record.position_test_state_id,
                test_run_id=run_id,
                candle_time=candle.timestamp,
                open_price=candle.open,
                high_price=candle.high,
                low_price=candle.low,
                close_price=candle.close,
            ))
            observations.append({
                "timestamp": candle.timestamp,
                "from_state": previous_state.value,
                "to_state": observation.state.value,
                "event": observation.event,
                "changed": observation.changed,
                "reason": observation.reason,
                "candle_open": candle.open,
                "candle_high": candle.high,
                "candle_low": candle.low,
                "candle_close": candle.close,
                "active_stop_before": before_stop,
                "active_stop_after": observation.active_stop,
                "target_1_hit": observation.target_1_hit,
                "target_2_hit": observation.target_2_hit,
                "exit_price": observation.exit_price,
                "exit_reason": observation.exit_reason,
            })
            if observation.state in TERMINAL_POSITION_STATES:
                break

        db.commit()
        db.refresh(record)
        return PositionLifecyclePersistentTestService._serialize(record, len(request.candles), observations, test_database_mutated=True)

    @staticmethod
    def get(db: Session, test_run_id: str) -> dict:
        record = PositionTestStateRepository.find(db, test_run_id)
        if record is None:
            raise ValueError(f"Persistent test run not found: {test_run_id}")
        return PositionLifecyclePersistentTestService._serialize(record, 0, [], test_database_mutated=False)

    @staticmethod
    def history(db: Session, test_run_id: str) -> dict:
        record = PositionTestStateRepository.find(db, test_run_id)
        if record is None:
            raise ValueError(f"Persistent test run not found: {test_run_id}")
        rows = PositionTestStateRepository.history(db, test_run_id)
        return {
            "symbol": record.symbol,
            "test_run_id": test_run_id,
            "test_mode": PositionLifecyclePersistentTestService.TEST_MODE,
            "execution_mode": PositionLifecyclePersistentTestService.EXECUTION_MODE,
            "broker_order_submitted": False,
            "production_position_tables_mutated": False,
            "transitions": [{
                "from_state": row.from_state,
                "to_state": row.to_state,
                "event": row.event,
                "reason": row.reason,
                "candle_time": row.candle_time,
                "observed_price": float(row.observed_price) if row.observed_price is not None else None,
                "active_stop": float(row.active_stop) if row.active_stop is not None else None,
                "signal_cycle_number": 0,
                "created_at": row.created_at,
            } for row in rows],
        }

    @staticmethod
    def delete(db: Session, symbol: str, test_run_id: str) -> dict:
        record = PositionTestStateRepository.find(db, test_run_id)
        if record is not None and record.symbol != symbol.strip().upper():
            raise ValueError(f"Persistent test run not found: {test_run_id}")
        deleted = PositionTestStateRepository.delete_run(db, test_run_id)
        return {"test_run_id": test_run_id, "deleted": deleted, "production_position_tables_mutated": False}

    @staticmethod
    def _serialize(record: PositionTestStateRecord, candles_received: int, observations: list[dict], *, test_database_mutated: bool) -> dict:
        return {
            "symbol": record.symbol,
            "timeframe": record.timeframe,
            "test_run_id": record.test_run_id,
            "test_mode": PositionLifecyclePersistentTestService.TEST_MODE,
            "execution_mode": PositionLifecyclePersistentTestService.EXECUTION_MODE,
            "persistence_mode": PositionLifecyclePersistentTestService.PERSISTENCE_MODE,
            "broker_order_submitted": False,
            "production_position_tables_mutated": False,
            "test_database_mutated": test_database_mutated,
            "initial_state": PositionState.POSITION_OPEN.value,
            "final_state": record.state,
            "entry_price": float(record.entry_price),
            "initial_stop": float(record.initial_stop),
            "active_stop": float(record.active_stop),
            "target_1": float(record.target_1) if record.target_1 is not None else None,
            "target_2": float(record.target_2) if record.target_2 is not None else None,
            "initial_risk_per_share": float(record.initial_risk_per_share),
            "target_1_hit": bool(record.target_1_hit),
            "target_2_hit": bool(record.target_2_hit),
            "terminal": PositionState(record.state) in TERMINAL_POSITION_STATES,
            "candles_received": candles_received,
            "candles_evaluated": len(observations),
            "version": record.version,
            "validation_status": "PASS",
            "observations": observations,
        }
