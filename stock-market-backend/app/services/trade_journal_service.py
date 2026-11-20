from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.position_state_repository import PositionStateRepository
from app.repositories.position_test_state_repository import PositionTestStateRepository
from app.repositories.stock_repository import StockRepository
from app.strategies.trade_performance import calculate_trade_statistics


class TradeJournalService:
    """#15F read-only trade journal and aggregate performance statistics.

    Uses only terminal analytical positions. No broker calls and no database writes.
    Results are per-share because analytical position quantity is not yet persisted.
    """

    JOURNAL_MODE = "TRADE_JOURNAL"
    STATISTICS_MODE = "TRADE_PERFORMANCE_STATISTICS"
    EXECUTION_MODE = "ANALYSIS_ONLY"
    VALID_SCOPES = {"PRODUCTION", "ISOLATED_TEST", "ALL"}

    @staticmethod
    def journal(db: Session, scope: str = "ALL", symbol: str | None = None, timeframe: str | None = None, limit: int = 200) -> dict:
        scope = TradeJournalService._normalize_scope(scope)
        symbol = symbol.strip().upper() if symbol else None
        timeframe = timeframe.strip() if timeframe else None
        entries = TradeJournalService._entries(db, scope, symbol, timeframe, max(limit, 1))
        return {
            "journal_mode": TradeJournalService.JOURNAL_MODE,
            "execution_mode": TradeJournalService.EXECUTION_MODE,
            "scope": scope,
            "broker_order_submitted": False,
            "production_position_tables_mutated": False,
            "symbol_filter": symbol,
            "timeframe_filter": timeframe,
            "total_completed_trades": len(entries),
            "returned_trades": min(len(entries), limit),
            "entries": entries[:limit],
        }

    @staticmethod
    def performance(db: Session, scope: str = "ALL", symbol: str | None = None, timeframe: str | None = None, limit: int = 500) -> dict:
        scope = TradeJournalService._normalize_scope(scope)
        symbol = symbol.strip().upper() if symbol else None
        timeframe = timeframe.strip() if timeframe else None
        entries = TradeJournalService._entries(db, scope, symbol, timeframe, limit)
        stats = TradeJournalService.calculate_statistics(entries)
        return {
            "statistics_mode": TradeJournalService.STATISTICS_MODE,
            "execution_mode": TradeJournalService.EXECUTION_MODE,
            "scope": scope,
            "broker_order_submitted": False,
            "production_position_tables_mutated": False,
            "symbol_filter": symbol,
            "timeframe_filter": timeframe,
            **stats,
        }

    @staticmethod
    def _normalize_scope(scope: str) -> str:
        value = scope.strip().upper()
        if value not in TradeJournalService.VALID_SCOPES:
            raise ValueError("scope must be one of PRODUCTION, ISOLATED_TEST, ALL")
        return value

    @staticmethod
    def _entries(db: Session, scope: str, symbol: str | None, timeframe: str | None, limit: int) -> list[dict]:
        entries: list[dict] = []
        if scope in {"PRODUCTION", "ALL"}:
            stock_id = None
            if symbol:
                stock = StockRepository.find_by_symbol(db, symbol)
                if stock is None:
                    return [] if scope == "PRODUCTION" else TradeJournalService._test_entries(db, symbol, timeframe, limit)
                stock_id = stock.stock_id
            records = PositionStateRepository.list_closed(db, stock_id, timeframe, limit)
            for r in records:
                stock = StockRepository.find_by_id(db, r.stock_id)
                if stock is None:
                    continue
                entries.append(TradeJournalService._record_to_entry(
                    source="PRODUCTION_ANALYTICAL",
                    position_id=str(r.position_state_id),
                    test_run_id=None,
                    symbol=stock.symbol,
                    timeframe=r.timeframe,
                    state=r.state,
                    entry_price=float(r.entry_price),
                    exit_price=float(r.exit_price),
                    risk=float(r.initial_risk_per_share),
                    opened_at=r.opened_at,
                    closed_at=r.closed_at,
                    exit_reason=r.exit_reason,
                    signal_cycle_number=r.signal_cycle_number,
                    analytics_candle_source="MARKET_CANDLE",
                ))

        if scope in {"ISOLATED_TEST", "ALL"}:
            entries.extend(TradeJournalService._test_entries(db, symbol, timeframe, limit))

        entries.sort(key=lambda x: x["closed_at"], reverse=True)
        return entries[:limit]

    @staticmethod
    def _test_entries(db: Session, symbol: str | None, timeframe: str | None, limit: int) -> list[dict]:
        result = []
        for r in PositionTestStateRepository.list_closed(db, symbol, timeframe, limit):
            result.append(TradeJournalService._record_to_entry(
                source="ISOLATED_TEST",
                position_id=str(r.position_test_state_id),
                test_run_id=r.test_run_id,
                symbol=r.symbol,
                timeframe=r.timeframe,
                state=r.state,
                entry_price=float(r.entry_price),
                exit_price=float(r.exit_price),
                risk=float(r.initial_risk_per_share),
                opened_at=r.opened_at,
                closed_at=r.closed_at,
                exit_reason=r.exit_reason,
                signal_cycle_number=None,
                analytics_candle_source=getattr(r, "analytics_candle_source", None),
            ))
        return result

    @staticmethod
    def _record_to_entry(*, source, position_id, test_run_id, symbol, timeframe, state, entry_price, exit_price, risk, opened_at, closed_at, exit_reason, signal_cycle_number, analytics_candle_source) -> dict:
        realized = round(exit_price - entry_price, 6)
        realized_r = round(realized / risk, 4) if risk > 0 else None
        outcome = "BREAKEVEN"
        if realized > 0:
            outcome = "WIN"
        elif realized < 0:
            outcome = "LOSS"
        holding = round((closed_at - opened_at).total_seconds() / 60.0, 2)
        return {
            "source": source,
            "position_id": position_id,
            "test_run_id": test_run_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "state": state,
            "outcome": outcome,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "realized_per_share": realized,
            "realized_r": realized_r,
            "opened_at": opened_at,
            "closed_at": closed_at,
            "holding_minutes": holding,
            "exit_reason": exit_reason,
            "signal_cycle_number": signal_cycle_number,
            "analytics_candle_source": analytics_candle_source,
        }

    @staticmethod
    def calculate_statistics(entries: list[dict]) -> dict:
        return calculate_trade_statistics(entries)
