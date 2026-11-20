from __future__ import annotations

from app.schemas.position_lifecycle import PositionLifecycleSimulationRequest
from app.strategies.position_lifecycle import (
    PositionState,
    TERMINAL_POSITION_STATES,
    evaluate_long_position_candle,
)


class PositionLifecycleSimulationService:
    """Stateless validation harness for Improvement #15.

    It never opens a database transaction and never calls a broker. The supplied
    candles are evaluated in timestamp order with the exact same strategy used by
    the persisted analysis-only position lifecycle.
    """

    SIMULATION_MODE = "STATELESS_VALIDATION"
    EXECUTION_MODE = "ANALYSIS_ONLY"

    @staticmethod
    def simulate(symbol: str, request: PositionLifecycleSimulationRequest) -> dict:
        symbol = symbol.strip().upper()
        if not symbol:
            raise ValueError("Symbol is required")

        entry = float(request.entry_price)
        initial_stop = float(request.initial_stop)
        target_1 = float(request.target_1) if request.target_1 is not None else None
        target_2 = float(request.target_2) if request.target_2 is not None else None

        if entry <= 0:
            raise ValueError("entry_price must be greater than 0")
        if initial_stop <= 0:
            raise ValueError("initial_stop must be greater than 0")
        if initial_stop >= entry:
            raise ValueError("For a long simulation, initial_stop must be below entry_price")
        if target_1 is not None and target_1 <= entry:
            raise ValueError("target_1 must be above entry_price")
        if target_2 is not None and target_2 <= entry:
            raise ValueError("target_2 must be above entry_price")
        if target_1 is not None and target_2 is not None and target_2 <= target_1:
            raise ValueError("target_2 must be above target_1")
        if not request.candles:
            raise ValueError("At least one completed candle is required")

        previous_timestamp = None
        for index, candle in enumerate(request.candles, start=1):
            o = float(candle.open)
            h = float(candle.high)
            l = float(candle.low)
            c = float(candle.close)
            if min(o, h, l, c) <= 0:
                raise ValueError(f"Candle {index} contains a non-positive OHLC value")
            if h < max(o, c, l):
                raise ValueError(f"Candle {index} high must be >= open, close, and low")
            if l > min(o, c, h):
                raise ValueError(f"Candle {index} low must be <= open, close, and high")
            if previous_timestamp is not None and candle.timestamp <= previous_timestamp:
                raise ValueError("Simulation candles must be in strictly increasing timestamp order")
            previous_timestamp = candle.timestamp

        risk = entry - initial_stop
        state = PositionState.POSITION_OPEN
        active_stop = initial_stop
        target_1_hit = False
        target_2_hit = False
        observations: list[dict] = []
        evaluated = 0

        for candle in request.candles:
            if state in TERMINAL_POSITION_STATES:
                break

            before_state = state
            before_stop = active_stop
            result = evaluate_long_position_candle(
                state=state,
                candle_high=float(candle.high),
                candle_low=float(candle.low),
                candle_close=float(candle.close),
                entry_price=entry,
                initial_stop=initial_stop,
                active_stop=active_stop,
                target_1=target_1,
                target_2=target_2,
                target_1_hit=target_1_hit,
                initial_risk_per_share=risk,
            )
            evaluated += 1
            state = result.state
            active_stop = result.active_stop
            target_1_hit = result.target_1_hit
            target_2_hit = result.target_2_hit

            observations.append(
                {
                    "timestamp": candle.timestamp,
                    "from_state": before_state.value,
                    "to_state": result.state.value,
                    "event": result.event,
                    "changed": result.changed,
                    "reason": result.reason,
                    "candle_open": float(candle.open),
                    "candle_high": float(candle.high),
                    "candle_low": float(candle.low),
                    "candle_close": float(candle.close),
                    "active_stop_before": before_stop,
                    "active_stop_after": active_stop,
                    "target_1_hit": target_1_hit,
                    "target_2_hit": target_2_hit,
                    "exit_price": result.exit_price,
                    "exit_reason": result.exit_reason,
                }
            )

        return {
            "symbol": symbol,
            "timeframe": request.timeframe,
            "simulation_mode": PositionLifecycleSimulationService.SIMULATION_MODE,
            "execution_mode": PositionLifecycleSimulationService.EXECUTION_MODE,
            "broker_order_submitted": False,
            "database_mutated": False,
            "initial_state": PositionState.POSITION_OPEN.value,
            "final_state": state.value,
            "entry_price": entry,
            "initial_stop": initial_stop,
            "active_stop": active_stop,
            "target_1": target_1,
            "target_2": target_2,
            "initial_risk_per_share": risk,
            "target_1_hit": target_1_hit,
            "target_2_hit": target_2_hit,
            "terminal": state in TERMINAL_POSITION_STATES,
            "candles_received": len(request.candles),
            "candles_evaluated": evaluated,
            "validation_status": "PASS",
            "observations": observations,
        }
