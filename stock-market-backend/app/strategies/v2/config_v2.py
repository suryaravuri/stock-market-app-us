from dataclasses import dataclass


STRATEGY_VERSION = "SELECTION_ENGINE_V2"


@dataclass(frozen=True)
class V2Config:
    # Trend / multi-timeframe
    minimum_score: int = 25
    strong_score: int = 50

    # Risk / reward
    minimum_rr_1: float = 1.0
    preferred_rr_2: float = 2.0

    # Extension control
    max_support_atr_distance: float = 1.0

    # Composite quality
    minimum_entry_quality: int = 70


DEFAULT_V2_CONFIG = V2Config()