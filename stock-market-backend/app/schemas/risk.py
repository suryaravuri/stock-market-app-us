from pydantic import BaseModel


class SetupRiskSummary(BaseModel):
    actionable: bool
    action: str
    decision_reasons: list[str]
    overall_score: int
    overall_classification: str
    risk_reward_quality: str


class PositionSizeDetails(BaseModel):
    allowed: bool
    shares: int

    account_size: float
    risk_percent: float
    max_risk_amount: float
    max_position_percent: float
    max_position_value: float

    entry_price: float | None
    stop_loss: float | None
    risk_per_share: float | None

    position_value: float
    actual_risk_amount: float

    reason: str | None


class OptionAnalysisSummary(BaseModel):
    status: str
    reason: str
    strategy_status: str
    option_type: str | None
    analysis_allowed: bool
    execution_allowed: bool
    contract_symbol: str | None
    observation_id: int | None


class PositionSizeResponse(BaseModel):
    symbol: str
    setup: SetupRiskSummary
    position: PositionSizeDetails
    option_analysis: OptionAnalysisSummary | None = None
