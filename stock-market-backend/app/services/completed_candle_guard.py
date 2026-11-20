from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import and_, event, or_, select
from sqlalchemy.orm import Session

from app.models.market_candle import MarketCandle


class CompletedCandleGuard:
    """Temporarily constrain MarketCandle ORM reads to completed-bar cutoffs.

    #16C-1 deliberately implements the boundary outside the frozen V1 source
    files. This keeps SELECTION_ENGINE_V1's baseline hash unchanged while
    ensuring every candle read made by SetupService and its downstream services
    sees only bars whose *start timestamp* is at or before the supplied cutoff.
    """

    @staticmethod
    def latest_stored_candle(db: Session, stock_id: int, timeframe: str) -> datetime | None:
        stmt = (
            select(MarketCandle.candle_time)
            .where(
                MarketCandle.stock_id == stock_id,
                MarketCandle.timeframe == timeframe,
            )
            .order_by(MarketCandle.candle_time.desc())
            .limit(1)
        )
        return db.scalar(stmt)

    @classmethod
    @contextmanager
    def enforce(cls, db: Session, cutoffs: dict[str, datetime | None]):
        active = {name: cutoff for name, cutoff in cutoffs.items() if cutoff is not None}
        if not active:
            yield
            return

        def _listener(execute_state):
            if execute_state.session is not db or not execute_state.is_select:
                return

            statement = execute_state.statement
            # Only amend ORM statements that already select/load MarketCandle.
            # This avoids introducing the table into unrelated Stock/Watchlist queries.
            try:
                descriptions = statement.column_descriptions
            except AttributeError:
                return
            if not any(desc.get("entity") is MarketCandle for desc in descriptions):
                return

            clauses = [
                and_(
                    MarketCandle.timeframe == timeframe,
                    MarketCandle.candle_time <= cutoff,
                )
                for timeframe, cutoff in active.items()
            ]
            execute_state.statement = statement.where(or_(*clauses))

        event.listen(Session, "do_orm_execute", _listener)
        try:
            yield
        finally:
            event.remove(Session, "do_orm_execute", _listener)
