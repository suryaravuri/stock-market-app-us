from pydantic import BaseModel

from app.schemas.breakout import BreakoutConfirmationResponse
from app.schemas.signal_lifecycle import SignalLifecycleResponse
from app.schemas.position_lifecycle import PositionLifecycleResponse


class RiskRewardResponse(BaseModel):
    available: bool = True
    reason: str | None = None
    entry: float | None
    stop_loss: float | None
    target_1: float | None
    target_2: float | None

    risk_per_share: float | None
    reward_1_per_share: float | None
    reward_2_per_share: float | None

    rr_1: float | None
    rr_2: float | None

    quality: str
    recalculated_after_breakout: bool = False
    calculation_basis: str = "PRE_BREAKOUT_STRUCTURE"
    target_source: str = "STRUCTURAL_RESISTANCE"


class SetupResponse(BaseModel):
    symbol: str
    current_price: float

    multi_timeframe: dict
    risk_reward: RiskRewardResponse
    breakout_confirmation: BreakoutConfirmationResponse
    signal_lifecycle: SignalLifecycleResponse
    position_lifecycle: PositionLifecycleResponse

    action: str
    decision_reasons: list[str]
    actionable: bool
