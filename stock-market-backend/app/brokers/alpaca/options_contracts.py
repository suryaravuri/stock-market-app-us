from datetime import date

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetStatus, ContractType
from alpaca.trading.requests import GetOptionContractsRequest

from app.core.config import settings


class AlpacaOptionContractsClient:
    """
    Read-only access to Alpaca option-contract metadata.

    No order submission belongs in this class.
    """

    def __init__(self) -> None:
        self.client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=True,
        )

    def get_contracts(
        self,
        *,
        underlying_symbol: str,
        contract_type: ContractType,
        expiration_date_gte: date,
        expiration_date_lte: date,
        strike_price_gte: float,
        strike_price_lte: float,
        limit: int = 1000,
    ) -> list:

        symbol = underlying_symbol.strip().upper()

        if not symbol:
            raise ValueError(
                "Underlying symbol is required"
            )

        if expiration_date_gte > expiration_date_lte:
            raise ValueError(
                "Invalid expiration range"
            )

        if strike_price_gte > strike_price_lte:
            raise ValueError(
                "Invalid strike range"
            )

        request = GetOptionContractsRequest(
            underlying_symbols=[symbol],
            status=AssetStatus.ACTIVE,
            type=contract_type,
            expiration_date_gte=expiration_date_gte,
            expiration_date_lte=expiration_date_lte,

            # 0.24.0 expects strings here.
            strike_price_gte=str(strike_price_gte),
            strike_price_lte=str(strike_price_lte),

            limit=limit,
        )

        response = self.client.get_option_contracts(
            request
        )

        return list(response.option_contracts)