from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PositionTestStateRecord(Base):
    __tablename__ = "position_test_state"

    position_test_state_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    test_run_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stock.stock_id", ondelete="CASCADE"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
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
    analytics_candle_source: Mapped[str] = mapped_column(String(40), nullable=False, default="SYNTHETIC_UNRECORDED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PositionTestStateHistory(Base):
    __tablename__ = "position_test_state_history"

    position_test_state_history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    position_test_state_id: Mapped[int] = mapped_column(ForeignKey("position_test_state.position_test_state_id", ondelete="CASCADE"), nullable=False, index=True)
    test_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    from_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_state: Mapped[str] = mapped_column(String(40), nullable=False)
    event: Mapped[str] = mapped_column(String(60), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    candle_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    active_stop: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PositionTestCandleObservation(Base):
    __tablename__ = "position_test_candle_observation"

    position_test_candle_observation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    position_test_state_id: Mapped[int] = mapped_column(ForeignKey("position_test_state.position_test_state_id", ondelete="CASCADE"), nullable=False, index=True)
    test_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    candle_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    high_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    low_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    close_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
