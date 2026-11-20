from __future__ import annotations

import math

from app.strategies.strategy_diagnostics import diagnose_strategy


class StrategyDiagnosticsSimulationService:
    """#15H-5 stateless, DB-free weakness-diagnostics validation harness.

    Request trades are treated as hypothetical production analytical outcomes
    only for this in-memory calculation. No database rows are created or
    changed and no broker integration is invoked.
    """

    SIMULATION_MODE = "STATELESS_DIAGNOSTICS_VALIDATION"
    DIAGNOSTICS_MODE = "STRATEGY_DIAGNOSTICS_WEAKNESS_ANALYSIS"
    EXECUTION_MODE = "ANALYSIS_ONLY"
    PERSISTENCE_MODE = "NONE"
    MAX_TRADES = 5000

    @staticmethod
    def simulate(trades) -> dict:
        if not trades:
            raise ValueError("trades must contain at least one hypothetical completed trade")
        if len(trades) > StrategyDiagnosticsSimulationService.MAX_TRADES:
            raise ValueError(
                f"trades cannot contain more than {StrategyDiagnosticsSimulationService.MAX_TRADES} items"
            )

        entries: list[dict] = []
        for idx, item in enumerate(trades, start=1):
            # Support both Pydantic request models and plain dicts for unit tests.
            value = item.model_dump() if hasattr(item, "model_dump") else dict(item)
            r = float(value.get("realized_r"))
            hold = float(value.get("holding_minutes", 60.0))
            if not math.isfinite(r):
                raise ValueError(f"trades[{idx - 1}].realized_r must be a finite number")
            if not math.isfinite(hold) or hold < 0:
                raise ValueError(f"trades[{idx - 1}].holding_minutes must be a finite non-negative number")

            symbol = str(value.get("symbol") or "SIMULATION").strip().upper()
            timeframe = str(value.get("timeframe") or "15Min").strip()
            if not symbol:
                raise ValueError(f"trades[{idx - 1}].symbol cannot be blank")
            if not timeframe:
                raise ValueError(f"trades[{idx - 1}].timeframe cannot be blank")

            if r > 0:
                outcome = "WIN"
            elif r < 0:
                outcome = "LOSS"
            else:
                outcome = "BREAKEVEN"

            state = value.get("state")
            exit_reason = value.get("exit_reason")
            if not state:
                state = "TARGET_2_HIT" if r > 0 else "STOP_HIT" if r < 0 else "STOP_HIT"
            if not exit_reason:
                if state == "TARGET_2_HIT":
                    exit_reason = "TARGET_2"
                elif state == "STOP_HIT":
                    exit_reason = "INITIAL_STOP" if r <= 0 else "TRAILING_STOP"
                else:
                    exit_reason = "SIMULATED_EXIT"

            entries.append(
                {
                    "source": "PRODUCTION_ANALYTICAL",
                    "position_id": f"DIAG-SIM-{idx}",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "outcome": outcome,
                    "realized_r": r,
                    "state": str(state),
                    "exit_reason": str(exit_reason),
                    "holding_minutes": hold,
                }
            )

        diagnostics = diagnose_strategy(entries)
        return {
            "simulation_mode": StrategyDiagnosticsSimulationService.SIMULATION_MODE,
            "diagnostics_mode": StrategyDiagnosticsSimulationService.DIAGNOSTICS_MODE,
            "execution_mode": StrategyDiagnosticsSimulationService.EXECUTION_MODE,
            "persistence_mode": StrategyDiagnosticsSimulationService.PERSISTENCE_MODE,
            "diagnostic_scope": "HYPOTHETICAL_PRODUCTION_ANALYTICAL_ONLY",
            "broker_order_submitted": False,
            "database_mutated": False,
            "production_position_tables_mutated": False,
            "trades_received": len(entries),
            **diagnostics,
            "validation_status": "PASS",
            "summary": (
                f"Stateless diagnostics validation over {len(entries)} hypothetical trade(s): "
                f"{diagnostics['weakness_count']} prioritized weakness(es), "
                f"{len(diagnostics['strengths'])} strength(s)."
            ),
        }
