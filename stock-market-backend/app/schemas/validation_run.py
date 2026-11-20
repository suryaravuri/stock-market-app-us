from datetime import datetime
from pydantic import BaseModel, Field

class ValidationRunCreateRequest(BaseModel):
    strategy_version: str = Field(default="SELECTION_ENGINE_V1", min_length=1, max_length=80)

class ValidationRunResponse(BaseModel):
    validation_run_id: int
    strategy_version: str
    validation_phase: str
    execution_mode: str
    status: str
    baseline_hash: str
    baseline_status: str
    baseline_note: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    broker_order_submitted: bool = False

class ValidationProgressResponse(BaseModel):
    validation_run_id: int
    strategy_version: str
    status: str
    baseline_status: str
    signals_observed: int
    breakouts_detected: int
    follow_through_confirmed: int
    entries_confirmed: int
    positions_opened: int
    positions_closed: int
    wins: int
    losses: int
    breakeven: int
    execution_mode: str = "ANALYSIS_ONLY"
    isolated_test_positions_included: bool = False
    broker_order_submitted: bool = False
