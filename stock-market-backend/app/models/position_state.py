from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PositionStateRecord(Base):
    __tablename__ = "position_state"
    __table_args__ = (
        UniqueConstraint("stock_id", "timeframe", "signal_cycle_number", name="uq_position_state_stock_timeframe_cycle"),
    )

    validation_run_id: Mapped[int | None] = mapped_column(ForeignKey("validation_run.validation_run_id", ondelete="SET NULL"), nullable=True, index=True)
    strategy_version: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    position_state_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stock.stock_id", ondelete="CASCADE"), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    signal_cycle_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    previous_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_event: Mapped[str] = mapped_column(String(60), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)

    entry_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    initial_stop: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    active_stop: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    target_1: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    target_2: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    initial_risk_per_share: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    target_1_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    target_2_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_evaluated_candle_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    quantity: Mapped[int] = mapped_column(Integer,nullable=False,default=0,)

class PositionStateHistory(Base):
    __tablename__ = "position_state_history"

    validation_run_id: Mapped[int | None] = mapped_column(ForeignKey("validation_run.validation_run_id", ondelete="SET NULL"), nullable=True, index=True)
    strategy_version: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    position_state_history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    position_state_id: Mapped[int] = mapped_column(ForeignKey("position_state.position_state_id", ondelete="CASCADE"), nullable=False, index=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stock.stock_id", ondelete="CASCADE"), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    signal_cycle_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    from_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(60), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    candle_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    active_stop: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
