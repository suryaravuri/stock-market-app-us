"""Options screen: read-only analysis of a stock's option chain.

Shows what the options pipeline WOULD pick and why, without saving anything
and without ever placing an order:

  * the stock's current signal and whether the options gate approves it
  * every contract examined, with the reason it qualified or was rejected
  * the selected contract with greeks, cost per contract (= max loss for a
    long option) and breakeven at expiry

US stocks only (Alpaca option data).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.market.sessions import is_indian_exchange
from app.repositories.stock_repository import StockRepository
from app.services.option_candidate_service import OptionCandidateService
from app.services.option_contract_selection_service import (
    OptionContractSelectionService,
    OptionSelectionConfig,
)
from app.services.option_strategy_risk_service import OptionStrategyRiskService
from app.services.setup_service import SetupService
from app.trading.derivatives_math import option_breakeven, option_cost_per_contract

DATA_FEED_NOTE = (
    "Without an Alpaca options data subscription quotes come from the "
    "'indicative' feed (estimated, may be delayed). Spreads and prices are "
    "approximate."
)


class OptionsExplorerService:

    @staticmethod
    def analyze(
        db: Session,
        symbol: str,
        *,
        option_type: str = "CALL",
        min_dte: int = 7,
        max_dte: int = 45,
        strike_range_percent: float = 10.0,
    ) -> dict:
        stock = StockRepository.find_by_symbol(db, symbol.strip().upper())
        if stock is None:
            raise ValueError(f"Stock not found: {symbol}")
        if is_indian_exchange(stock.exchange):
            raise ValueError("Options analysis currently supports US stocks only")
        if min_dte < 0 or max_dte < min_dte:
            raise ValueError("Invalid days-to-expiry range")

        setup = SetupService.get_setup(db=db, symbol=stock.symbol)
        price = float(setup.get("current_price") or 0)
        if price <= 0:
            raise ValueError(f"No current price for {stock.symbol}")

        state = str((setup.get("signal_lifecycle") or {}).get("state") or "UNKNOWN")
        score = float((setup.get("multi_timeframe") or {}).get("overall_score") or 0)
        actionable = bool(setup.get("actionable"))

        # The stock strategy is long-only, so the gate is asked about a
        # BULLISH signal; it approves only ENTRY_CONFIRMED + actionable.
        gate = OptionStrategyRiskService().evaluate(
            underlying_symbol=stock.symbol,
            signal_direction="BULLISH",
            signal_score=score,
            signal_state=state,
            actionable=actionable,
        )

        loaded = OptionCandidateService().load_candidates(
            underlying_symbol=stock.symbol,
            underlying_price=price,
            option_type=option_type,
            min_dte=min_dte,
            max_dte=max_dte,
            strike_range_percent=strike_range_percent,
        )

        selector = OptionContractSelectionService(
            OptionSelectionConfig(
                min_dte=min_dte,
                max_dte=max_dte,
                max_strike_distance_percent=strike_range_percent,
            )
        )
        today = date.today()
        result = selector.select(
            underlying_symbol=stock.symbol,
            underlying_price=price,
            option_type=option_type,
            snapshots=loaded["snapshots"],
            contracts=loaded["contracts"],
            as_of_date=today,
        )
        rows = selector.explain(
            snapshots=loaded["snapshots"],
            contracts=loaded["contracts"],
            underlying_price=price,
            option_type=option_type,
            as_of_date=today,
        )

        selected = None
        if result.selected is not None:
            chosen = result.selected
            greeks = getattr(chosen.snapshot, "greeks", None)
            selected = {
                "contract_symbol": chosen.contract_symbol,
                "option_type": chosen.option_type,
                "strike_price": chosen.strike_price,
                "expiration_date": chosen.expiration_date,
                "dte": chosen.dte,
                "bid_price": chosen.bid_price,
                "ask_price": chosen.ask_price,
                "midpoint": round(chosen.midpoint, 4),
                "spread_percent": round(chosen.spread_percent, 2),
                "open_interest": chosen.open_interest,
                "implied_volatility": getattr(chosen.snapshot, "implied_volatility", None),
                "greeks": {
                    name: getattr(greeks, name, None)
                    for name in ("delta", "gamma", "theta", "vega", "rho")
                } if greeks is not None else None,
                "cost_per_contract": option_cost_per_contract(chosen.midpoint),
                "max_loss_per_contract": option_cost_per_contract(chosen.midpoint),
                "breakeven_at_expiry": option_breakeven(
                    chosen.option_type, chosen.strike_price, chosen.midpoint
                ),
            }

        return {
            "symbol": stock.symbol,
            "underlying_price": price,
            "option_type": option_type.strip().upper(),
            "analysis_only": True,
            "orders_enabled": False,
            "signal": {
                "state": state,
                "score": score,
                "actionable": actionable,
                "recommendation": setup.get("action") or setup.get("recommendation"),
            },
            "gate": {
                "status": gate.status,
                "reason": gate.reason,
                "analysis_allowed": gate.analysis_allowed,
                "execution_allowed": gate.execution_allowed,
            },
            "filters": {
                "min_dte": min_dte,
                "max_dte": max_dte,
                "strike_range_percent": strike_range_percent,
                "max_spread_percent": selector.config.max_spread_percent,
                "min_open_interest": selector.config.min_open_interest,
            },
            "selection_status": result.status,
            "selection_reason": result.reason,
            "candidates_examined": result.candidates_examined,
            "candidates_qualified": result.candidates_qualified,
            "selected": selected,
            "candidates": rows[:200],
            "data_feed_note": DATA_FEED_NOTE,
        }
