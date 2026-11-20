from sqlalchemy.orm import Session

from app.models.option_contract import OptionContract
from app.models.stock import Stock
from app.repositories.option_contract_repository import (
    OptionContractRepository,
)


class OptionContractService:

    @staticmethod
    def save_alpaca_contract(
        db: Session,
        stock: Stock,
        alpaca_contract,
    ) -> OptionContract:

        symbol = str(
            alpaca_contract.symbol
        ).strip().upper()

        existing = (
            OptionContractRepository
            .find_by_contract_symbol(
                db=db,
                contract_symbol=symbol,
            )
        )

        if existing is not None:
            return existing

        contract_type = (
            alpaca_contract.type.value.upper()
            if hasattr(
                alpaca_contract.type,
                "value",
            )
            else str(
                alpaca_contract.type
            ).upper()
        )

        multiplier = int(
            alpaca_contract.size
        )

        if (
                stock.symbol.strip().upper()
                != alpaca_contract.underlying_symbol.strip().upper()
        ):
            raise ValueError(
                "Option contract underlying does not match stock"
            )

        contract = OptionContract(
            underlying_stock_id=stock.stock_id,
            contract_symbol=symbol,
            option_type=contract_type,
            strike_price=alpaca_contract.strike_price,
            expiration_date=alpaca_contract.expiration_date,
            multiplier=multiplier,
            active=(
                str(
                    getattr(
                        alpaca_contract.status,
                        "value",
                        alpaca_contract.status,
                    )
                ).lower()
                == "active"
            ),
        )

        return OptionContractRepository.save(
            db=db,
            contract=contract,
        )