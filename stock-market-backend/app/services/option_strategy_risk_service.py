from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OptionStrategyRiskConfig:
    options_enabled: bool = True
    execution_enabled: bool = False


@dataclass(frozen=True)
class OptionStrategyDecision:
    status: str
    reason: str

    underlying_symbol: str
    signal_direction: str
    signal_score: float

    option_type: str | None

    analysis_allowed: bool
    execution_allowed: bool


class OptionStrategyRiskService:

    def __init__(
        self,
        config: OptionStrategyRiskConfig | None = None,
    ) -> None:
        self.config = config or OptionStrategyRiskConfig()

    def evaluate(
        self,
        *,
        underlying_symbol: str,
        signal_direction: str,
        signal_score: float,
        signal_state: str,
        actionable: bool,
    ) -> OptionStrategyDecision:

        symbol = underlying_symbol.strip().upper()
        direction = signal_direction.strip().upper()
        state = signal_state.strip().upper()

        if not symbol:
            raise ValueError("Underlying symbol is required")

        if direction not in {
            "BULLISH",
            "BEARISH",
            "NEUTRAL",
        }:
            raise ValueError(
                "signal_direction must be "
                "BULLISH, BEARISH or NEUTRAL"
            )

        if not self.config.options_enabled:
            return self._reject(
                symbol=symbol,
                direction=direction,
                score=signal_score,
                reason="Options analysis is disabled",
            )

        # V1 options integration is intentionally long-side only.
        #
        # The current stock strategy implements decide_long_setup()
        # and confirm_long_breakout(). We must not manufacture a
        # bearish/PUT signal that the upstream strategy has not
        # actually confirmed.
        if direction != "BULLISH":
            return self._reject(
                symbol=symbol,
                direction=direction,
                score=signal_score,
                reason=(
                    "Options V1 accepts only confirmed "
                    "long-side stock signals"
                ),
            )

        if state != "ENTRY_CONFIRMED":
            return self._reject(
                symbol=symbol,
                direction=direction,
                score=signal_score,
                reason=(
                    f"Stock signal lifecycle is {state}; "
                    "ENTRY_CONFIRMED is required"
                ),
            )

        if not actionable:
            return self._reject(
                symbol=symbol,
                direction=direction,
                score=signal_score,
                reason=(
                    "Stock decision is not actionable"
                ),
            )

        return OptionStrategyDecision(
            status="APPROVED_FOR_ANALYSIS",
            reason=(
                "Confirmed long-side stock entry passed "
                "the options analysis gate"
            ),
            underlying_symbol=symbol,
            signal_direction=direction,
            signal_score=signal_score,
            option_type="CALL",
            analysis_allowed=True,

            # HARD OFF for V1.
            execution_allowed=False,
        )

    def _reject(
        self,
        *,
        symbol: str,
        direction: str,
        score: float,
        reason: str,
    ) -> OptionStrategyDecision:

        return OptionStrategyDecision(
            status="REJECTED",
            reason=reason,
            underlying_symbol=symbol,
            signal_direction=direction,
            signal_score=score,
            option_type=None,
            analysis_allowed=False,
            execution_allowed=False,
        )