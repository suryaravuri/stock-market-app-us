from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketAlert(Base):
    """Alerts from the live early-breakout watcher or TradingView webhooks.
    Informational only - nothing here places orders."""

    __tablename__ = "market_alert"
    __table_args__ = (
        # One early-breakout alert per symbol per forming candle.
        UniqueConstraint("source", "symbol", "candle_start", name="uq_market_alert_candle"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)   # EARLY_BREAKOUT | TRADINGVIEW
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    candle_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    level: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
