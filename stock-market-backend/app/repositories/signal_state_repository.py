from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.signal_state import SignalStateHistory, SignalStateRecord


class SignalStateRepository:
    @staticmethod
    def find_current(db: Session, stock_id: int, timeframe: str) -> SignalStateRecord | None:
        stmt = select(SignalStateRecord).where(
            SignalStateRecord.stock_id == stock_id,
            SignalStateRecord.timeframe == timeframe,
        )
        return db.scalar(stmt)

    @staticmethod
    def history(db: Session, stock_id: int, timeframe: str, limit: int = 50) -> list[SignalStateHistory]:
        stmt = (
            select(SignalStateHistory)
            .where(
                SignalStateHistory.stock_id == stock_id,
                SignalStateHistory.timeframe == timeframe,
            )
            .order_by(SignalStateHistory.signal_state_history_id.desc())
            .limit(limit)
        )
        return list(db.scalars(stmt).all())
    @staticmethod
    def latest_transition_to_state(
        db: Session, stock_id: int, timeframe: str, to_state: str
    ) -> SignalStateHistory | None:
        stmt = (
            select(SignalStateHistory)
            .where(
                SignalStateHistory.stock_id == stock_id,
                SignalStateHistory.timeframe == timeframe,
                SignalStateHistory.to_state == to_state,
            )
            .order_by(SignalStateHistory.signal_state_history_id.desc())
            .limit(1)
        )
        return db.scalar(stmt)

