from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Stock(Base):
    __tablename__ = "stock"

    stock_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    symbol: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True
    )

    company_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    exchange: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True
    )

    # Zerodha instrument_token for NSE/BSE stocks; resolved and cached on first sync.
    instrument_token: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True
    )

    asset_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="STOCK"
    )

    sector: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    industry: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    tradable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"Stock(stock_id={self.stock_id}, "
            f"symbol='{self.symbol}', "
            f"company_name='{self.company_name}')"
        )