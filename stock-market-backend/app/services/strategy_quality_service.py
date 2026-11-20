from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.trade_journal_service import TradeJournalService
from app.strategies.strategy_quality import calculate_quality_breakdown, calculate_strategy_quality


class StrategyQualityService:
    QUALITY_MODE = "STRATEGY_PERFORMANCE_QUALITY_SCORE"
    EXECUTION_MODE = "ANALYSIS_ONLY"

    @staticmethod
    def quality(db: Session, scope: str = "ALL", symbol: str | None = None, timeframe: str | None = None, limit: int = 1000) -> dict:
        scope = TradeJournalService._normalize_scope(scope)
        symbol = symbol.strip().upper() if symbol else None
        timeframe = timeframe.strip() if timeframe else None

        # Always fetch ALL requested evidence so the response can explicitly show
        # how many isolated tests were excluded. The scoring function itself only
        # accepts PRODUCTION_ANALYTICAL rows as real strategy evidence.
        entries = TradeJournalService._entries(db, scope, symbol, timeframe, limit)
        quality = calculate_strategy_quality(entries)
        by_symbol = calculate_quality_breakdown(entries, "symbol")
        by_timeframe = calculate_quality_breakdown(entries, "timeframe")

        if quality["assessment"] == "NOT_EVALUABLE":
            summary = (
                f"Strategy quality is not yet evaluable: 0 completed production analytical trades; "
                f"{quality['isolated_test_trade_count']} isolated validation trade(s) excluded from scoring."
            )
        else:
            summary = (
                f"{quality['real_market_trade_count']} completed production analytical trade(s); "
                f"quality {quality['quality_grade']} ({quality['quality_score']:.2f}/100), "
                f"confidence {quality['confidence']}."
            )

        return {
            "quality_mode": StrategyQualityService.QUALITY_MODE,
            "execution_mode": StrategyQualityService.EXECUTION_MODE,
            "scope_requested": scope,
            "scoring_scope": "PRODUCTION_ANALYTICAL_ONLY",
            "broker_order_submitted": False,
            "production_position_tables_mutated": False,
            "symbol_filter": symbol,
            "timeframe_filter": timeframe,
            **quality,
            "by_symbol": by_symbol,
            "by_timeframe": by_timeframe,
            "summary": summary,
        }
