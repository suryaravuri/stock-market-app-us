from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.stock import Stock


class OptionContract(Base):
    __tablename__ = "option_contract"

    option_contract_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    underlying_stock_id: Mapped[int] = mapped_column(
        ForeignKey(
            "stock.stock_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    contract_symbol: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    option_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    strike_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    expiration_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    multiplier: Mapped[int] = mapped_column(
        nullable=False,
        default=100,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    underlying_stock: Mapped["Stock"] = relationship()