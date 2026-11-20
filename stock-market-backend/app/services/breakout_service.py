from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.market.sessions import US_SESSION, MarketSession, session_for_stock
from app.models.market_candle import MarketCandle
from app.repositories.stock_repository import StockRepository
from app.schemas.market import MarketTimeframe
from app.services.indicator_service import IndicatorService
from app.services.market_data_quality_service import MarketDataQualityService
from app.strategies.breakout_confirmation import confirm_long_breakout


class BreakoutService:
    LOOKBACK = 20
    ATR_BUFFER = 0.05
    MIN_VOLUME_RATIO = 1.20
    MIN_BODY_RATIO = 0.50
    MIN_CLOSE_LOCATION = 0.70
    MAX_UPPER_WICK_RATIO = 0.30

    # Improvement #8: breakout candidates must be meaningful regular-session bars.
    SESSION_TZ = ZoneInfo("America/New_York")
    REGULAR_SESSION_OPEN = time(9, 30)
    REGULAR_SESSION_CLOSE = time(16, 0)  # candle start must be strictly before 16:00
    MIN_LIQUIDITY_RATIO = 0.10
    MIN_TRADE_COUNT = 10
    EXTRA_CANDLES = 100

    @staticmethod
    def _is_regular_session_candle(
        candle: MarketCandle,
        session: MarketSession = US_SESSION,
    ) -> bool:
        # Naive legacy timestamps are treated as UTC inside MarketSession.local().
        return session.is_regular(candle.candle_time)

    @staticmethod
    def _has_nonzero_range(candle: MarketCandle) -> bool:
        return float(candle.high_price) > float(candle.low_price)

    @staticmethod
    def _trade_count_ok(candle: MarketCandle) -> bool:
        # Missing trade_count is allowed because some feeds/timeframes may omit it.
        return (
            candle.trade_count is None
            or int(candle.trade_count) >= BreakoutService.MIN_TRADE_COUNT
        )

    @staticmethod
    def _base_eligible(candle: MarketCandle, session: MarketSession = US_SESSION) -> bool:
        validation = MarketDataQualityService.validate_candle(candle)
        return (
            validation.valid
            and BreakoutService._is_regular_session_candle(candle, session)
            and BreakoutService._has_nonzero_range(candle)
            and BreakoutService._trade_count_ok(candle)
        )

    @staticmethod
    def _select_candidate(
        candles: list[MarketCandle],
        session: MarketSession = US_SESSION,
    ) -> tuple[MarketCandle, list[MarketCandle], dict]:
        """Choose newest liquid regular-session candle and its 20-candle baseline.

        A candidate must pass structural validation, be inside the US regular session,
        have a non-zero price range, meet a small trade-count floor, and have at least
        10% of the average volume of the preceding 20 base-eligible candles.
        Thin boundary bars are skipped automatically and selection walks backward.
        """
        ignored_out_of_session = 0
        ignored_low_liquidity = 0
        ignored_zero_range = 0
        ignored_low_trade_count = 0
        ignored_invalid = 0

        # Pre-compute structural/session rejection counts for transparency.
        for candle in candles:
            validation = MarketDataQualityService.validate_candle(candle)
            if not validation.valid:
                ignored_invalid += 1
                continue
            if not BreakoutService._is_regular_session_candle(candle, session):
                ignored_out_of_session += 1
                continue
            if not BreakoutService._has_nonzero_range(candle):
                ignored_zero_range += 1
                continue
            if not BreakoutService._trade_count_ok(candle):
                ignored_low_trade_count += 1

        # Search newest to oldest. For each candidate, build its own preceding baseline
        # so volume eligibility is evaluated without look-ahead bias.
        for candidate_index in range(len(candles) - 1, -1, -1):
            candidate = candles[candidate_index]
            if not BreakoutService._base_eligible(candidate, session):
                continue

            prior_base = [
                candle
                for candle in candles[:candidate_index]
                if BreakoutService._base_eligible(candle, session)
            ]
            if len(prior_base) < BreakoutService.LOOKBACK:
                continue

            prior = prior_base[-BreakoutService.LOOKBACK :]
            avg_prior_volume = sum(float(c.volume) for c in prior) / len(prior)
            candidate_volume = float(candidate.volume or 0)
            liquidity_ratio = (
                candidate_volume / avg_prior_volume if avg_prior_volume > 0 else 0.0
            )

            if liquidity_ratio < BreakoutService.MIN_LIQUIDITY_RATIO:
                ignored_low_liquidity += 1
                continue

            diagnostics = {
                "ignored_out_of_session_candles": ignored_out_of_session,
                "ignored_low_liquidity_candles": ignored_low_liquidity,
                "ignored_zero_range_candles": ignored_zero_range,
                "ignored_low_trade_count_candles": ignored_low_trade_count,
                "ignored_invalid_candles": ignored_invalid,
                "selection_volume_ratio": liquidity_ratio,
                "selection_average_prior_volume": avg_prior_volume,
            }
            return candidate, prior, diagnostics

        raise ValueError(
            "No breakout-eligible regular-session candle found with sufficient "
            "liquidity and at least 20 prior eligible candles"
        )

    @staticmethod
    def get_confirmation(
        db: Session,
        symbol: str,
        timeframe: MarketTimeframe = MarketTimeframe.FIFTEEN_MINUTES,
    ) -> dict:
        symbol = symbol.strip().upper()
        stock = StockRepository.find_by_symbol(db, symbol)
        if stock is None:
            raise ValueError(f"Stock '{symbol}' not found")

        stmt = (
            select(MarketCandle)
            .where(
                MarketCandle.stock_id == stock.stock_id,
                MarketCandle.timeframe == timeframe.value,
            )
            .order_by(MarketCandle.candle_time.desc())
            .limit(BreakoutService.LOOKBACK + 1 + BreakoutService.EXTRA_CANDLES)
        )
        raw_candles = list(db.scalars(stmt).all())
        raw_candles.reverse()

        if len(raw_candles) < BreakoutService.LOOKBACK + 1:
            raise ValueError(
                f"At least {BreakoutService.LOOKBACK + 1} candles are required for breakout confirmation"
            )

        session = session_for_stock(stock)
        latest, prior, diagnostics = BreakoutService._select_candidate(raw_candles, session)

        indicators = IndicatorService.get_indicators(
            db=db,
            symbol=symbol,
            timeframe=timeframe,
        )

        prior_volumes = [float(c.volume) for c in prior]
        average_prior_volume = sum(prior_volumes) / len(prior_volumes)
        latest_volume = float(latest.volume)
        raw_volume_ratio = (
            latest_volume / average_prior_volume
            if average_prior_volume > 0
            else None
        )

        result = confirm_long_breakout(
            latest_close=float(latest.close_price),
            latest_open=float(latest.open_price),
            latest_volume=latest_volume,
            latest_high=float(latest.high_price),
            latest_low=float(latest.low_price),
            prior_highs=[float(c.high_price) for c in prior],
            prior_volumes=prior_volumes,
            atr_14=indicators["atr_14"],
            lookback=BreakoutService.LOOKBACK,
            atr_buffer=BreakoutService.ATR_BUFFER,
            min_volume_ratio=BreakoutService.MIN_VOLUME_RATIO,
            min_body_ratio=BreakoutService.MIN_BODY_RATIO,
            min_close_location=BreakoutService.MIN_CLOSE_LOCATION,
            max_upper_wick_ratio=BreakoutService.MAX_UPPER_WICK_RATIO,
        )

        # Improvement #10: a breakout candle is a detection event, not yet an entry.
        # Final entry requires the next qualified regular-session candle to hold the
        # breakout level or retest it and close back above it.
        breakout_detected = False
        follow_through_confirmed = False
        retest_confirmed = False
        follow_through_status = "NOT_APPLICABLE"
        breakout_candle_timestamp = None
        follow_through_candle_timestamp = None
        follow_through_close = None
        follow_through_low = None
        failed_quality_checks: list[str] = []

        # Improvement #10.1: diagnostics describe the selected candle even when
        # price has not broken out yet. This keeps API/UI/audit output consistent.
        if float(latest.close_price) <= float(latest.open_price):
            failed_quality_checks.append("CANDLE_NOT_BULLISH")
        if result.body_ratio is not None and result.body_ratio < BreakoutService.MIN_BODY_RATIO:
            failed_quality_checks.append("BODY_TOO_SMALL")
        if result.close_location is not None and result.close_location < BreakoutService.MIN_CLOSE_LOCATION:
            failed_quality_checks.append("CLOSE_NOT_NEAR_HIGH")
        if result.upper_wick_ratio is not None and result.upper_wick_ratio > BreakoutService.MAX_UPPER_WICK_RATIO:
            failed_quality_checks.append("UPPER_WICK_TOO_LARGE")
        if not result.volume_confirmed:
            failed_quality_checks.append("LOW_BREAKOUT_VOLUME")

        # These effective values normally describe the newest candidate. If that
        # candle is actually a follow-through candle, they are switched to the
        # prior confirmed breakout candle so ENTRY_CONFIRMED remains internally
        # consistent and Improvement #11 receives the correct breakout anchor.
        effective_result = result

        # If the latest qualified candle itself is a valid breakout, wait for the next
        # completed qualified candle instead of making the setup actionable immediately.
        if result.confirmed:
            breakout_detected = True
            breakout_candle_timestamp = latest.candle_time
            follow_through_status = "PENDING_FOLLOW_THROUGH"
            final_status = "BREAKOUT_DETECTED_PENDING_FOLLOW_THROUGH"
            final_confirmed = False
        else:
            final_status = result.status
            final_confirmed = False

            # Check whether the immediately preceding qualified/liquid candle was the
            # breakout candle and `latest` is now its follow-through/retest candle.
            latest_index = raw_candles.index(latest)
            if latest_index > 0:
                try:
                    prior_breakout, prior_breakout_baseline, _ = BreakoutService._select_candidate(
                        raw_candles[:latest_index], session
                    )
                    prior_result = confirm_long_breakout(
                        latest_close=float(prior_breakout.close_price),
                        latest_open=float(prior_breakout.open_price),
                        latest_volume=float(prior_breakout.volume),
                        latest_high=float(prior_breakout.high_price),
                        latest_low=float(prior_breakout.low_price),
                        prior_highs=[float(c.high_price) for c in prior_breakout_baseline],
                        prior_volumes=[float(c.volume) for c in prior_breakout_baseline],
                        atr_14=indicators["atr_14"],
                        lookback=BreakoutService.LOOKBACK,
                        atr_buffer=BreakoutService.ATR_BUFFER,
                        min_volume_ratio=BreakoutService.MIN_VOLUME_RATIO,
                        min_body_ratio=BreakoutService.MIN_BODY_RATIO,
                        min_close_location=BreakoutService.MIN_CLOSE_LOCATION,
                        max_upper_wick_ratio=BreakoutService.MAX_UPPER_WICK_RATIO,
                    )
                    if prior_result.confirmed and prior_result.breakout_level is not None:
                        effective_result = prior_result
                        # Quality failures above were about the follow-through candidate;
                        # for a confirmed prior breakout they are not breakout-quality failures.
                        failed_quality_checks = []
                        breakout_detected = True
                        breakout_candle_timestamp = prior_breakout.candle_time
                        follow_through_candle_timestamp = latest.candle_time
                        follow_through_close = float(latest.close_price)
                        follow_through_low = float(latest.low_price)
                        level = float(prior_result.breakout_level)
                        confirmation = float(prior_result.confirmation_price or level)
                        # HOLD: entire follow-through candle remains above old resistance.
                        hold_confirmed = follow_through_low > level and follow_through_close > level
                        # RETEST: price probes the breakout zone but closes back above the
                        # buffered confirmation price, showing that old resistance held.
                        retest_confirmed = (
                            follow_through_low <= confirmation
                            and follow_through_close >= confirmation
                        )
                        follow_through_confirmed = hold_confirmed or retest_confirmed
                        if follow_through_confirmed:
                            follow_through_status = "RETEST_HELD" if retest_confirmed else "FOLLOW_THROUGH_HELD"
                            final_status = "ENTRY_CONFIRMED"
                            final_confirmed = True
                        else:
                            follow_through_status = "FOLLOW_THROUGH_FAILED"
                            final_status = "FOLLOW_THROUGH_FAILED"
                            failed_quality_checks.append("FOLLOW_THROUGH_FAILED")
                except ValueError:
                    # Not enough earlier eligible candles to establish a prior breakout.
                    pass

        reasons = list(result.reasons)
        if final_status == "BREAKOUT_DETECTED_PENDING_FOLLOW_THROUGH":
            reasons.append("Breakout detected; waiting for the next qualified 15-minute candle to hold or retest the breakout level")
        elif final_status == "ENTRY_CONFIRMED":
            reasons.append(f"{follow_through_status}: next qualified candle preserved the breakout level")
        elif final_status == "FOLLOW_THROUGH_FAILED":
            reasons.append("Prior breakout failed follow-through/retest confirmation")
        notes: list[str] = []
        if diagnostics["ignored_out_of_session_candles"]:
            notes.append(
                f"Ignored {diagnostics['ignored_out_of_session_candles']} out-of-session candle(s)"
            )
        if diagnostics["ignored_low_liquidity_candles"]:
            notes.append(
                f"Ignored {diagnostics['ignored_low_liquidity_candles']} candle(s) below "
                f"{BreakoutService.MIN_LIQUIDITY_RATIO:.0%} of prior average volume"
            )
        if diagnostics["ignored_zero_range_candles"]:
            notes.append(
                f"Ignored {diagnostics['ignored_zero_range_candles']} zero-range candle(s)"
            )
        if diagnostics["ignored_low_trade_count_candles"]:
            notes.append(
                f"Ignored {diagnostics['ignored_low_trade_count_candles']} candle(s) with fewer than "
                f"{BreakoutService.MIN_TRADE_COUNT} trades"
            )
        if diagnostics["ignored_invalid_candles"]:
            notes.append(
                f"Ignored {diagnostics['ignored_invalid_candles']} structurally invalid candle(s)"
            )

        data_quality_note = "; ".join(notes) if notes else None
        if data_quality_note:
            reasons.append(data_quality_note)

        return {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "timestamp": latest.candle_time,
            "status": final_status,
            "confirmed": final_confirmed,
            "breakout_level": effective_result.breakout_level,
            "confirmation_price": effective_result.confirmation_price,
            "buffer_price": effective_result.buffer_price,
            "volume_ratio": effective_result.volume_ratio,
            "lookback_candles": BreakoutService.LOOKBACK,
            "min_volume_ratio": BreakoutService.MIN_VOLUME_RATIO,
            "min_body_ratio": BreakoutService.MIN_BODY_RATIO,
            "min_close_location": BreakoutService.MIN_CLOSE_LOCATION,
            "max_upper_wick_ratio": BreakoutService.MAX_UPPER_WICK_RATIO,
            "price_confirmed": effective_result.price_confirmed,
            "volume_confirmed": effective_result.volume_confirmed,
            "candle_quality_confirmed": effective_result.candle_quality_confirmed,
            "breakout_detected": breakout_detected,
            "follow_through_required": True,
            "follow_through_confirmed": follow_through_confirmed,
            "retest_confirmed": retest_confirmed,
            "follow_through_status": follow_through_status,
            "breakout_candle_timestamp": breakout_candle_timestamp,
            "follow_through_candle_timestamp": follow_through_candle_timestamp,
            "follow_through_close": round(follow_through_close, 4) if follow_through_close is not None else None,
            "follow_through_low": round(follow_through_low, 4) if follow_through_low is not None else None,
            "failed_quality_checks": failed_quality_checks,
            "candle_range": effective_result.candle_range,
            "body_ratio": effective_result.body_ratio,
            "close_location": effective_result.close_location,
            "upper_wick_ratio": effective_result.upper_wick_ratio,
            "ignored_zero_volume_candles": sum(
                1 for c in raw_candles if float(c.volume or 0) <= 0
            ),
            "ignored_invalid_candles": diagnostics["ignored_invalid_candles"],
            "ignored_out_of_session_candles": diagnostics["ignored_out_of_session_candles"],
            "ignored_low_liquidity_candles": diagnostics["ignored_low_liquidity_candles"],
            "ignored_zero_range_candles": diagnostics["ignored_zero_range_candles"],
            "ignored_low_trade_count_candles": diagnostics["ignored_low_trade_count_candles"],
            "session": "REGULAR",
            "session_timezone": session.timezone_name,
            "min_liquidity_ratio": BreakoutService.MIN_LIQUIDITY_RATIO,
            "min_trade_count": BreakoutService.MIN_TRADE_COUNT,
            "latest_volume": latest_volume,
            "average_prior_volume": round(average_prior_volume, 4),
            "volume_ratio_raw": round(raw_volume_ratio, 6) if raw_volume_ratio is not None else None,
            "data_quality_note": data_quality_note,
            "reasons": reasons,
        }
