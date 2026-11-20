from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.option_contract import OptionContract
from app.models.option_selection_observation import (
    OptionSelectionObservation,
)
from app.models.stock import Stock
from app.repositories.option_selection_observation_repository import (
    OptionSelectionObservationRepository,
)


class OptionSelectionObservationService:

    @staticmethod
    def save_selection(
        *,
        db: Session,
        stock: Stock,
        result,
        saved_contract: OptionContract | None,
    ) -> OptionSelectionObservation:

        selected = result.selected

        # Defaults for NO_QUALIFIED_CONTRACT.
        bid_price = None
        ask_price = None
        midpoint = None
        spread_percent = None
        strike_distance_percent = None
        dte = None
        open_interest = None

        implied_volatility = None
        delta = None
        gamma = None
        theta = None
        vega = None
        rho = None

        if selected is not None:
            bid_price = selected.bid_price
            ask_price = selected.ask_price
            midpoint = selected.midpoint
            spread_percent = selected.spread_percent
            strike_distance_percent = (
                selected.strike_distance_percent
            )
            dte = selected.dte
            open_interest = selected.open_interest

            snapshot = selected.snapshot

            implied_volatility = getattr(
                snapshot,
                "implied_volatility",
                None,
            )

            greeks = getattr(
                snapshot,
                "greeks",
                None,
            )

            if greeks is not None:
                delta = getattr(greeks, "delta", None)
                gamma = getattr(greeks, "gamma", None)
                theta = getattr(greeks, "theta", None)
                vega = getattr(greeks, "vega", None)
                rho = getattr(greeks, "rho", None)

        observation = OptionSelectionObservation(
            underlying_stock_id=stock.stock_id,

            option_contract_id=(
                saved_contract.option_contract_id
                if saved_contract is not None
                else None
            ),

            option_type=result.option_type,
            selection_status=result.status,
            selection_reason=result.reason,

            underlying_price=result.underlying_price,

            candidates_examined=(
                result.candidates_examined
            ),
            candidates_qualified=(
                result.candidates_qualified
            ),

            bid_price=bid_price,
            ask_price=ask_price,
            midpoint=midpoint,

            spread_percent=spread_percent,
            strike_distance_percent=(
                strike_distance_percent
            ),

            dte=dte,
            open_interest=open_interest,

            implied_volatility=implied_volatility,

            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
        )

        return (
            OptionSelectionObservationRepository.save(
                db=db,
                observation=observation,
            )
        )