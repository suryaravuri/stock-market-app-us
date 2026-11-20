from datetime import date

from alpaca.data.historical.option import (
    OptionHistoricalDataClient,
)
from alpaca.data.requests import OptionChainRequest
from alpaca.trading.enums import ContractType

from app.core.config import settings


class AlpacaOptionsDataClient:
    """
    Read-only Alpaca options market-data client.

    Phase 1:
    - Retrieve option chains
    - Filter by expiration
    - Filter by strike range
    - Filter CALL / PUT

    No option orders are submitted from this class.
    """

    def __init__(self) -> None:
        if not settings.alpaca_api_key:
            raise ValueError(
                "ALPACA_API_KEY is not configured"
            )

        if not settings.alpaca_secret_key:
            raise ValueError(
                "ALPACA_SECRET_KEY is not configured"
            )

        self.client = OptionHistoricalDataClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
        )

    def get_option_chain(
        self,
        underlying_symbol: str,
        *,
        contract_type: ContractType | None = None,
        strike_price_gte: float | None = None,
        strike_price_lte: float | None = None,
        expiration_date: date | None = None,
        expiration_date_gte: date | None = None,
        expiration_date_lte: date | None = None,
    ):
        symbol = underlying_symbol.strip().upper()

        if not symbol:
            raise ValueError(
                "Underlying symbol is required"
            )

        if (
            strike_price_gte is not None
            and strike_price_lte is not None
            and strike_price_gte > strike_price_lte
        ):
            raise ValueError(
                "strike_price_gte cannot be greater "
                "than strike_price_lte"
            )

        if (
            expiration_date_gte is not None
            and expiration_date_lte is not None
            and expiration_date_gte > expiration_date_lte
        ):
            raise ValueError(
                "expiration_date_gte cannot be later "
                "than expiration_date_lte"
            )

        request = OptionChainRequest(
            underlying_symbol=symbol,
            type=contract_type,
            strike_price_gte=strike_price_gte,
            strike_price_lte=strike_price_lte,
            expiration_date=expiration_date,
            expiration_date_gte=expiration_date_gte,
            expiration_date_lte=expiration_date_lte,
        )

        return self.client.get_option_chain(request)

    def get_calls(
        self,
        underlying_symbol: str,
        *,
        strike_price_gte: float | None = None,
        strike_price_lte: float | None = None,
        expiration_date: date | None = None,
        expiration_date_gte: date | None = None,
        expiration_date_lte: date | None = None,
    ):
        return self.get_option_chain(
            underlying_symbol=underlying_symbol,
            contract_type=ContractType.CALL,
            strike_price_gte=strike_price_gte,
            strike_price_lte=strike_price_lte,
            expiration_date=expiration_date,
            expiration_date_gte=expiration_date_gte,
            expiration_date_lte=expiration_date_lte,
        )

    def get_puts(
        self,
        underlying_symbol: str,
        *,
        strike_price_gte: float | None = None,
        strike_price_lte: float | None = None,
        expiration_date: date | None = None,
        expiration_date_gte: date | None = None,
        expiration_date_lte: date | None = None,
    ):
        return self.get_option_chain(
            underlying_symbol=underlying_symbol,
            contract_type=ContractType.PUT,
            strike_price_gte=strike_price_gte,
            strike_price_lte=strike_price_lte,
            expiration_date=expiration_date,
            expiration_date_gte=expiration_date_gte,
            expiration_date_lte=expiration_date_lte,
        )