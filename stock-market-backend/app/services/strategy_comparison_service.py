from __future__ import annotations

from typing import Any

from app.strategies.v2 import decide_long_setup_v2


class StrategyComparisonService:
    """
    Compare the existing V1 decision with V2 using the SAME
    SetupService snapshot.

    Important:
    - Does not query market data.
    - Does not update signal lifecycle.
    - Does not update position lifecycle.
    - Does not submit broker orders.
    - V1 remains the production decision.
    """

    @staticmethod
    def compare(
        *,
        setup: dict[str, Any],
    ) -> dict[str, Any]:

        # -------------------------------------------------
        # 1. Extract existing analysis snapshot
        # -------------------------------------------------

        symbol = str(
            setup.get("symbol") or ""
        ).strip().upper()

        current_price = float(
            setup.get("current_price") or 0.0
        )

        multi = setup.get("multi_timeframe") or {}
        risk_reward = setup.get("risk_reward") or {}
        breakout = setup.get("breakout_confirmation") or {}

        # -------------------------------------------------
        # 2. V1 result
        #
        # Do NOT execute V1 again.
        # SetupService already calculated it.
        # -------------------------------------------------

        v1_action = str(
            setup.get("action") or "UNKNOWN"
        ).upper()

        v1_actionable = bool(
            setup.get("actionable", False)
        )

        v1_reasons = list(
            setup.get("decision_reasons") or []
        )

        # -------------------------------------------------
        # 3. Extract common analytical inputs
        # -------------------------------------------------

        overall_score = int(
            multi.get("overall_score") or 0
        )

        overall_classification = str(
            multi.get("overall_classification")
            or "UNKNOWN"
        )

        risk_reward_quality = str(
            risk_reward.get("quality")
            or "UNAVAILABLE"
        )

        rr_1 = StrategyComparisonService._optional_float(
            risk_reward.get("rr_1")
        )

        rr_2 = StrategyComparisonService._optional_float(
            risk_reward.get("rr_2")
        )

        nearest_support = (
            StrategyComparisonService._extract_support(
                setup=setup,
                risk_reward=risk_reward,
            )
        )

        nearest_resistance = (
            StrategyComparisonService._extract_resistance(
                setup=setup,
                risk_reward=risk_reward,
            )
        )

        atr_14 = (
            StrategyComparisonService._extract_atr(
                setup=setup
            )
        )

        breakout_confirmed = bool(
            breakout.get("confirmed", False)
        )

        breakout_status = (
            str(breakout.get("status"))
            if breakout.get("status") is not None
            else None
        )

        breakout_confirmation_price = (
            StrategyComparisonService._optional_float(
                breakout.get("confirmation_price")
            )
        )

        # -------------------------------------------------
        # 4. Run V2 only
        # -------------------------------------------------

        v2 = decide_long_setup_v2(
            overall_score=overall_score,
            overall_classification=overall_classification,
            risk_reward_quality=risk_reward_quality,
            rr_1=rr_1,
            rr_2=rr_2,
            current_price=current_price,
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            atr_14=atr_14,
            breakout_confirmed=breakout_confirmed,
            breakout_status=breakout_status,
            breakout_confirmation_price=(
                breakout_confirmation_price
            ),
        )

        # -------------------------------------------------
        # 5. Compare decisions
        # -------------------------------------------------

        action_changed = (
            v1_action != v2.action
        )

        actionable_changed = (
            v1_actionable != v2.actionable
        )

        # V2 becoming actionable while V1 is not is the
        # most important condition to review manually.
        v2_new_entry_candidate = (
            not v1_actionable
            and v2.actionable
        )

        # -------------------------------------------------
        # 6. Return comparison
        # -------------------------------------------------

        return {
            "symbol": symbol,

            "market_snapshot": {
                "current_price": current_price,
                "overall_score": overall_score,
                "overall_classification":
                    overall_classification,
                "risk_reward_quality":
                    risk_reward_quality,
                "rr_1": rr_1,
                "rr_2": rr_2,
                "nearest_support": nearest_support,
                "nearest_resistance":
                    nearest_resistance,
                "atr_14": atr_14,
                "breakout_status": breakout_status,
                "breakout_confirmed":
                    breakout_confirmed,
            },

            "v1": {
                "strategy_version":
                    "SELECTION_ENGINE_V1",
                "action": v1_action,
                "actionable": v1_actionable,
                "reasons": v1_reasons,
            },

            "v2": {
                "strategy_version":
                    v2.strategy_version,
                "action": v2.action,
                "actionable": v2.actionable,
                "quality_score":
                    v2.quality_score,
                "quality": v2.quality,
                "reasons": v2.reasons,
            },

            "comparison": {
                "action_changed":
                    action_changed,

                "actionable_changed":
                    actionable_changed,

                "v2_new_entry_candidate":
                    v2_new_entry_candidate,

                "requires_review":
                    (
                        action_changed
                        or actionable_changed
                    ),
            },
        }

    # -----------------------------------------------------
    # Helpers
    # -----------------------------------------------------

    @staticmethod
    def _optional_float(
        value: Any,
    ) -> float | None:

        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_support(
        *,
        setup: dict[str, Any],
        risk_reward: dict[str, Any],
    ) -> float | None:
        """
        Prefer the structural stop/reference already used
        by SetupService.

        We intentionally do not query AnalysisService again.
        """

        # First preference: explicit support if SetupService
        # later exposes one.
        value = setup.get("nearest_support")

        if value is not None:
            return StrategyComparisonService._optional_float(
                value
            )

        # Current SetupService snapshot may not expose support
        # directly. The risk stop is NOT automatically support,
        # so don't silently substitute stop_loss here.
        return None

    @staticmethod
    def _extract_resistance(
        *,
        setup: dict[str, Any],
        risk_reward: dict[str, Any],
    ) -> float | None:

        value = setup.get("nearest_resistance")

        if value is not None:
            return StrategyComparisonService._optional_float(
                value
            )

        # target_1 generally originates from structural
        # resistance in the existing risk model.
        return StrategyComparisonService._optional_float(
            risk_reward.get("target_1")
        )

    @staticmethod
    def _extract_atr(
        *,
        setup: dict[str, Any],
    ) -> float | None:
        """
        SetupService currently does not expose ATR as a
        top-level field. Do not perform another market-data
        query just for comparison.
        """

        value = setup.get("atr_14")

        return StrategyComparisonService._optional_float(
            value
        )