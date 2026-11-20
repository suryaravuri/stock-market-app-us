"""Simulated long-only broker. Pure Python: no database, no Alpaca.

Fill rules (deliberately conservative):
- A signal seen at a bar's close is filled at the NEXT bar's open.
- Gap through the stop at the open -> exit at the open (worse than the stop).
- Gap above the target at the open -> exit at the open.
- Stop and target both touched inside one bar -> assume the stop hit first.
- Slippage is applied against us on every fill.
- The trailing stop is updated at each bar close, like the live 15-minute cycle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable


@dataclass
class Bar:
    time: datetime          # bar START time (UTC)
    open: float
    high: float
    low: float
    close: float


@dataclass
class PendingEntry:
    signal_time: datetime
    shares: int
    stop: float
    target: float
    reference_price: float


@dataclass
class Position:
    entry_time: datetime
    entry_price: float
    shares: int
    initial_stop: float
    stop: float
    target: float
    signal_time: datetime


@dataclass
class Trade:
    symbol: str
    signal_time: datetime
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    shares: int
    initial_stop: float
    final_stop: float
    target: float
    exit_reason: str
    commission: float

    @property
    def pnl(self) -> float:
        return (self.exit_price - self.entry_price) * self.shares - self.commission

    @property
    def pnl_percent(self) -> float:
        return (self.exit_price / self.entry_price - 1) * 100

    @property
    def r_multiple(self) -> float | None:
        risk = self.entry_price - self.initial_stop
        if risk <= 0:
            return None
        return (self.exit_price - self.entry_price) / risk


# (entry_price, current_price, current_stop) -> new stop or None
TrailFn = Callable[[float, float, float], float | None]


@dataclass
class SimulatedBroker:
    symbol: str
    starting_cash: float
    slippage_bps: float = 5.0
    commission_per_order: float = 0.0
    trail_fn: TrailFn | None = None

    cash: float = field(init=False)
    position: Position | None = field(default=None, init=False)
    pending: PendingEntry | None = field(default=None, init=False)
    trades: list[Trade] = field(default_factory=list, init=False)
    skipped_entries: dict[str, int] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.cash = self.starting_cash

    # ----------------------------------------------------------------- state
    @property
    def is_flat(self) -> bool:
        return self.position is None and self.pending is None

    def equity(self, mark_price: float) -> float:
        held = self.position.shares * mark_price if self.position else 0.0
        return self.cash + held

    def _buy_fill(self, price: float) -> float:
        return price * (1 + self.slippage_bps / 10_000)

    def _sell_fill(self, price: float) -> float:
        return price * (1 - self.slippage_bps / 10_000)

    def _skip(self, reason: str) -> None:
        self.skipped_entries[reason] = self.skipped_entries.get(reason, 0) + 1

    # ---------------------------------------------------------------- orders
    def queue_entry(
        self,
        signal_time: datetime,
        shares: int,
        stop: float,
        target: float,
        reference_price: float,
    ) -> None:
        if not self.is_flat:
            return
        if shares <= 0:
            self._skip("ZERO_SHARES")
            return
        self.pending = PendingEntry(signal_time, shares, stop, target, reference_price)

    def _close(self, bar_time: datetime, raw_price: float, reason: str) -> None:
        pos = self.position
        assert pos is not None
        price = self._sell_fill(raw_price)
        self.cash += price * pos.shares - self.commission_per_order
        self.trades.append(
            Trade(
                symbol=self.symbol,
                signal_time=pos.signal_time,
                entry_time=pos.entry_time,
                entry_price=pos.entry_price,
                exit_time=bar_time,
                exit_price=price,
                shares=pos.shares,
                initial_stop=pos.initial_stop,
                final_stop=pos.stop,
                target=pos.target,
                exit_reason=reason,
                commission=self.commission_per_order * 2,
            )
        )
        self.position = None

    # ------------------------------------------------------------ bar events
    def on_bar(self, bar: Bar) -> None:
        """Process one bar: fill a pending entry at the open, then exits."""
        if self.pending is not None:
            p = self.pending
            self.pending = None
            fill = self._buy_fill(bar.open)
            if fill <= p.stop:
                # Gapped down through the stop before we could even enter.
                self._skip("GAP_BELOW_STOP_AT_ENTRY")
            else:
                cost = fill * p.shares + self.commission_per_order
                shares = p.shares
                if cost > self.cash:
                    shares = int((self.cash - self.commission_per_order) // fill)
                if shares <= 0:
                    self._skip("INSUFFICIENT_CASH")
                else:
                    self.cash -= fill * shares + self.commission_per_order
                    self.position = Position(
                        entry_time=bar.time,
                        entry_price=fill,
                        shares=shares,
                        initial_stop=p.stop,
                        stop=p.stop,
                        target=p.target,
                        signal_time=p.signal_time,
                    )

        pos = self.position
        if pos is None:
            return

        # Exits, conservative ordering.
        if bar.open <= pos.stop:
            self._close(bar.time, bar.open, "STOP_GAP")
        elif bar.open >= pos.target:
            self._close(bar.time, bar.open, "TARGET_GAP")
        elif bar.low <= pos.stop:
            reason = "TRAILING_STOP" if pos.stop > pos.initial_stop else "STOP_LOSS"
            self._close(bar.time, pos.stop, reason)
        elif bar.high >= pos.target:
            self._close(bar.time, pos.target, "TARGET")
        elif self.trail_fn is not None:
            # Still open at the close: raise the stop like the live cycle does.
            new_stop = self.trail_fn(pos.entry_price, bar.close, pos.stop)
            if new_stop is not None and new_stop > pos.stop:
                pos.stop = new_stop

    def close_at_end(self, bar: Bar) -> None:
        self.pending = None
        if self.position is not None:
            self._close(bar.time, bar.close, "END_OF_TEST")
