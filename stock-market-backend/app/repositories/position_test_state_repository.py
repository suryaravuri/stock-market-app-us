from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.position_test_state import PositionTestCandleObservation, PositionTestStateHistory, PositionTestStateRecord


class PositionTestStateRepository:
    @staticmethod
    def find(db: Session, test_run_id: str) -> PositionTestStateRecord | None:
        return db.scalar(select(PositionTestStateRecord).where(PositionTestStateRecord.test_run_id == test_run_id))

    @staticmethod
    def history(db: Session, test_run_id: str) -> list[PositionTestStateHistory]:
        stmt = (
            select(PositionTestStateHistory)
            .where(PositionTestStateHistory.test_run_id == test_run_id)
            .order_by(PositionTestStateHistory.position_test_state_history_id.asc())
        )
        return list(db.scalars(stmt).all())


    @staticmethod
    def observations(db: Session, test_run_id: str) -> list[PositionTestCandleObservation]:
        stmt = (
            select(PositionTestCandleObservation)
            .where(PositionTestCandleObservation.test_run_id == test_run_id)
            .order_by(PositionTestCandleObservation.candle_time.asc())
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def delete_run(db: Session, test_run_id: str) -> bool:
        record = PositionTestStateRepository.find(db, test_run_id)
        if record is None:
            return False
        db.delete(record)
        db.commit()
        return True

    @staticmethod
    def list_closed(db: Session, symbol: str | None = None, timeframe: str | None = None, limit: int = 500) -> list[PositionTestStateRecord]:
        stmt = select(PositionTestStateRecord).where(
            PositionTestStateRecord.state.in_(["STOP_HIT", "TARGET_2_HIT"]),
            PositionTestStateRecord.closed_at.is_not(None),
            PositionTestStateRecord.exit_price.is_not(None),
        )
        if symbol is not None:
            stmt = stmt.where(PositionTestStateRecord.symbol == symbol.upper())
        if timeframe is not None:
            stmt = stmt.where(PositionTestStateRecord.timeframe == timeframe)
        stmt = stmt.order_by(PositionTestStateRecord.closed_at.desc(), PositionTestStateRecord.position_test_state_id.desc()).limit(limit)
        return list(db.scalars(stmt).all())
