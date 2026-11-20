from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MarketCandle(Base):
    __tablename__ = "market_candle"

    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "timeframe",
            "candle_time",
            name="uq_market_candle_stock_timeframe_time",
        ),
    )

    candle_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    stock_id: Mapped[int] = mapped_column(
        ForeignKey(
            "stock.stock_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    timeframe: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
    )

    candle_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    open_price: Mapped[float] = mapped_column(
        Numeric(18, 6),
        nullable=False,
    )

    high_price: Mapped[float] = mapped_column(
        Numeric(18, 6),
        nullable=False,
    )

    low_price: Mapped[float] = mapped_column(
        Numeric(18, 6),
        nullable=False,
    )

    close_price: Mapped[float] = mapped_column(
        Numeric(18, 6),
        nullable=False,
    )

    volume: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    trade_count: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    vwap: Mapped[float | None] = mapped_column(
        Numeric(18, 6),
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="ALPACA",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )