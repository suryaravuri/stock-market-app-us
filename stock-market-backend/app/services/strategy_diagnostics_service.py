from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.trade_journal_service import TradeJournalService
from app.strategies.strategy_diagnostics import diagnose_strategy


class StrategyDiagnosticsService:
    DIAGNOSTICS_MODE = "STRATEGY_DIAGNOSTICS_WEAKNESS_ANALYSIS"
    EXECUTION_MODE = "ANALYSIS_ONLY"

    @staticmethod
    def diagnostics(db: Session, scope: str = "ALL", symbol: str | None = None, timeframe: str | None = None, limit: int = 1000) -> dict:
        scope = TradeJournalService._normalize_scope(scope)
        symbol = symbol.strip().upper() if symbol else None
        timeframe = timeframe.strip() if timeframe else None
        entries = TradeJournalService._entries(db, scope, symbol, timeframe, limit)
        result = diagnose_strategy(entries)
        return {
            "diagnostics_mode": StrategyDiagnosticsService.DIAGNOSTICS_MODE,
            "execution_mode": StrategyDiagnosticsService.EXECUTION_MODE,
            "scope_requested": scope,
            "diagnostic_scope": "PRODUCTION_ANALYTICAL_ONLY",
            "broker_order_submitted": False,
            "database_mutated": False,
            "production_position_tables_mutated": False,
            "symbol_filter": symbol,
            "timeframe_filter": timeframe,
            **result,
        }
