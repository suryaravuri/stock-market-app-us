from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class OptionSelectionConfig:
    min_dte: int = 7
    max_dte: int = 45

    max_strike_distance_percent: float = 10.0
    max_spread_percent: float = 20.0

    min_open_interest: int = 100


@dataclass
class OptionCandidate:
    contract_symbol: str
    option_type: str

    strike_price: float
    expiration_date: date
    dte: int

    bid_price: float
    ask_price: float
    midpoint: float

    spread_percent: float
    strike_distance_percent: float

    open_interest: int

    alpaca_contract: Any
    snapshot: Any


@dataclass
class OptionSelectionResult:
    status: str
    reason: str

    underlying_symbol: str
    underlying_price: float
    option_type: str

    candidates_examined: int
    candidates_qualified: int

    selected: OptionCandidate | None


class OptionContractSelectionService:

    def __init__(
        self,
        config: OptionSelectionConfig | None = None,
    ) -> None:
        self.config = (
            config or OptionSelectionConfig()
        )

    def select(
        self,
        *,
        underlying_symbol: str,
        underlying_price: float,
        option_type: str,
        snapshots: dict,
        contracts: dict,
        as_of_date: date | None = None,
    ) -> OptionSelectionResult:

        if underlying_price <= 0:
            raise ValueError(
                "Underlying price must be greater than zero"
            )

        today = as_of_date or date.today()

        requested_type = (
            option_type.strip().upper()
        )

        if requested_type not in {"CALL", "PUT"}:
            raise ValueError(
                "option_type must be CALL or PUT"
            )

        qualified: list[OptionCandidate] = []

        examined = 0

        for symbol, snapshot in snapshots.items():

            contract = contracts.get(symbol)

            if contract is None:
                continue

            examined += 1

            candidate = self._evaluate(
                contract=contract,
                snapshot=snapshot,
                underlying_price=underlying_price,
                requested_type=requested_type,
                today=today,
            )

            if candidate is not None:
                qualified.append(candidate)

        if not qualified:
            return OptionSelectionResult(
                status="NO_QUALIFIED_CONTRACT",
                reason=(
                    "No option contract passed "
                    "expiration, strike, quote, spread "
                    "and liquidity requirements"
                ),
                underlying_symbol=(
                    underlying_symbol.strip().upper()
                ),
                underlying_price=underlying_price,
                option_type=requested_type,
                candidates_examined=examined,
                candidates_qualified=0,
                selected=None,
            )

        #
        # V1 ranking:
        #
        # 1. Prefer strike closest to underlying.
        # 2. Prefer tighter spread.
        # 3. Prefer greater open interest.
        # 4. Prefer lower DTE when otherwise equal.
        #
        qualified.sort(
            key=lambda candidate: (
                candidate.strike_distance_percent,
                candidate.spread_percent,
                -candidate.open_interest,
                candidate.dte,
            )
        )

        selected = qualified[0]

        return OptionSelectionResult(
            status="SELECTED",
            reason="Qualified option contract selected",
            underlying_symbol=(
                underlying_symbol.strip().upper()
            ),
            underlying_price=underlying_price,
            option_type=requested_type,
            candidates_examined=examined,
            candidates_qualified=len(qualified),
            selected=selected,
        )

    def explain(
        self,
        *,
        snapshots: dict,
        contracts: dict,
        underlying_price: float,
        option_type: str,
        as_of_date: date | None = None,
    ) -> list[dict]:
        """Every contract with the reason it qualified or was rejected.

        Read-only companion to select(), used by the options screen.
        """
        if underlying_price <= 0:
            raise ValueError("Underlying price must be greater than zero")
        requested_type = option_type.strip().upper()
        if requested_type not in {"CALL", "PUT"}:
            raise ValueError("option_type must be CALL or PUT")
        today = as_of_date or date.today()

        rows: list[dict] = []
        for symbol, snapshot in snapshots.items():
            contract = contracts.get(symbol)
            if contract is None:
                continue
            candidate, reason = self._assess(
                contract=contract,
                snapshot=snapshot,
                underlying_price=underlying_price,
                requested_type=requested_type,
                today=today,
            )
            quote = getattr(snapshot, "latest_quote", None)
            greeks = getattr(snapshot, "greeks", None)
            rows.append({
                "contract_symbol": str(contract.symbol),
                "strike_price": float(contract.strike_price),
                "expiration_date": contract.expiration_date,
                "dte": (contract.expiration_date - today).days,
                "bid_price": getattr(quote, "bid_price", None),
                "ask_price": getattr(quote, "ask_price", None),
                "spread_percent": candidate.spread_percent if candidate else None,
                "open_interest": self._parse_int(getattr(contract, "open_interest", None)),
                "delta": getattr(greeks, "delta", None),
                "implied_volatility": getattr(snapshot, "implied_volatility", None),
                "qualified": candidate is not None,
                "reason": reason,
            })
        rows.sort(key=lambda row: (not row["qualified"], row["expiration_date"], row["strike_price"]))
        return rows

    def _evaluate(
        self,
        *,
        contract,
        snapshot,
        underlying_price: float,
        requested_type: str,
        today: date,
    ) -> OptionCandidate | None:
        candidate, _ = self._assess(
            contract=contract,
            snapshot=snapshot,
            underlying_price=underlying_price,
            requested_type=requested_type,
            today=today,
        )
        return candidate

    def _assess(
        self,
        *,
        contract,
        snapshot,
        underlying_price: float,
        requested_type: str,
        today: date,
    ) -> tuple[OptionCandidate | None, str]:
        """(candidate, "QUALIFIED") or (None, reason it was rejected)."""
        contract_type = str(getattr(contract.type, "value", contract.type)).upper()
        if contract_type != requested_type:
            return None, f"WRONG_TYPE:{contract_type}"

        expiration = contract.expiration_date
        dte = (expiration - today).days
        if dte < self.config.min_dte or dte > self.config.max_dte:
            return None, f"DTE_OUT_OF_RANGE:{dte}"

        strike = float(contract.strike_price)
        strike_distance_percent = abs(strike - underlying_price) / underlying_price * 100.0
        if strike_distance_percent > self.config.max_strike_distance_percent:
            return None, f"STRIKE_TOO_FAR:{strike_distance_percent:.1f}%"

        quote = getattr(snapshot, "latest_quote", None)
        if quote is None:
            return None, "NO_QUOTE"

        bid = float(getattr(quote, "bid_price", 0) or 0)
        ask = float(getattr(quote, "ask_price", 0) or 0)
        if bid <= 0 or ask <= 0:
            return None, "NO_BID_OR_ASK"
        if ask < bid:
            return None, "CROSSED_QUOTE"

        midpoint = (bid + ask) / 2.0
        if midpoint <= 0:
            return None, "NO_BID_OR_ASK"

        spread_percent = (ask - bid) / midpoint * 100.0
        if spread_percent > self.config.max_spread_percent:
            return None, f"SPREAD_TOO_WIDE:{spread_percent:.1f}%"

        open_interest = self._parse_int(getattr(contract, "open_interest", None))
        if open_interest < self.config.min_open_interest:
            return None, f"LOW_OPEN_INTEREST:{open_interest}"

        return OptionCandidate(
            contract_symbol=str(contract.symbol),
            option_type=contract_type,
            strike_price=strike,
            expiration_date=expiration,
            dte=dte,
            bid_price=bid,
            ask_price=ask,
            midpoint=midpoint,
            spread_percent=spread_percent,
            strike_distance_percent=strike_distance_percent,
            open_interest=open_interest,
            alpaca_contract=contract,
            snapshot=snapshot,
        ), "QUALIFIED"

    @staticmethod
    def _parse_int(
        value,
    ) -> int:

        if value is None:
            return 0

        try:
            return int(
                float(value)
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0