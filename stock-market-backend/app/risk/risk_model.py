"""Which pre-breakout risk/reward model the strategy uses.

    LEGACY     - original: stop at nearest support, targets = nearest/next
                 resistance (no target when price is at new highs).
    ATR_FLOOR  - stop at least 1 x ATR below entry; ATR-projected targets
                 when there is no resistance above.

The live app uses settings.risk_model. Backtests can override it per run
(use_risk_model) so both models can be compared on the same data.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from app.core.config import settings

RISK_MODELS = ("LEGACY", "ATR_FLOOR")

_override: ContextVar[str | None] = ContextVar("risk_model_override", default=None)


def current_risk_model() -> str:
    model = (_override.get() or settings.risk_model or "ATR_FLOOR").upper()
    return model if model in RISK_MODELS else "ATR_FLOOR"


@contextmanager
def use_risk_model(model: str | None):
    token = _override.set(model.upper() if model else None)
    try:
        yield
    finally:
        _override.reset(token)


def long_risk_kwargs() -> dict:
    """Extra arguments for calculate_long_risk_reward for the active model."""
    if current_risk_model() == "LEGACY":
        return {}
    return {
        "min_stop_atr": settings.risk_min_stop_atr,
        "atr_target_fallback": True,
        "target_1_atr": settings.risk_target_1_atr,
        "target_2_atr": settings.risk_target_2_atr,
    }
