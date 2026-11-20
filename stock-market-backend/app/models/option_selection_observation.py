from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.option_contract import OptionContract
    from app.models.stock import Stock


class OptionSelectionObservation(Base):
    __tablename__ = "option_selection_observation"

    observation_id: Mapped[int] = mapped_column(
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

    # Nullable because NO_QUALIFIED_CONTRACT has no selection.
    option_contract_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "option_contract.option_contract_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    option_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    selection_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    selection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    underlying_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    candidates_examined: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    candidates_qualified: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # -----------------------------
    # Selected-contract snapshot
    # -----------------------------

    bid_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4),
        nullable=True,
    )

    ask_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4),
        nullable=True,
    )

    midpoint: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4),
        nullable=True,
    )

    spread_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    strike_distance_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    dte: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    open_interest: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    implied_volatility: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    delta: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    gamma: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    theta: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    vega: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    rho: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    underlying_stock: Mapped["Stock"] = relationship()

    option_contract: Mapped["OptionContract | None"] = relationship()