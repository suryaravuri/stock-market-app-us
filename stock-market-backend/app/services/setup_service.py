from sqlalchemy.orm import Session

from app.risk.risk_model import long_risk_kwargs
from app.core.config import settings
from app.risk import (
    calculate_long_risk_reward,
    calculate_confirmed_breakout_risk_reward,
    calculate_position_size,
)
from app.models.stock import Stock
from app.market.sessions import is_indian_exchange
from app.services.option_analysis_orchestrator import (
    OptionAnalysisOrchestrator,
)

from app.schemas.market import MarketTimeframe
from app.services.analysis_service import AnalysisService
from app.services.breakout_service import BreakoutService
from app.services.multi_timeframe_service import MultiTimeframeService
from app.services.signal_lifecycle_service import SignalLifecycleService
from app.services.position_lifecycle_service import PositionLifecycleService
from app.strategies import decide_long_setup


class SetupService:

    @staticmethod
    def get_setup(
        db: Session,
        symbol: str,
    ) -> dict:

        symbol = symbol.strip().upper()

        # Execution timeframe
        intraday = AnalysisService.get_summary(
            db=db,
            symbol=symbol,
            timeframe=MarketTimeframe.FIFTEEN_MINUTES,
        )

        # Broader trend context
        multi = MultiTimeframeService.get_analysis(
            db=db,
            symbol=symbol,
        )

        # Entry trigger is evaluated independently from trend and R/R.
        breakout = BreakoutService.get_confirmation(
            db=db,
            symbol=symbol,
            timeframe=MarketTimeframe.FIFTEEN_MINUTES,
        )

        nearest_support = intraday["support"]["nearest"]
        nearest_resistance = intraday["resistance"]["nearest"]
        atr_14 = intraday["indicators"]["atr_14"]

        # A confirmed breakout has its own post-breakout structural risk model
        # and must not be blocked by the absence of a pre-breakout support level.
        if breakout["confirmed"] and breakout.get("follow_through_close") is not None:
            structural_resistances = [
                level
                for level in (
                    intraday["resistance"]["nearest"],
                    intraday["resistance"]["next"],
                    intraday["resistance"]["strongest"],
                )
                if level is not None
            ]
            risk = calculate_confirmed_breakout_risk_reward(
                confirmed_entry_price=breakout["follow_through_close"],
                breakout_level=breakout["breakout_level"],
                follow_through_low=breakout["follow_through_low"],
                atr_14=atr_14,
                structural_resistances=structural_resistances,
            )
        elif nearest_support is None:
            # "No support found" is a valid analytical market condition, not an
            # application failure.  Preserve the strict risk calculator and fail
            # closed here: no structural stop anchor means no long trade.
            reason = "No qualifying support level available for risk calculation"
            lifecycle = SignalLifecycleService.advance(
                db=db,
                symbol=symbol,
                timeframe=MarketTimeframe.FIFTEEN_MINUTES,
                overall_score=multi["overall_score"],
                decision_action="NO_TRADE",
                breakout=breakout,
                confirmed_entry_price=None,
            )
            unavailable_risk = {
                "available": False,
                "reason": reason,
                "entry": intraday["current_price"],
                "stop_loss": None,
                "target_1": intraday["resistance"]["nearest"],
                "target_2": intraday["resistance"]["next"],
                "risk_per_share": None,
                "reward_1_per_share": None,
                "reward_2_per_share": None,
                "rr_1": None,
                "rr_2": None,
                "quality": "UNAVAILABLE",
                "recalculated_after_breakout": False,
                "calculation_basis": "NO_STRUCTURAL_SUPPORT",
                "target_source": "STRUCTURAL_RESISTANCE",
            }
            position_lifecycle = PositionLifecycleService.advance_from_setup(
                db=db,
                symbol=symbol,
                timeframe=MarketTimeframe.FIFTEEN_MINUTES,
                signal_lifecycle=lifecycle,
                risk_reward=unavailable_risk,
                breakout=breakout,
                current_price=intraday["current_price"],
            )
            return {
                "symbol": symbol,
                "current_price": intraday["current_price"],
                "multi_timeframe": multi,
                "risk_reward": unavailable_risk,
                "breakout_confirmation": breakout,
                "signal_lifecycle": lifecycle,
                "position_lifecycle": position_lifecycle,
                "action": "NO_TRADE",
                "decision_reasons": [reason],
                "actionable": False,
            }
        else:
            risk = calculate_long_risk_reward(
                current_price=intraday["current_price"],
                nearest_support=nearest_support,
                nearest_resistance=intraday["resistance"]["nearest"],
                next_resistance=intraday["resistance"]["next"],
                atr_14=atr_14,
                **long_risk_kwargs(),
            )

        decision_current_price = (
            risk.entry if breakout["confirmed"] else intraday["current_price"]
        )
        decision_support = (
            breakout["breakout_level"]
            if breakout["confirmed"] and breakout.get("breakout_level") is not None
            else intraday["support"]["nearest"]
        )

        decision = decide_long_setup(
            overall_score=multi["overall_score"],
            overall_classification=multi["overall_classification"],
            risk_reward_quality=risk.quality,
            current_price=decision_current_price,
            nearest_support=decision_support,
            nearest_resistance=intraday["resistance"]["nearest"],
            atr_14=intraday["indicators"]["atr_14"],
            breakout_confirmed=breakout["confirmed"],
            breakout_status=breakout["status"],
            breakout_confirmation_price=breakout["confirmation_price"],
        )

        # Improvement #12: persist the signal lifecycle so repeated API reads
        # advance one state machine instead of treating every request in isolation.
        lifecycle = SignalLifecycleService.advance(
            db=db,
            symbol=symbol,
            timeframe=MarketTimeframe.FIFTEEN_MINUTES,
            overall_score=multi["overall_score"],
            decision_action=decision.action,
            breakout=breakout,
            confirmed_entry_price=(risk.entry if breakout["confirmed"] else None),
        )

        position_size = calculate_position_size(
            account_size=settings.account_size,
            risk_percent=settings.risk_percent,
            entry_price=risk.entry,
            stop_loss=risk.stop_loss,
            actionable=decision.actionable,
            max_position_percent=settings.max_position_percent,
        )

        # Improvement #15: maintain an analysis-only post-entry position
        # lifecycle. This never submits or modifies a broker order. A position
        # can be created only after the signal lifecycle reaches ENTRY_CONFIRMED.
        position_lifecycle = PositionLifecycleService.advance_from_setup(
            db=db,
            symbol=symbol,
            timeframe=MarketTimeframe.FIFTEEN_MINUTES,
            signal_lifecycle=lifecycle,
            risk_reward={
                "entry": risk.entry,
                "stop_loss": risk.stop_loss,
                "target_1": risk.target_1,
                "target_2": risk.target_2,
                "risk_per_share": risk.risk_per_share,
                "quantity": position_size.shares,
                "recalculated_after_breakout": risk.recalculated_after_breakout,
                "calculation_basis": risk.calculation_basis,
                "target_source": risk.target_source,
            },
            breakout=breakout,
            current_price=intraday["current_price"],
        )

        # ---------------------------------------------------------
        # Options analysis integration.
        #
        # V1 is intentionally long-side and analysis-only.
        # Contract selection is invoked only after the existing
        # stock lifecycle reaches ENTRY_CONFIRMED.
        #
        # No broker option order is submitted here.
        # ---------------------------------------------------------

        option_analysis = None

        signal_state = str(
            lifecycle.get("state") or ""
        ).upper()

        if (
            signal_state == "ENTRY_CONFIRMED"
            and decision.actionable
        ):
            stock = (
                db.query(Stock)
                .filter(Stock.symbol == symbol)
                .first()
            )

            # Options analysis uses Alpaca's US option chains; skip NSE/BSE stocks.
            if stock is not None and not is_indian_exchange(stock.exchange):
                option_result = (
                    OptionAnalysisOrchestrator().analyze(
                        db=db,
                        stock=stock,
                        underlying_price=float(
                            risk.entry
                        ),
                        signal_direction="BULLISH",
                        signal_score=float(
                            multi["overall_score"]
                        ),
                        signal_state=signal_state,
                        actionable=decision.actionable,
                    )
                )

                option_analysis = {
                    "status": option_result.status,
                    "reason": option_result.reason,
                    "strategy_status": (
                        option_result.strategy_decision.status
                    ),
                    "option_type": (
                        option_result.strategy_decision.option_type
                    ),
                    "analysis_allowed": (
                        option_result
                        .strategy_decision
                        .analysis_allowed
                    ),
                    "execution_allowed": (
                        option_result
                        .strategy_decision
                        .execution_allowed
                    ),
                    "contract_symbol": (
                        option_result.saved_contract.contract_symbol
                        if option_result.saved_contract
                        else None
                    ),
                    "observation_id": (
                        option_result.observation.observation_id
                        if option_result.observation
                        else None
                    ),
                }

        final_action = decision.action
        final_actionable = decision.actionable
        final_reasons = list(decision.reasons)
        if lifecycle.get("expired"):
            final_action = "SIGNAL_EXPIRED"
            final_actionable = False
            final_reasons.append(
                f"Signal expired: {lifecycle.get('expiration_reason') or lifecycle.get('staleness_status')}"
            )

        return {
            "symbol": symbol,
            "current_price": intraday["current_price"],
            # Shared analytical snapshot for V1/V2 comparison
            # "nearest_support": nearest_support,
            # "nearest_resistance": nearest_resistance,
            # "atr_14": atr_14,
            "multi_timeframe": multi,
            "risk_reward": {
                "available": True,
                "reason": None,
                "entry": risk.entry,
                "stop_loss": risk.stop_loss,
                "target_1": risk.target_1,
                "target_2": risk.target_2,
                "risk_per_share": risk.risk_per_share,
                "reward_1_per_share": risk.reward_1_per_share,
                "reward_2_per_share": risk.reward_2_per_share,
                "rr_1": risk.rr_1,
                "rr_2": risk.rr_2,
                "quality": risk.quality,
                "recalculated_after_breakout": risk.recalculated_after_breakout,
                "calculation_basis": risk.calculation_basis,
                "target_source": risk.target_source,
            },
            "breakout_confirmation": breakout,
            "signal_lifecycle": lifecycle,
            "position_lifecycle": position_lifecycle,

            # New
            "option_analysis": option_analysis,

            "action": decision.action,
            "decision_reasons": decision.reasons,
            "actionable": decision.actionable,
        }

