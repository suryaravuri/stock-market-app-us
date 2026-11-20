from datetime import date, timedelta

from alpaca.trading.enums import ContractType

from sqlalchemy.orm import Session

from app.models.stock import Stock
from app.services.option_contract_service import (
    OptionContractService,
)

from app.brokers.alpaca.options_contracts import (
    AlpacaOptionContractsClient,
)
from app.brokers.alpaca.options_data import (
    AlpacaOptionsDataClient,
)
from app.services.option_contract_selection_service import (
    OptionContractSelectionService,
)

from app.services.option_selection_observation_service import (
    OptionSelectionObservationService,
)


class OptionCandidateService:

    def __init__(self) -> None:
        self.contract_client = (
            AlpacaOptionContractsClient()
        )

        self.market_data_client = (
            AlpacaOptionsDataClient()
        )

        self.selection_service = (
            OptionContractSelectionService()
        )

    def load_candidates(
            self,
            *,
            underlying_symbol: str,
            underlying_price: float,
            option_type: str,
            min_dte: int = 7,
            max_dte: int = 45,
            strike_range_percent: float = 10.0,
    ):
        if underlying_price <= 0:
            raise ValueError(
                "Underlying price must be greater than zero"
            )

        option_type = (
            option_type.strip().upper()
        )

        if option_type == "CALL":
            contract_type = ContractType.CALL
        elif option_type == "PUT":
            contract_type = ContractType.PUT
        else:
            raise ValueError(
                "option_type must be CALL or PUT"
            )

        today = date.today()

        expiration_gte = (
                today + timedelta(days=min_dte)
        )

        expiration_lte = (
                today + timedelta(days=max_dte)
        )

        range_fraction = (
                strike_range_percent / 100.0
        )

        strike_gte = (
                underlying_price
                * (1.0 - range_fraction)
        )

        strike_lte = (
                underlying_price
                * (1.0 + range_fraction)
        )

        #
        # 1. Get authoritative contract metadata.
        #
        contracts = (
            self.contract_client.get_contracts(
                underlying_symbol=underlying_symbol,
                contract_type=contract_type,
                expiration_date_gte=expiration_gte,
                expiration_date_lte=expiration_lte,
                strike_price_gte=strike_gte,
                strike_price_lte=strike_lte,
            )
        )

        #
        # 2. Retrieve snapshots using exactly
        #    the same server-side boundaries.
        #
        snapshots = (
            self.market_data_client.get_option_chain(
                underlying_symbol,
                contract_type=contract_type,
                strike_price_gte=strike_gte,
                strike_price_lte=strike_lte,
                expiration_date_gte=expiration_gte,
                expiration_date_lte=expiration_lte,
            )
        )

        #
        # 3. Index metadata by contract symbol.
        #
        contract_map = {
            contract.symbol: contract
            for contract in contracts
        }

        return {
            "underlying_symbol":
                underlying_symbol.strip().upper(),

            "underlying_price":
                underlying_price,

            "option_type":
                option_type,

            "expiration_date_gte":
                expiration_gte,

            "expiration_date_lte":
                expiration_lte,

            "strike_price_gte":
                strike_gte,

            "strike_price_lte":
                strike_lte,

            "contracts":
                contract_map,

            "snapshots":
                snapshots,
        }

    def select_best_contract(
            self,
            *,
            underlying_symbol: str,
            underlying_price: float,
            option_type: str,
    ):
        data = self.load_candidates(
            underlying_symbol=underlying_symbol,
            underlying_price=underlying_price,
            option_type=option_type,
        )

        result = self.selection_service.select(
            underlying_symbol=data["underlying_symbol"],
            underlying_price=data["underlying_price"],
            option_type=data["option_type"],
            snapshots=data["snapshots"],
            contracts=data["contracts"],
        )

        return result

    # def select_and_save_best_contract(
    #         self,
    #         *,
    #         db: Session,
    #         stock: Stock,
    #         underlying_price: float,
    #         option_type: str,
    # ):
    #     result = self.select_best_contract(
    #         underlying_symbol=stock.symbol,
    #         underlying_price=underlying_price,
    #         option_type=option_type,
    #     )
    #
    #     # Nothing qualified.
    #     # Do not write anything to option_contract.
    #     if (
    #             result.status != "SELECTED"
    #             or result.selected is None
    #     ):
    #         return result, None
    #
    #     selected = result.selected
    #
    #     # Persist ONLY the selected contract.
    #     saved_contract = (
    #         OptionContractService.save_alpaca_contract(
    #             db=db,
    #             stock=stock,
    #             alpaca_contract=selected.alpaca_contract,
    #         )
    #     )
    #
    #     return result, saved_contract

    def select_and_save_best_contract(
            self,
            *,
            db: Session,
            stock: Stock,
            underlying_price: float,
            option_type: str,
    ):
        result = self.select_best_contract(
            underlying_symbol=stock.symbol,
            underlying_price=underlying_price,
            option_type=option_type,
        )

        saved_contract = None

        # -----------------------------------------
        # Persist master contract only when selected
        # -----------------------------------------

        if (
                result.status == "SELECTED"
                and result.selected is not None
        ):
            saved_contract = (
                OptionContractService.save_alpaca_contract(
                    db=db,
                    stock=stock,
                    alpaca_contract=(
                        result.selected.alpaca_contract
                    ),
                )
            )

        # -----------------------------------------
        # ALWAYS save the observation.
        #
        # SELECTED and NO_QUALIFIED_CONTRACT
        # are both useful historical information.
        # -----------------------------------------

        observation = (
            OptionSelectionObservationService.save_selection(
                db=db,
                stock=stock,
                result=result,
                saved_contract=saved_contract,
            )
        )

        return result, saved_contract, observation
