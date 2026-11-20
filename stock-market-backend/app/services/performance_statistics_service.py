from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.position_state import PositionStateRecord
from app.models.stock import Stock
from app.models.watchlist import WatchlistStock


class PerformanceStatisticsService:

    EXECUTION_MODE = "ANALYSIS_ONLY"

    @staticmethod
    def get_performance(
        db: Session,
        start_date: date,
        end_date: date,
        watchlist_id: int | None = None,
    ) -> dict:

        if end_date < start_date:
            raise ValueError(
                "end_date must be greater than or equal to start_date"
            )

        start_datetime = datetime.combine(
            start_date,
            time.min,
            tzinfo=timezone.utc,
        )

        # Exclusive upper bound includes the entire end_date.
        end_datetime = datetime.combine(
            end_date + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )

        stmt = (
            select(
                PositionStateRecord,
                Stock.symbol,
            )
            .join(
                Stock,
                Stock.stock_id == PositionStateRecord.stock_id,
            )
           .where(
                or_(
                    (
                        (PositionStateRecord.opened_at >= start_datetime)
                        & (PositionStateRecord.opened_at < end_datetime)
                    ),
                    (
                        (PositionStateRecord.closed_at >= start_datetime)
                        & (PositionStateRecord.closed_at < end_datetime)
                    ),
                )
            )
            .order_by(
                PositionStateRecord.opened_at.asc(),
                PositionStateRecord.position_state_id.asc(),
            )
        )

        if watchlist_id is not None:
            stmt = (
                stmt
                .join(
                    WatchlistStock,
                    WatchlistStock.stock_id == PositionStateRecord.stock_id,
                )
                .where(
                    WatchlistStock.watchlist_id == watchlist_id,
                )
            )

        rows = db.execute(stmt).all()

        trades: list[dict] = []

        positions_opened = 0
        positions_closed = 0
        positions_still_open = 0

        winning_trades = 0
        losing_trades = 0
        breakeven_trades = 0

        total_profit_loss_per_share = 0.0

        shares_bought = 0
        shares_sold = 0

        total_buy_value = 0.0
        total_sell_value = 0.0

        gross_profit = 0.0
        gross_loss = 0.0
        net_profit_loss = 0.0

        bought_symbols: set[str] = set()
        sold_symbols: set[str] = set()
        opened_in_period = 0.0
        closed_in_period = 0.0


        for record, symbol in rows:

            opened_in_period = (
                record.opened_at is not None
                and start_datetime <= record.opened_at < end_datetime
            )

            closed_in_period = (
                record.closed_at is not None
                and start_datetime <= record.closed_at < end_datetime
            )

            entry_price = float(record.entry_price)

            exit_price = (
                float(record.exit_price)
                if record.exit_price is not None
                else None
            )

            # quantity=0 means legacy analytical position where
            # quantity was not persisted at the time it opened.
            quantity = int(record.quantity or 0)

            buy_value = round(
                entry_price * quantity,
                2,
            )

            # ---------------------------------
            # Opened during selected period
            # ---------------------------------
            if opened_in_period:
                positions_opened += 1
                bought_symbols.add(symbol)

                shares_bought += quantity
                total_buy_value += buy_value

            pnl_per_share = None
            sell_value = None
            profit_loss = None
            result = "OPEN"

            # ---------------------------------
            # Closed during selected period
            # ---------------------------------
            if closed_in_period and exit_price is not None:

                positions_closed += 1
                sold_symbols.add(symbol)

                pnl_per_share = round(
                    exit_price - entry_price,
                    6,
                )

                sell_value = round(
                    exit_price * quantity,
                    2,
                )

                profit_loss = round(
                    pnl_per_share * quantity,
                    2,
                )

                shares_sold += quantity
                total_sell_value += sell_value
                net_profit_loss += profit_loss
                total_profit_loss_per_share += pnl_per_share

                if pnl_per_share > 0:
                    result = "WIN"
                    winning_trades += 1

                    if profit_loss > 0:
                        gross_profit += profit_loss

                elif pnl_per_share < 0:
                    result = "LOSS"
                    losing_trades += 1

                    if profit_loss < 0:
                        gross_loss += abs(profit_loss)

                else:
                    result = "BREAKEVEN"
                    breakeven_trades += 1

            # Position is still open as of the end of selected period.
            elif record.closed_at is None or record.closed_at >= end_datetime:
                positions_still_open += 1

            trades.append(
                {
                    "symbol": symbol,
                    "timeframe": record.timeframe,
                    "signal_cycle_number": record.signal_cycle_number,

                    "entry_price": entry_price,
                    "quantity": quantity,
                    "buy_value": (
                        buy_value
                        if opened_in_period
                        else None
                    ),

                    "exit_price": (
                        exit_price
                        if closed_in_period
                        else None
                    ),
                    "sell_value": sell_value,

                    "profit_loss_per_share": pnl_per_share,
                    "profit_loss": profit_loss,

                    "result": result,

                    "opened_at": record.opened_at,
                    "closed_at": record.closed_at,
                    "exit_reason": (
                        record.exit_reason
                        if closed_in_period
                        else None
                    ),
                }
            )
            
        completed_trades = (
            winning_trades
            + losing_trades
            + breakeven_trades
        )

        win_rate = None

        if completed_trades > 0:
            win_rate = round(
                (winning_trades / completed_trades) * 100,
                2,
            )

        return {
            "period": {
                "start_date": start_date,
                "end_date": end_date,
            },

            "execution_mode":
                PerformanceStatisticsService.EXECUTION_MODE,

            "stocks_bought": len(bought_symbols),
            "stocks_sold": len(sold_symbols),

            "positions_opened": positions_opened,
            "positions_closed": positions_closed,
            "positions_still_open":
                positions_still_open,
            "shares_bought": shares_bought,
            "shares_sold": shares_sold,

            "total_buy_value": round(total_buy_value, 2),
            "total_sell_value": round(total_sell_value, 2),

            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "net_profit_loss": round(net_profit_loss, 2),

            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "breakeven_trades":
                breakeven_trades,

            "profit_loss_per_share": round(
                total_profit_loss_per_share,
                6,
            ),

            "win_rate_percent": win_rate,

            # This service is analytical/read-only.
            "broker_orders_submitted": 0,

            "trades": trades,
        }