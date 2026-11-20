from sqlalchemy.orm import Session

from app.models.option_contract import OptionContract


class OptionContractRepository:

    @staticmethod
    def find_by_contract_symbol(
        db: Session,
        contract_symbol: str,
    ) -> OptionContract | None:

        return (
            db.query(OptionContract)
            .filter(
                OptionContract.contract_symbol
                == contract_symbol.strip().upper()
            )
            .first()
        )

    @staticmethod
    def save(
        db: Session,
        contract: OptionContract,
    ) -> OptionContract:

        db.add(contract)
        db.commit()
        db.refresh(contract)

        return contract