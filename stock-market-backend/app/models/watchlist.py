from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.stock import Stock
    from app.models.user import AppUser

class Watchlist(Base):
    __tablename__ = "watchlist"

    watchlist_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
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

    user: Mapped["AppUser"] = relationship()

    stocks: Mapped[list["WatchlistStock"]] = relationship(
        back_populates="watchlist",
        cascade="all, delete-orphan",
    )
class WatchlistStock(Base):
    __tablename__ = "watchlist_stock"

    watchlist_id: Mapped[int] = mapped_column(
        ForeignKey(
            "watchlist.watchlist_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    stock_id: Mapped[int] = mapped_column(
        ForeignKey(
            "stock.stock_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    analysis_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    trading_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    profit_target_percent: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=5.0,
        server_default="5.0",
    )

    loss_limit_percent: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=5.0,
        server_default="5.0",
    )

    # SWING (no time limit) | INTRADAY | WEEKLY | MONTHLY
    holding_style: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="SWING",
        server_default="SWING",
    )

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    watchlist: Mapped["Watchlist"] = relationship(
        back_populates="stocks",
    )

    stock: Mapped["Stock"] = relationship()