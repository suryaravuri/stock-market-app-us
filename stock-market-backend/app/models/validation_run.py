from datetime import datetime
from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class ValidationRun(Base):
    __tablename__ = "validation_run"
    validation_run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    strategy_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    validation_phase: Mapped[str] = mapped_column(String(80), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="ANALYSIS_ONLY")
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True, default="ACTIVE")
    baseline_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    baseline_manifest: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
