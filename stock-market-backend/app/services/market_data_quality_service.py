from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_candle import MarketCandle
from app.repositories.stock_repository import StockRepository
from app.schemas.market import MarketTimeframe


@dataclass(frozen=True)
class CandleValidation:
    valid: bool
    issues: list[str]


class MarketDataQualityService:
    """Validate stored market candles before they are used by entry logic."""

    DEFAULT_LOOKBACK = 25

    @staticmethod
    def validate_candle(candle: MarketCandle) -> CandleValidation:
        issues: list[str] = []

        open_price = float(candle.open_price)
        high_price = float(candle.high_price)
        low_price = float(candle.low_price)
        close_price = float(candle.close_price)
        volume = float(candle.volume or 0)
        vwap = float(candle.vwap) if candle.vwap is not None else None

        if min(open_price, high_price, low_price, close_price) <= 0:
            issues.append("NON_POSITIVE_PRICE")
        if high_price < low_price:
            issues.append("HIGH_BELOW_LOW")
        if high_price < max(open_price, close_price):
            issues.append("HIGH_BELOW_OPEN_OR_CLOSE")
        if low_price > min(open_price, close_price):
            issues.append("LOW_ABOVE_OPEN_OR_CLOSE")
        if volume <= 0:
            issues.append("NON_POSITIVE_VOLUME")
        if candle.trade_count is not None and candle.trade_count < 0:
            issues.append("NEGATIVE_TRADE_COUNT")
        if vwap is not None and not (low_price <= vwap <= high_price):
            issues.append("VWAP_OUTSIDE_BAR_RANGE")

        return CandleValidation(valid=not issues, issues=issues)

    @staticmethod
    def _serialize_candle(candle: MarketCandle, validation: CandleValidation) -> dict:
        return {
            "timestamp": candle.candle_time,
            "open": float(candle.open_price),
            "high": float(candle.high_price),
            "low": float(candle.low_price),
            "close": float(candle.close_price),
            "volume": float(candle.volume or 0),
            "trade_count": candle.trade_count,
            "vwap": float(candle.vwap) if candle.vwap is not None else None,
            "source": candle.source,
            "valid": validation.valid,
            "issues": validation.issues,
        }

    @staticmethod
    def get_quality_report(
        db: Session,
        symbol: str,
        timeframe: MarketTimeframe = MarketTimeframe.FIFTEEN_MINUTES,
        lookback: int = DEFAULT_LOOKBACK,
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
            .limit(lookback)
        )
        candles = list(db.scalars(stmt).all())
        candles.reverse()

        if not candles:
            raise ValueError(
                f"No market candles found for '{symbol}' ({timeframe.value})"
            )

        validations = [
            MarketDataQualityService.validate_candle(candle)
            for candle in candles
        ]

        valid_pairs = [
            (candle, validation)
            for candle, validation in zip(candles, validations)
            if validation.valid
        ]
        invalid_pairs = [
            (candle, validation)
            for candle, validation in zip(candles, validations)
            if not validation.valid
        ]

        zero_volume_count = sum(
            1 for candle in candles if float(candle.volume or 0) <= 0
        )
        invalid_ohlc_count = sum(
            1
            for validation in validations
            if any(
                issue in validation.issues
                for issue in (
                    "NON_POSITIVE_PRICE",
                    "HIGH_BELOW_LOW",
                    "HIGH_BELOW_OPEN_OR_CLOSE",
                    "LOW_ABOVE_OPEN_OR_CLOSE",
                )
            )
        )

        latest = candles[-1]
        latest_validation = validations[-1]

        prior_positive_volumes = [
            float(candle.volume)
            for candle in candles[:-1]
            if float(candle.volume or 0) > 0
            and MarketDataQualityService.validate_candle(candle).valid
        ]
        avg_prior_volume = (
            mean(prior_positive_volumes)
            if prior_positive_volumes
            else None
        )
        latest_volume = float(latest.volume or 0)
        volume_ratio_raw = (
            latest_volume / avg_prior_volume
            if avg_prior_volume and avg_prior_volume > 0
            else None
        )

        issue_counts: dict[str, int] = {}
        for validation in validations:
            for issue in validation.issues:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1

        if not latest_validation.valid:
            status = "FAIL"
        elif invalid_pairs:
            status = "WARN"
        else:
            status = "PASS"

        usable_for_breakout = (
            latest_validation.valid
            and len(valid_pairs) >= 21
            and len(prior_positive_volumes) >= 20
        )

        notes: list[str] = []
        if zero_volume_count:
            notes.append(f"Found {zero_volume_count} candle(s) with non-positive volume")
        if invalid_ohlc_count:
            notes.append(f"Found {invalid_ohlc_count} candle(s) with invalid OHLC structure")
        if volume_ratio_raw is not None and volume_ratio_raw < 0.01:
            notes.append(
                "Latest volume is less than 1% of the valid prior-candle average; "
                "verify the source bar before using volume confirmation"
            )

        return {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "status": status,
            "usable_for_breakout": usable_for_breakout,
            "candles_checked": len(candles),
            "valid_candles": len(valid_pairs),
            "invalid_candles": len(invalid_pairs),
            "zero_volume_candles": zero_volume_count,
            "invalid_ohlc_candles": invalid_ohlc_count,
            "issue_counts": issue_counts,
            "latest_candle": MarketDataQualityService._serialize_candle(
                latest, latest_validation
            ),
            "volume_diagnostics": {
                "latest_volume": latest_volume,
                "valid_prior_volume_count": len(prior_positive_volumes),
                "average_prior_volume": round(avg_prior_volume, 4)
                if avg_prior_volume is not None
                else None,
                "volume_ratio_raw": round(volume_ratio_raw, 6)
                if volume_ratio_raw is not None
                else None,
            },
            "notes": notes,
        }
