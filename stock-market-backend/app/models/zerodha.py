from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ZerodhaSession(Base):
    """One linked Zerodha login per app user. The token expires daily."""

    __tablename__ = "zerodha_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    kite_user_id: Mapped[str] = mapped_column(String(40), nullable=False)
    kite_user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    login_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ZerodhaOrder(Base):
    """Audit row for every order attempt, whether sent, dry-run or rejected."""

    __tablename__ = "zerodha_order"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kite_user_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False)
    tradingsymbol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    product: Mapped[str] = mapped_column(String(10), nullable=False)
    order_type: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    limit_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    last_price: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    # SUBMITTED | DRY_RUN | REJECTED | FAILED | CANCEL_REQUESTED
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    kite_order_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    reasons: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Latest state reported by Zerodha (COMPLETE, REJECTED, CANCELLED, OPEN...).
    kite_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    kite_status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    filled_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_price: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class ZerodhaTrade(Base):
    """One executed fill, copied from Kite's same-day trade book.

    Kite only returns today's trades, so fills are stored here to build history.
    """

    __tablename__ = "zerodha_trade"
    __table_args__ = (
        UniqueConstraint("user_id", "kite_trade_id", name="uq_zerodha_trade_user_trade"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kite_user_id: Mapped[str] = mapped_column(String(40), nullable=False)
    kite_trade_id: Mapped[str] = mapped_column(String(40), nullable=False)
    kite_order_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False)
    tradingsymbol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    product: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    fill_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
