from __future__ import annotations

import math

from app.strategies.strategy_quality import calculate_strategy_quality


class StrategyQualitySimulationService:
    """#15G-5 DB-free validation harness for the strategy quality formula.

    The supplied R values are treated as hypothetical production-analytical
    outcomes only inside this in-memory calculation. Nothing is persisted and
    nothing is submitted to a broker.
    """

    SIMULATION_MODE = "STATELESS_QUALITY_SCORE_VALIDATION"
    EXECUTION_MODE = "ANALYSIS_ONLY"
    PERSISTENCE_MODE = "NONE"
    MAX_TRADES = 5000

    @staticmethod
    def simulate(realized_r_values: list[float]) -> dict:
        if not realized_r_values:
            raise ValueError("realized_r_values must contain at least one trade")
        if len(realized_r_values) > StrategyQualitySimulationService.MAX_TRADES:
            raise ValueError(
                f"realized_r_values cannot contain more than {StrategyQualitySimulationService.MAX_TRADES} trades"
            )

        normalized: list[float] = []
        for idx, value in enumerate(realized_r_values):
            r = float(value)
            if not math.isfinite(r):
                raise ValueError(f"realized_r_values[{idx}] must be a finite number")
            normalized.append(r)

        entries = []
        for idx, r in enumerate(normalized, start=1):
            if r > 0:
                outcome = "WIN"
            elif r < 0:
                outcome = "LOSS"
            else:
                outcome = "BREAKEVEN"
            entries.append(
                {
                    "source": "PRODUCTION_ANALYTICAL",
                    "position_id": f"SIM-{idx}",
                    "symbol": "SIMULATION",
                    "timeframe": "SIMULATION",
                    "outcome": outcome,
                    "realized_r": r,
                }
            )

        quality = calculate_strategy_quality(entries)

        validation_status = "PASS"
        summary = (
            f"Stateless validation over {len(normalized)} hypothetical trade(s): "
            f"win rate {quality['win_rate_pct']:.2f}%, average R "
            f"{quality['average_r']:+.4f}R, quality {quality['quality_score']:.2f}/100, "
            f"grade {quality['quality_grade']}, confidence {quality['confidence']}."
        )

        return {
            "simulation_mode": StrategyQualitySimulationService.SIMULATION_MODE,
            "execution_mode": StrategyQualitySimulationService.EXECUTION_MODE,
            "persistence_mode": StrategyQualitySimulationService.PERSISTENCE_MODE,
            "broker_order_submitted": False,
            "database_mutated": False,
            "production_position_tables_mutated": False,
            "trades_received": len(normalized),
            **quality,
            "validation_status": validation_status,
            "summary": summary,
        }
