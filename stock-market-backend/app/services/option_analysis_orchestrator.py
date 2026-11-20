from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.stock import Stock
from app.services.option_candidate_service import (
    OptionCandidateService,
)
from app.services.option_strategy_risk_service import (
    OptionStrategyDecision,
    OptionStrategyRiskService,
)


@dataclass
class OptionAnalysisResult:
    status: str
    reason: str

    strategy_decision: OptionStrategyDecision

    selection_result: object | None = None
    saved_contract: object | None = None
    observation: object | None = None


class OptionAnalysisOrchestrator:

    def __init__(self) -> None:
        self.strategy_service = (
            OptionStrategyRiskService()
        )

        self.candidate_service = (
            OptionCandidateService()
        )

    def analyze(
        self,
        *,
        db: Session,
        stock: Stock,
        underlying_price: float,
        signal_direction: str,
        signal_score: float,
        signal_state: str,
        actionable: bool,
    ) -> OptionAnalysisResult:

        # ---------------------------------------
        # STEP 1
        # Evaluate options strategy/risk gate.
        # ---------------------------------------

        strategy_decision = (
            self.strategy_service.evaluate(
                underlying_symbol=stock.symbol,
                signal_direction=signal_direction,
                signal_score=signal_score,
                signal_state=signal_state,
                actionable=actionable,
            )
        )

        # ---------------------------------------
        # STEP 2
        # Fail closed when options analysis
        # is not approved.
        #
        # IMPORTANT:
        # Do not call the option-chain selector.
        # Do not persist a contract.
        # Do not create a selection observation.
        # ---------------------------------------

        if not strategy_decision.analysis_allowed:
            return OptionAnalysisResult(
                status="REJECTED",
                reason=strategy_decision.reason,
                strategy_decision=strategy_decision,
            )

        # Defensive check.
        if strategy_decision.option_type is None:
            return OptionAnalysisResult(
                status="REJECTED",
                reason=(
                    "Options strategy approved analysis "
                    "without an option type"
                ),
                strategy_decision=strategy_decision,
            )

        # ---------------------------------------
        # STEP 3
        # Contract selection + persistence +
        # selection observation.
        #
        # OptionCandidateService already owns
        # this complete pipeline.
        # ---------------------------------------

        (
            selection_result,
            saved_contract,
            observation,
        ) = (
            self.candidate_service
            .select_and_save_best_contract(
                db=db,
                stock=stock,
                underlying_price=underlying_price,
                option_type=(
                    strategy_decision.option_type
                ),
            )
        )

        # ---------------------------------------
        # STEP 4
        # Return analysis result.
        #
        # This orchestrator NEVER submits
        # a broker order.
        # ---------------------------------------

        return OptionAnalysisResult(
            status=selection_result.status,
            reason=selection_result.reason,
            strategy_decision=strategy_decision,
            selection_result=selection_result,
            saved_contract=saved_contract,
            observation=observation,
        )