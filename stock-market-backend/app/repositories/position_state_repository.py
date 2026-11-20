from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.position_state import PositionStateHistory, PositionStateRecord


class PositionStateRepository:
    @staticmethod
    def find_cycle(db: Session, stock_id: int, timeframe: str, cycle_number: int) -> PositionStateRecord | None:
        stmt = select(PositionStateRecord).where(
            PositionStateRecord.stock_id == stock_id,
            PositionStateRecord.timeframe == timeframe,
            PositionStateRecord.signal_cycle_number == cycle_number,
        )
        return db.scalar(stmt)

    @staticmethod
    def find_latest(db: Session, stock_id: int, timeframe: str) -> PositionStateRecord | None:
        stmt = (
            select(PositionStateRecord)
            .where(PositionStateRecord.stock_id == stock_id, PositionStateRecord.timeframe == timeframe)
            .order_by(PositionStateRecord.signal_cycle_number.desc())
            .limit(1)
        )
        return db.scalar(stmt)

    @staticmethod
    def history(db: Session, stock_id: int, timeframe: str, limit: int = 50) -> list[PositionStateHistory]:
        stmt = (
            select(PositionStateHistory)
            .where(PositionStateHistory.stock_id == stock_id, PositionStateHistory.timeframe == timeframe)
            .order_by(PositionStateHistory.created_at.desc(), PositionStateHistory.position_state_history_id.desc())
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def list_closed(db: Session, symbol_stock_id: int | None = None, timeframe: str | None = None, limit: int = 500) -> list[PositionStateRecord]:
        stmt = select(PositionStateRecord).where(
            PositionStateRecord.state.in_(["STOP_HIT", "TARGET_2_HIT"]),
            PositionStateRecord.closed_at.is_not(None),
            PositionStateRecord.exit_price.is_not(None),
        )
        if symbol_stock_id is not None:
            stmt = stmt.where(PositionStateRecord.stock_id == symbol_stock_id)
        if timeframe is not None:
            stmt = stmt.where(PositionStateRecord.timeframe == timeframe)
        stmt = stmt.order_by(PositionStateRecord.closed_at.desc(), PositionStateRecord.position_state_id.desc()).limit(limit)
        return list(db.scalars(stmt).all())
