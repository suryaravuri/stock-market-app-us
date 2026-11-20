"""Backtest runs and their trades. Stored in the MAIN database (small)."""
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BacktestRun(Base):
    __tablename__ = "backtest_run"

    backtest_run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    # QUEUED -> RUNNING -> COMPLETED | FAILED
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED", index=True)
    symbols: Mapped[str] = mapped_column(String(500), nullable=False)  # comma-separated
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    progress_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # {"overall": {...}, "by_symbol": {"AAPL": {...}}, "equity_curve": {"AAPL": [...]}}
    results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BacktestTrade(Base):
    __tablename__ = "backtest_trade"

    backtest_trade_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    backtest_run_id: Mapped[int] = mapped_column(
        ForeignKey("backtest_run.backtest_run_id", ondelete="CASCADE"), index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    signal_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entry_price: Mapped[float] = mapped_column(Float)
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exit_price: Mapped[float] = mapped_column(Float)
    shares: Mapped[int] = mapped_column(Integer)
    initial_stop: Mapped[float] = mapped_column(Float)
    final_stop: Mapped[float] = mapped_column(Float)
    target: Mapped[float] = mapped_column(Float)
    pnl: Mapped[float] = mapped_column(Float)
    pnl_percent: Mapped[float] = mapped_column(Float)
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str] = mapped_column(String(30))


class BacktestDataset(Base):
    """One uploaded CSV, received as rows (the file itself is never stored).

    Candles live in the BACKTEST database; this row only tracks the upload.
    """

    __tablename__ = "backtest_dataset"

    backtest_dataset_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source_timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    # UPLOADING -> READY | FAILED -> PURGED
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="UPLOADING")
    base_timeframe: Mapped[str | None] = mapped_column(String(10), nullable=True)
    chunks_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_bar: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_bar: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bars_by_timeframe: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
