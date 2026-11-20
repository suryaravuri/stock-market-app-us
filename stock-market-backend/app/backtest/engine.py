"""Walk-forward replay of the LIVE strategy over historical 15-minute bars.

For every completed 15-minute bar, the engine does exactly what the live
trading cycle does a minute after that bar closes:

  1. freeze the clock at bar end + 1 minute
  2. limit every candle query to bars completed by then (CompletedCandleGuard)
  3. run PositionMonitoringService + SetupService.get_setup() on the backtest DB
  4. enter when the setup is actionable AND the signal is ENTRY_CONFIRMED
     (same rule as AutoPaperExecutionService), filled at the NEXT bar's open
  5. exits: bracket stop/target (PaperTradingService._exit_prices) plus the
     trailing stop (compute_trailing_stop), checked bar by bar

So the backtest tests the same code that trades, not a rewritten copy.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Callable

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.backtest.broker import Bar, SimulatedBroker
from app.backtest.clock import frozen_at
from app.backtest.metrics import equity_curve_points, summarize
from app.core.config import settings
from app.market.sessions import session_for_stock
from app.models.market_candle import MarketCandle
from app.models.position_state import PositionStateHistory, PositionStateRecord
from app.models.position_test_state import (
    PositionTestCandleObservation,
    PositionTestStateHistory,
    PositionTestStateRecord,
)
from app.models.signal_state import SignalStateHistory, SignalStateRecord
from app.models.stock import Stock
from app.risk.position_sizer import calculate_position_size
from app.risk.risk_model import use_risk_model
from app.services.support_bounce_service import SupportBounceService, entry_mode_allows
from app.strategies.support_bounce import BounceRules
from app.risk.trailing_stop import compute_trailing_stop
from app.schemas.market import MarketTimeframe
from app.services.completed_candle_guard import CompletedCandleGuard
from app.services.paper_trading_service import PaperTradingService
from app.services.position_monitoring_service import PositionMonitoringService
from app.services.setup_service import SetupService
from app.services.validation_market_data_service import ValidationMarketDataService

logger = logging.getLogger(__name__)

BAR_MINUTES = 15
DECISION_DELAY = timedelta(minutes=1)  # the live scheduler runs at :01/:16/:31/:46


@dataclass
class BacktestParams:
    starting_cash: float = 10_000.0
    risk_percent: float = settings.risk_percent
    max_position_percent: float = settings.max_position_percent
    slippage_bps: float = 5.0
    commission_per_order: float = 0.0
    trailing_enabled: bool = settings.trailing_stop_enabled
    trail_percent: float = settings.trailing_stop_percent
    trailing_activation_percent: float = settings.trailing_activation_percent
    trailing_breakeven_percent: float = settings.trailing_breakeven_percent
    trailing_min_step_percent: float = settings.trailing_min_step_percent
    # True = evaluate the strategy on every bar, like live (signal lifecycle
    # keeps advancing while in a trade). False = only when flat (faster).
    evaluate_every_bar: bool = True
    # Risk/reward model for this run: LEGACY or ATR_FLOOR (compare both).
    risk_model: str = settings.risk_model
    # Entry rules: BREAKOUT, SUPPORT_BOUNCE or BOTH.
    entry_mode: str = "BREAKOUT"
    # Which levels the support bounce uses: INTRADAY (15m), WEEKLY (1h),
    # MONTHLY / SWING (daily).
    bounce_holding_style: str = "WEEKLY"
    bounce_min_rr: float = settings.bounce_min_rr
    # Experimental bounce rules (see strategies/support_bounce.py).
    bounce_level_zone_atr: float = 0.0
    bounce_confirm_bars: int = 1

    @classmethod
    def from_dict(cls, data: dict | None) -> "BacktestParams":
        data = data or {}
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def to_dict(self) -> dict:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass
class SymbolResult:
    symbol: str
    trades: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    equity: pd.Series | None = None
    evaluation_errors: dict[str, int] = field(default_factory=dict)
    skipped_entries: dict[str, int] = field(default_factory=dict)


def reset_strategy_state(bt_db: Session, stock_id: int) -> None:
    """Fresh signal/position lifecycle for this stock before each run."""
    for model in (
        SignalStateHistory,
        SignalStateRecord,
        PositionStateHistory,
        PositionStateRecord,
        PositionTestCandleObservation,
        PositionTestStateHistory,
        PositionTestStateRecord,
    ):
        bt_db.execute(delete(model).where(model.stock_id == stock_id))
    bt_db.commit()


def _load_bars(bt_db: Session, stock: Stock, start: date, end: date) -> list[Bar]:
    session = session_for_stock(stock)
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=session.tz)
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=session.tz)
    rows = bt_db.execute(
        select(
            MarketCandle.candle_time,
            MarketCandle.open_price,
            MarketCandle.high_price,
            MarketCandle.low_price,
            MarketCandle.close_price,
        )
        .where(
            MarketCandle.stock_id == stock.stock_id,
            MarketCandle.timeframe == MarketTimeframe.FIFTEEN_MINUTES.value,
            MarketCandle.candle_time >= start_dt,
            MarketCandle.candle_time < end_dt,
        )
        .order_by(MarketCandle.candle_time)
    ).all()
    return [
        Bar(time=r[0], open=float(r[1]), high=float(r[2]), low=float(r[3]), close=float(r[4]))
        for r in rows
        if session.is_regular(r[0])
    ]


def _trail_fn(params: BacktestParams):
    if not params.trailing_enabled:
        return None

    def trail(entry: float, price: float, current_stop: float):
        decision = compute_trailing_stop(
            entry_price=entry,
            current_price=price,
            current_stop=current_stop,
            trail_percent=params.trail_percent,
            activation_percent=params.trailing_activation_percent,
            breakeven_percent=params.trailing_breakeven_percent,
            min_step_percent=params.trailing_min_step_percent,
        )
        return decision.new_stop if decision.should_update else None

    return trail


def run_symbol(
    bt_db: Session,
    stock: Stock,
    start: date,
    end: date,
    params: BacktestParams,
    progress: Callable[[float, str], None] | None = None,
) -> SymbolResult:
    symbol = stock.symbol
    session = session_for_stock(stock)
    result = SymbolResult(symbol=symbol)

    reset_strategy_state(bt_db, stock.stock_id)
    bars = _load_bars(bt_db, stock, start, end)
    if len(bars) < 2:
        raise ValueError(f"{symbol}: no 15-minute bars between {start} and {end}")

    broker = SimulatedBroker(
        symbol=symbol,
        starting_cash=params.starting_cash,
        slippage_bps=params.slippage_bps,
        commission_per_order=params.commission_per_order,
        trail_fn=_trail_fn(params),
    )

    daily_equity: dict[date, float] = {}
    bars_in_market = 0
    report_every = max(len(bars) // 200, 1)

    for index, bar in enumerate(bars):
        broker.on_bar(bar)
        if broker.position is not None:
            bars_in_market += 1

        local_day = session.local(bar.time).date()
        daily_equity[local_day] = broker.equity(bar.close)

        if not params.evaluate_every_bar and not broker.is_flat:
            continue

        decision_time = bar.time + timedelta(minutes=BAR_MINUTES) + DECISION_DELAY
        try:
            with frozen_at(decision_time):
                cutoffs = {
                    tf.value: ValidationMarketDataService.expected_latest_completed_candle(
                        tf.value, decision_time, session
                    )
                    for tf in (
                        MarketTimeframe.FIFTEEN_MINUTES,
                        MarketTimeframe.ONE_HOUR,
                        MarketTimeframe.ONE_DAY,
                    )
                }
                with CompletedCandleGuard.enforce(bt_db, cutoffs):
                    PositionMonitoringService.monitor_existing(
                        bt_db,
                        symbol,
                        MarketTimeframe.FIFTEEN_MINUTES,
                        trigger="MARKET_SYNC",
                        now_utc=decision_time,
                    )
                    with use_risk_model(params.risk_model):
                        setup = SetupService.get_setup(db=bt_db, symbol=symbol)
                    bounce = None
                    if broker.is_flat and entry_mode_allows(params.entry_mode, "SUPPORT_BOUNCE"):
                        bounce = SupportBounceService.evaluate(
                            bt_db,
                            stock,
                            holding_style=params.bounce_holding_style,
                            trend_score=(setup.get("multi_timeframe") or {}).get("overall_score"),
                            cutoffs=cutoffs,
                            rules=BounceRules(
                                zone_atr=settings.bounce_zone_atr,
                                min_rr=params.bounce_min_rr,
                                min_stop_atr=settings.risk_min_stop_atr,
                                min_trend_score=settings.bounce_min_trend_score,
                                level_zone_atr=params.bounce_level_zone_atr,
                                confirm_bars=params.bounce_confirm_bars,
                            ),
                        )
        except Exception as exc:  # noqa: BLE001 - one bad bar must not stop the run
            bt_db.rollback()
            key = type(exc).__name__
            result.evaluation_errors[key] = result.evaluation_errors.get(key, 0) + 1
            continue

        if broker.is_flat and index + 1 < len(bars):
            lifecycle = setup.get("signal_lifecycle") or {}
            confirmed = str(lifecycle.get("state") or "").upper() == "ENTRY_CONFIRMED"
            breakout_ok = (
                entry_mode_allows(params.entry_mode, "BREAKOUT")
                and confirmed
                and setup.get("actionable")
            )
            entry_setup = None
            if breakout_ok:
                entry_setup = setup
            elif bounce and bounce.get("triggered"):
                entry_setup = SupportBounceService.as_setup(bounce, setup)
            if entry_setup is not None:
                risk = entry_setup.get("risk_reward") or {}
                entry_ref = float(risk.get("entry") or setup.get("current_price") or bar.close)
                stop, target = PaperTradingService._exit_prices(
                    {
                        "entry_price": entry_ref,
                        "stop_loss": risk.get("stop_loss"),
                        "target_1": risk.get("target_1"),
                    }
                )
                try:
                    size = calculate_position_size(
                        account_size=broker.equity(bar.close),
                        risk_percent=params.risk_percent,
                        entry_price=entry_ref,
                        stop_loss=stop,
                        actionable=True,
                        max_position_percent=params.max_position_percent,
                    )
                    shares = size.shares if size.allowed else 0
                except ValueError:
                    shares = 0
                broker.queue_entry(bar.time, shares, stop, target, entry_ref)

        if progress and index % report_every == 0:
            progress(index / len(bars), f"{symbol}: {session.local(bar.time):%Y-%m-%d}, {len(broker.trades)} trades")

    broker.close_at_end(bars[-1])
    daily_equity[session.local(bars[-1].time).date()] = broker.cash

    equity = pd.Series(daily_equity).sort_index()
    equity.index = pd.to_datetime(equity.index)

    buy_and_hold = (bars[-1].close / bars[0].open - 1) * 100

    result.trades = broker.trades
    result.equity = equity
    result.skipped_entries = broker.skipped_entries
    result.summary = summarize(
        broker.trades,
        equity,
        params.starting_cash,
        buy_and_hold,
        bars_in_market,
        len(bars),
    )
    result.summary["evaluation_errors"] = result.evaluation_errors
    result.summary["skipped_entries"] = result.skipped_entries
    result.summary["bars_replayed"] = len(bars)
    return result


def combine(results: list[SymbolResult], params: BacktestParams) -> dict:
    """Each symbol trades its own equal sleeve of capital; add them up."""
    curves = [r.equity for r in results if r.equity is not None and len(r.equity)]
    if not curves:
        return {}
    frame = pd.concat(curves, axis=1).sort_index().ffill()
    frame = frame.fillna(params.starting_cash)
    total = frame.sum(axis=1)
    trades = [t for r in results for t in r.trades]
    bh = [r.summary.get("buy_and_hold_return_percent") for r in results]
    bh = [v for v in bh if v is not None]
    overall = summarize(
        trades,
        total,
        params.starting_cash * len(curves),
        sum(bh) / len(bh) if bh else None,
        bars_in_market=0,
        bars_total=0,
    )
    overall.pop("exposure_percent", None)
    return {"summary": overall, "equity_curve": equity_curve_points(total)}
