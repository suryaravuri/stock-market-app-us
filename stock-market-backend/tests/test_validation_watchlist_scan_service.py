from types import SimpleNamespace

import pytest

from app.schemas.market import MarketTimeframe
from app.services.validation_watchlist_scan_service import ValidationWatchlistScanService


def test_16c_rejects_non_15min_before_db_access():
    with pytest.raises(ValueError, match="15Min"):
        ValidationWatchlistScanService.scan(
            db=None,
            validation_run_id=1,
            watchlist_id=1,
            timeframe=MarketTimeframe.ONE_HOUR,
        )


def test_16c_execution_mode_is_analysis_only():
    assert ValidationWatchlistScanService.EXECUTION_MODE == "ANALYSIS_ONLY"
