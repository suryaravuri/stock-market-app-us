from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SignalStateRecord(Base):
    __tablename__ = "signal_state"
    __table_args__ = (
        UniqueConstraint("stock_id", "timeframe", name="uq_signal_state_stock_timeframe"),
    )

    validation_run_id: Mapped[int | None] = mapped_column(ForeignKey("validation_run.validation_run_id", ondelete="SET NULL"), nullable=True, index=True)
    strategy_version: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    signal_state_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stock.stock_id", ondelete="CASCADE"), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    previous_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_event: Mapped[str] = mapped_column(String(60), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    observed_breakout_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    breakout_level: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    confirmation_price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    confirmed_entry_price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    signal_candle_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cycle_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class SignalStateHistory(Base):
    __tablename__ = "signal_state_history"

    validation_run_id: Mapped[int | None] = mapped_column(ForeignKey("validation_run.validation_run_id", ondelete="SET NULL"), nullable=True, index=True)
    strategy_version: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    signal_state_history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stock.stock_id", ondelete="CASCADE"), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    from_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(60), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    observed_breakout_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    signal_candle_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
