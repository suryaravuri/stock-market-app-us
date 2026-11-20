from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.market_candle_repository import MarketCandleRepository
from app.repositories.position_state_repository import PositionStateRepository
from app.repositories.position_test_state_repository import PositionTestStateRepository
from app.repositories.stock_repository import StockRepository
from app.schemas.market import MarketTimeframe
from app.strategies.position_lifecycle import PositionState, TERMINAL_POSITION_STATES
from app.strategies.position_persistence import is_regular_session_candle
from app.market.sessions import session_for_exchange
from app.strategies.position_pnl_analytics import calculate_per_share_position_analytics


@dataclass(frozen=True)
class _AnalyticsContext:
    symbol: str
    stock_id: int
    timeframe: str
    state: str
    entry_price: float
    initial_risk_per_share: float
    opened_at: datetime
    last_evaluated_candle_time: datetime | None
    exit_price: float | None
    exit_reason: str | None
    closed_at: datetime | None
    persistence_mode: str
    analytics_scope: str
    candle_source: str
    test_run_id: str | None = None
    exchange: str | None = None  # selects the market session (None -> US)


class PositionPnLAnalyticsService:
    """#15E/#15E-5 source-aware P&L and exit-quality analytics.

    Analytics remain read-only and per-share. The source selector prevents synthetic
    persistent-test runs from accidentally using real market_candle prices.
    """

    ANALYTICS_MODE = "POSITION_PNL_EXIT_ANALYTICS"
    EXECUTION_MODE = "ANALYSIS_ONLY"
    PNL_BASIS = "PER_SHARE"
    SOURCE_MARKET = "MARKET_CANDLE"
    SOURCE_SYNTHETIC = "SYNTHETIC_PERSISTED_CANDLES"
    SOURCE_SYNTHETIC_UNRECORDED = "SYNTHETIC_UNRECORDED"

    @staticmethod
    def for_persistent_position(db: Session, symbol: str, timeframe: MarketTimeframe) -> dict:
        symbol = symbol.strip().upper()
        stock = StockRepository.find_by_symbol(db, symbol)
        if stock is None:
            raise ValueError(f"Stock not found: {symbol}")
        record = PositionStateRepository.find_latest(db, stock.stock_id, timeframe.value)
        if record is None:
            return PositionPnLAnalyticsService._no_position(
                symbol=symbol,
                timeframe=timeframe.value,
                persistence_mode="PERSISTENT_ANALYTICAL",
                analytics_scope="PRODUCTION_ANALYTICAL_POSITION",
            )
        ctx = _AnalyticsContext(
            symbol=symbol,
            stock_id=stock.stock_id,
            timeframe=record.timeframe,
            state=record.state,
            entry_price=float(record.entry_price),
            initial_risk_per_share=float(record.initial_risk_per_share),
            opened_at=record.opened_at,
            last_evaluated_candle_time=record.last_evaluated_candle_time,
            exit_price=float(record.exit_price) if record.exit_price is not None else None,
            exit_reason=record.exit_reason,
            closed_at=record.closed_at,
            persistence_mode="PERSISTENT_ANALYTICAL",
            analytics_scope="PRODUCTION_ANALYTICAL_POSITION",
            candle_source=PositionPnLAnalyticsService.SOURCE_MARKET,
            exchange=getattr(stock, "exchange", None),
        )
        return PositionPnLAnalyticsService._calculate(db, ctx)

    @staticmethod
    def for_test_run(db: Session, symbol: str, test_run_id: str) -> dict:
        symbol = symbol.strip().upper()
        record = PositionTestStateRepository.find(db, test_run_id)
        if record is None or record.symbol.strip().upper() != symbol:
            raise ValueError(f"Persistent test run not found: {test_run_id}")
        ctx = _AnalyticsContext(
            symbol=symbol,
            stock_id=record.stock_id,
            timeframe=record.timeframe,
            state=record.state,
            entry_price=float(record.entry_price),
            initial_risk_per_share=float(record.initial_risk_per_share),
            opened_at=record.opened_at,
            last_evaluated_candle_time=record.last_evaluated_candle_time,
            exit_price=float(record.exit_price) if record.exit_price is not None else None,
            exit_reason=record.exit_reason,
            closed_at=record.closed_at,
            persistence_mode="ISOLATED_TEST_TABLES",
            analytics_scope="ISOLATED_PERSISTENT_TEST_POSITION",
            candle_source=getattr(record, "analytics_candle_source", None)
            or PositionPnLAnalyticsService.SOURCE_SYNTHETIC_UNRECORDED,
            test_run_id=test_run_id,
        )
        return PositionPnLAnalyticsService._calculate(db, ctx)

    @staticmethod
    def _calculate(db: Session, ctx: _AnalyticsContext) -> dict:
        terminal = PositionState(ctx.state) in TERMINAL_POSITION_STATES
        end_at = ctx.closed_at or ctx.last_evaluated_candle_time or ctx.opened_at
        ignored_out_of_session = 0
        source_status = "AVAILABLE"
        source_note = None
        eligible = []
        current_price = None

        if ctx.candle_source == PositionPnLAnalyticsService.SOURCE_MARKET:
            rows = MarketCandleRepository.find_by_range(
                db, ctx.stock_id, ctx.timeframe, ctx.opened_at, end_at
            )
            market_session = session_for_exchange(ctx.exchange)
            for candle in rows:
                if candle.candle_time <= ctx.opened_at:
                    continue
                if not is_regular_session_candle(candle.candle_time, market_session):
                    ignored_out_of_session += 1
                    continue
                eligible.append(candle)
            latest = MarketCandleRepository.find_latest(db, ctx.stock_id, ctx.timeframe)
            current_price = float(latest.close_price) if latest is not None else None

        elif ctx.candle_source == PositionPnLAnalyticsService.SOURCE_SYNTHETIC:
            rows = PositionTestStateRepository.observations(db, ctx.test_run_id)
            eligible = [r for r in rows if ctx.opened_at < r.candle_time <= end_at]
            if eligible:
                current_price = float(eligible[-1].close_price)
            elif terminal and ctx.exit_price is not None:
                current_price = ctx.exit_price

        else:
            source_status = "UNAVAILABLE"
            source_note = (
                "This synthetic test run was created before #15E-5 persisted OHLC observations. "
                "Excursion and exit-efficiency metrics are intentionally suppressed to prevent "
                "mixing synthetic test prices with real market_candle data. Re-run the controlled "
                "synthetic test to obtain source-complete analytics."
            )
            if terminal and ctx.exit_price is not None:
                current_price = ctx.exit_price

        entry = ctx.entry_price
        risk = ctx.initial_risk_per_share
        holding_minutes = round((end_at - ctx.opened_at).total_seconds() / 60.0, 2)
        status = "CLOSED" if terminal else "OPEN"

        if source_status == "UNAVAILABLE":
            realized = realized_r = unrealized = unrealized_r = None
            if terminal and ctx.exit_price is not None:
                realized = round(ctx.exit_price - entry, 6)
                realized_r = round(realized / risk, 4) if risk > 0 else None
            elif current_price is not None:
                unrealized = round(current_price - entry, 6)
                unrealized_r = round(unrealized / risk, 4) if risk > 0 else None
            metrics = {
                "mfe_per_share": None,
                "mfe_r": None,
                "mae_per_share": None,
                "mae_r": None,
                "best_price": None,
                "worst_price": None,
                "giveback_from_mfe_per_share": None,
                "exit_efficiency_pct": None,
            }
            if terminal:
                summary = (
                    f"Closed {ctx.state}: realized {realized:+.4f}/share"
                    + (f" ({realized_r:+.2f}R)" if realized_r is not None else "")
                    + "; source OHLC unavailable, so MFE/MAE and exit efficiency are suppressed."
                )
            else:
                summary = f"Open {ctx.state}: source OHLC unavailable for reliable excursion analytics."
        else:
            metrics_all = calculate_per_share_position_analytics(
                entry_price=entry,
                initial_risk_per_share=risk,
                current_price=current_price,
                exit_price=ctx.exit_price,
                terminal=terminal,
                highs=[float(c.high_price) for c in eligible],
                lows=[float(c.low_price) for c in eligible],
            )
            metrics = metrics_all
            realized = metrics_all["realized_per_share"]
            realized_r = metrics_all["realized_r"]
            unrealized = metrics_all["unrealized_per_share"]
            unrealized_r = metrics_all["unrealized_r"]
            mfe = metrics_all["mfe_per_share"]
            mae = metrics_all["mae_per_share"]
            if terminal:
                summary = (
                    f"Closed {ctx.state}: realized {realized:+.4f}/share"
                    + (f" ({realized_r:+.2f}R)" if realized_r is not None else "")
                    + f"; MFE {mfe:+.4f}, MAE {mae:+.4f}."
                )
            else:
                summary = (
                    f"Open {ctx.state}: unrealized {unrealized:+.4f}/share"
                    + (f" ({unrealized_r:+.2f}R)" if unrealized_r is not None else "")
                    + f"; MFE {mfe:+.4f}, MAE {mae:+.4f}."
                ) if unrealized is not None else f"Open {ctx.state}: current price unavailable."

        return {
            "symbol": ctx.symbol,
            "timeframe": ctx.timeframe,
            "analytics_mode": PositionPnLAnalyticsService.ANALYTICS_MODE,
            "analytics_scope": ctx.analytics_scope,
            "analytics_candle_source": ctx.candle_source,
            "source_data_status": source_status,
            "source_data_note": source_note,
            "execution_mode": PositionPnLAnalyticsService.EXECUTION_MODE,
            "persistence_mode": ctx.persistence_mode,
            "broker_order_submitted": False,
            "production_position_tables_mutated": False,
            "test_run_id": ctx.test_run_id,
            "analytics_status": status,
            "state": ctx.state,
            "terminal": terminal,
            "pnl_basis": PositionPnLAnalyticsService.PNL_BASIS,
            "entry_price": entry,
            "current_price": current_price,
            "exit_price": ctx.exit_price,
            "initial_risk_per_share": risk,
            "unrealized_per_share": unrealized,
            "unrealized_r": unrealized_r,
            "realized_per_share": realized,
            "realized_r": realized_r,
            "mfe_per_share": metrics["mfe_per_share"],
            "mfe_r": metrics["mfe_r"],
            "mae_per_share": metrics["mae_per_share"],
            "mae_r": metrics["mae_r"],
            "best_price": metrics["best_price"],
            "worst_price": metrics["worst_price"],
            "giveback_from_mfe_per_share": metrics["giveback_from_mfe_per_share"],
            "exit_efficiency_pct": metrics["exit_efficiency_pct"],
            "holding_minutes": holding_minutes,
            "opened_at": ctx.opened_at,
            "analysis_end_at": end_at,
            "closed_at": ctx.closed_at,
            "exit_reason": ctx.exit_reason,
            "candles_analyzed": len(eligible),
            "ignored_out_of_session_candles": ignored_out_of_session,
            "summary": summary,
        }

    @staticmethod
    def _no_position(*, symbol: str, timeframe: str, persistence_mode: str, analytics_scope: str) -> dict:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "analytics_mode": PositionPnLAnalyticsService.ANALYTICS_MODE,
            "analytics_scope": analytics_scope,
            "analytics_candle_source": PositionPnLAnalyticsService.SOURCE_MARKET,
            "source_data_status": "NOT_APPLICABLE",
            "source_data_note": None,
            "execution_mode": PositionPnLAnalyticsService.EXECUTION_MODE,
            "persistence_mode": persistence_mode,
            "broker_order_submitted": False,
            "production_position_tables_mutated": False,
            "test_run_id": None,
            "analytics_status": "NO_POSITION",
            "state": "NOT_OPEN",
            "terminal": False,
            "pnl_basis": PositionPnLAnalyticsService.PNL_BASIS,
            "entry_price": None,
            "current_price": None,
            "exit_price": None,
            "initial_risk_per_share": None,
            "unrealized_per_share": None,
            "unrealized_r": None,
            "realized_per_share": None,
            "realized_r": None,
            "mfe_per_share": None,
            "mfe_r": None,
            "mae_per_share": None,
            "mae_r": None,
            "best_price": None,
            "worst_price": None,
            "giveback_from_mfe_per_share": None,
            "exit_efficiency_pct": None,
            "holding_minutes": None,
            "opened_at": None,
            "analysis_end_at": None,
            "closed_at": None,
            "exit_reason": None,
            "candles_analyzed": 0,
            "ignored_out_of_session_candles": 0,
            "summary": "No persistent analytical position exists; P&L analytics are unavailable.",
        }
