from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AutoTrade(Base):
    """One automatic paper position opened by the trading cycle.

    Remembers WHO opened it (watchlist/user), with WHICH settings (holding
    style, trail %) and WHEN it must be closed. The broker only knows the
    position, not why it exists, so this is what time exits and per-user
    trailing stops are driven from.
    """

    __tablename__ = "auto_trade"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True, index=True
    )
    watchlist_id: Mapped[int | None] = mapped_column(
        ForeignKey("watchlist.watchlist_id", ondelete="SET NULL"), nullable=True
    )
    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stock.stock_id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    broker: Mapped[str] = mapped_column(String(20), nullable=False, default="ALPACA_PAPER")
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    holding_style: Mapped[str] = mapped_column(String(10), nullable=False)
    # BREAKOUT | SUPPORT_BOUNCE - which entry rule opened the position
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False, default="BREAKOUT")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    stop_loss_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    trail_percent: Mapped[float | None] = mapped_column(Float, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    exit_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # OPEN | CLOSED
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="OPEN", index=True)
    # SESSION_CLOSE | TIME_EXIT | BROKER_EXIT (stop/target/trailing hit at the broker)
    exit_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    exit_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
