from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.position_state import PositionStateHistory, PositionStateRecord
from app.services.validation_run_service import ValidationRunService
from app.repositories.market_candle_repository import MarketCandleRepository
from app.repositories.position_state_repository import PositionStateRepository
from app.repositories.stock_repository import StockRepository
from app.market.sessions import session_for_stock
from app.schemas.market import MarketTimeframe
from app.strategies.position_lifecycle import (
    PositionState,
    TERMINAL_POSITION_STATES,
    evaluate_long_position_candle,
)
from app.strategies.position_persistence import (
    evaluate_persistent_opening_gate,
    is_completed_candle,
    is_regular_session_candle,
)


class PositionLifecycleService:
    """Persistent, analysis-only post-entry lifecycle.

    Improvement #15C hardens the persistence bridge between an ENTRY_CONFIRMED
    signal and the analytical position state machine. Broker execution remains
    completely disabled.
    """

    EXECUTION_MODE = "ANALYSIS_ONLY"
    PERSISTENCE_MODE = "PERSISTENT_ANALYTICAL"
    @staticmethod
    def advance_from_setup(
        *,
        db: Session,
        symbol: str,
        timeframe: MarketTimeframe,
        signal_lifecycle: dict,
        risk_reward: dict,
        breakout: dict,
        current_price: float,
    ) -> dict:
        """Create/advance one persistent analytical position for a signal cycle.

        Idempotency is provided by the unique (stock, timeframe, signal cycle)
        record. Only completed regular-session candles strictly after the confirmed
        follow-through candle can advance the position.
        """
        symbol = symbol.strip().upper()
        stock = StockRepository.find_by_symbol(db, symbol)
        if stock is None:
            raise ValueError(f"Stock not found: {symbol}")

        cycle_number = int(signal_lifecycle.get("cycle_number") or 1)
        record = PositionStateRepository.find_cycle(db, stock.stock_id, timeframe.value, cycle_number)

        opening_gate_passed, opening_gate_reason = evaluate_persistent_opening_gate(
            signal_lifecycle, risk_reward, breakout
        )
        if record is None and not opening_gate_passed:
            return PositionLifecycleService._not_open(
                symbol=symbol,
                timeframe=timeframe,
                cycle_number=cycle_number,
                current_price=current_price,
                reason=opening_gate_reason,
                opening_gate_passed=False,
            )

        state_changed = False
        database_mutated = False
        processed_candles = 0
        ignored_out_of_session_candles = 0
        ignored_incomplete_candles = 0

        active_validation = ValidationRunService.active(db)
        if active_validation is not None:
            baseline_status, _ = ValidationRunService.baseline_status(active_validation)
            if baseline_status != "MATCH":
                raise ValueError("BASELINE_MISMATCH: frozen strategy source changed during the active validation run")

        if record is None:
            entry = float(risk_reward["entry"])
            stop = float(risk_reward["stop_loss"])
            risk_per_share = float(risk_reward["risk_per_share"])
            opened_at = breakout["follow_through_candle_timestamp"]

            record = PositionStateRecord(
                validation_run_id=active_validation.validation_run_id if active_validation else None,
                strategy_version=active_validation.strategy_version if active_validation else None,
                stock_id=stock.stock_id,
                timeframe=timeframe.value,
                signal_cycle_number=cycle_number,
                state=PositionState.POSITION_OPEN.value,
                previous_state=None,
                last_event="ANALYTICAL_POSITION_OPENED",
                reason="ENTRY_CONFIRMED created a persistent analysis-only position; no broker order was submitted",
                entry_price=entry,
                quantity=int(risk_reward.get("quantity") or 0),
                initial_stop=stop,
                active_stop=stop,
                target_1=risk_reward.get("target_1"),
                target_2=risk_reward.get("target_2"),
                initial_risk_per_share=risk_per_share,
                target_1_hit=False,
                target_2_hit=False,
                opened_at=opened_at,
                # The follow-through candle established the entry. Never evaluate
                # that same candle again as post-entry price action.
                last_evaluated_candle_time=opened_at,
                version=1,
            )
            db.add(record)
            db.flush()
            db.add(
                PositionStateHistory(
                    validation_run_id=active_validation.validation_run_id if active_validation else None,
                    strategy_version=active_validation.strategy_version if active_validation else None,
                    position_state_id=record.position_state_id,
                    stock_id=stock.stock_id,
                    timeframe=timeframe.value,
                    signal_cycle_number=cycle_number,
                    from_state=None,
                    to_state=PositionState.POSITION_OPEN.value,
                    event="ANALYTICAL_POSITION_OPENED",
                    reason=record.reason,
                    candle_time=opened_at,
                    observed_price=entry,
                    active_stop=stop,
                )
            )
            db.commit()
            db.refresh(record)
            state_changed = True
            database_mutated = True

        # Terminal positions remain immutable on repeated reads.
        if PositionState(record.state) not in TERMINAL_POSITION_STATES:
            latest = MarketCandleRepository.find_latest(db, stock.stock_id, timeframe.value)
            if (
                latest is not None
                and record.last_evaluated_candle_time is not None
                and latest.candle_time > record.last_evaluated_candle_time
            ):
                rows = MarketCandleRepository.find_by_range(
                    db,
                    stock.stock_id,
                    timeframe.value,
                    record.last_evaluated_candle_time,
                    latest.candle_time,
                )
                now_utc = datetime.now(timezone.utc)
                session = session_for_stock(stock)
                for candle in rows:
                    if candle.candle_time <= record.last_evaluated_candle_time:
                        continue
                    if not is_regular_session_candle(candle.candle_time, session):
                        ignored_out_of_session_candles += 1
                        continue
                    if not is_completed_candle(candle.candle_time, timeframe.value, now_utc, session):
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

                    processed_candles += 1
                    record.last_evaluated_candle_time = candle.candle_time
                    record.active_stop = observation.active_stop
                    record.target_1_hit = observation.target_1_hit
                    record.target_2_hit = observation.target_2_hit
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
                                validation_run_id=record.validation_run_id,
                                strategy_version=record.strategy_version,
                                position_state_id=record.position_state_id,
                                stock_id=stock.stock_id,
                                timeframe=timeframe.value,
                                signal_cycle_number=cycle_number,
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
        observed_price = float(latest.close_price) if latest is not None else current_price
        return PositionLifecycleService._serialize(
            symbol,
            record,
            state_changed,
            observed_price,
            database_mutated=database_mutated,
            opening_gate_passed=True,
            opening_gate_reason=opening_gate_reason,
            processed_candles=processed_candles,
            ignored_out_of_session_candles=ignored_out_of_session_candles,
            ignored_incomplete_candles=ignored_incomplete_candles,
        )

    @staticmethod
    def get_current(db: Session, symbol: str, timeframe: MarketTimeframe) -> dict:
        symbol = symbol.strip().upper()
        stock = StockRepository.find_by_symbol(db, symbol)
        if stock is None:
            raise ValueError(f"Stock not found: {symbol}")
        record = PositionStateRepository.find_latest(db, stock.stock_id, timeframe.value)
        if record is None:
            return PositionLifecycleService._not_open(
                symbol=symbol,
                timeframe=timeframe,
                cycle_number=0,
                current_price=None,
                reason="No analytical post-entry position has been created yet",
                opening_gate_passed=False,
            )
        latest = MarketCandleRepository.find_latest(db, stock.stock_id, timeframe.value)
        current_price = float(latest.close_price) if latest is not None else None
        return PositionLifecycleService._serialize(
            symbol,
            record,
            False,
            current_price,
            database_mutated=False,
            opening_gate_passed=True,
            opening_gate_reason="Persistent position already exists for its signal cycle",
            processed_candles=0,
            ignored_out_of_session_candles=0,
            ignored_incomplete_candles=0,
        )

    @staticmethod
    def get_history(db: Session, symbol: str, timeframe: MarketTimeframe, limit: int = 50) -> dict:
        symbol = symbol.strip().upper()
        stock = StockRepository.find_by_symbol(db, symbol)
        if stock is None:
            raise ValueError(f"Stock not found: {symbol}")
        rows = PositionStateRepository.history(db, stock.stock_id, timeframe.value, limit)
        return {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "execution_mode": PositionLifecycleService.EXECUTION_MODE,
            "persistence_mode": PositionLifecycleService.PERSISTENCE_MODE,
            "broker_order_submitted": False,
            "transitions": [
                {
                    "from_state": row.from_state,
                    "to_state": row.to_state,
                    "event": row.event,
                    "reason": row.reason,
                    "candle_time": row.candle_time,
                    "observed_price": float(row.observed_price) if row.observed_price is not None else None,
                    "active_stop": float(row.active_stop) if row.active_stop is not None else None,
                    "signal_cycle_number": row.signal_cycle_number,
                    "created_at": row.created_at,
                }
                for row in rows
            ],
        }

    @staticmethod
    def _not_open(
        *,
        symbol: str,
        timeframe: MarketTimeframe,
        cycle_number: int,
        current_price: float | None,
        reason: str,
        opening_gate_passed: bool,
    ) -> dict:
        return {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "execution_mode": PositionLifecycleService.EXECUTION_MODE,
            "persistence_mode": PositionLifecycleService.PERSISTENCE_MODE,
            "broker_order_submitted": False,
            "database_mutated": False,
            "opening_gate_passed": opening_gate_passed,
            "opening_gate_reason": reason,
            "processed_candles": 0,
            "ignored_out_of_session_candles": 0,
            "ignored_incomplete_candles": 0,
            "state": "NOT_OPEN",
            "previous_state": None,
            "last_event": "NO_POSITION",
            "state_changed": False,
            "reason": reason,
            "signal_cycle_number": cycle_number,
            "entry_price": None,
            "initial_stop": None,
            "active_stop": None,
            "target_1": None,
            "target_2": None,
            "initial_risk_per_share": None,
            "target_1_hit": False,
            "target_2_hit": False,
            "opened_at": None,
            "last_evaluated_candle_time": None,
            "current_price": current_price,
            "unrealized_per_share": None,
            "unrealized_r": None,
            "exit_price": None,
            "exit_reason": None,
            "closed_at": None,
            "version": None,
        }

    @staticmethod
    def _serialize(
        symbol: str,
        record: PositionStateRecord,
        state_changed: bool,
        current_price: float | None,
        *,
        database_mutated: bool,
        opening_gate_passed: bool,
        opening_gate_reason: str,
        processed_candles: int,
        ignored_out_of_session_candles: int,
        ignored_incomplete_candles: int,
    ) -> dict:
        entry = float(record.entry_price)
        risk = float(record.initial_risk_per_share)
        unrealized = None
        unrealized_r = None
        if current_price is not None and record.state not in {PositionState.STOP_HIT.value, PositionState.TARGET_2_HIT.value}:
            unrealized = round(current_price - entry, 6)
            unrealized_r = round(unrealized / risk, 4) if risk > 0 else None
        return {
            "symbol": symbol,
            "timeframe": record.timeframe,
            "execution_mode": PositionLifecycleService.EXECUTION_MODE,
            "persistence_mode": PositionLifecycleService.PERSISTENCE_MODE,
            "broker_order_submitted": False,
            "database_mutated": database_mutated,
            "opening_gate_passed": opening_gate_passed,
            "opening_gate_reason": opening_gate_reason,
            "processed_candles": processed_candles,
            "ignored_out_of_session_candles": ignored_out_of_session_candles,
            "ignored_incomplete_candles": ignored_incomplete_candles,
            "state": record.state,
            "previous_state": record.previous_state,
            "last_event": record.last_event,
            "state_changed": state_changed,
            "reason": record.reason,
            "signal_cycle_number": record.signal_cycle_number,
            "entry_price": entry,
            "quantity": int(record.quantity or 0),
            "initial_stop": float(record.initial_stop),
            "active_stop": float(record.active_stop),
            "target_1": float(record.target_1) if record.target_1 is not None else None,
            "target_2": float(record.target_2) if record.target_2 is not None else None,
            "initial_risk_per_share": risk,
            "target_1_hit": bool(record.target_1_hit),
            "target_2_hit": bool(record.target_2_hit),
            "opened_at": record.opened_at,
            "last_evaluated_candle_time": record.last_evaluated_candle_time,
            "current_price": current_price,
            "unrealized_per_share": unrealized,
            "unrealized_r": unrealized_r,
            "exit_price": float(record.exit_price) if record.exit_price is not None else None,
            "exit_reason": record.exit_reason,
            "closed_at": record.closed_at,
            "version": record.version,
        }
