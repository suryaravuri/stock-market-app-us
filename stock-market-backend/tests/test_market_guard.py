import pytest

from app.market.sectors import sector_for
from app.services.market_guard_service import (
    IndexMove,
    evaluate_market_mood,
    evaluate_sector_limit,
)


def test_market_ok_when_flat():
    ok, reason = evaluate_market_mood(
        [IndexMove("SPY", 600, 601, 602), IndexMove("QQQ", 500, 500, 499.5)], 1.0, 0.6)
    assert ok and "SPY +0.33%" in reason


def test_market_blocks_big_day_drop():
    ok, reason = evaluate_market_mood([IndexMove("QQQ", 500, 498, 494)], 1.0, 0.6)
    assert not ok and reason.startswith("MARKET_FILTER:QQQ -1.20% today")


def test_market_blocks_selloff_from_open_even_if_day_small():
    # gapped up, then sold off 0.8% from the open (like 9:50 AM on 2026-11-18)
    ok, reason = evaluate_market_mood([IndexMove("SPY", 600, 604, 600.0)], 1.0, 0.6)
    assert not ok and "since open" in reason


def test_market_fails_closed_without_data():
    ok, reason = evaluate_market_mood([], 1.0, 0.6)
    assert not ok and reason == "MARKET_FILTER:NO_INDEX_DATA"


def test_sector_map():
    assert sector_for("nxpi") == sector_for("AVGO") == "SEMICONDUCTORS"
    assert sector_for("XYZ", "Retail Trade") == "RETAIL_TRADE"
    assert sector_for("XYZ") == "UNKNOWN"


def test_sector_limit_blocks_third_chip_stock():
    ok, reason = evaluate_sector_limit("AMD", "SEMICONDUCTORS", {"NVDA", "AVGO", "COST"}, sector_for, 2)
    assert not ok and reason == "SECTOR_LIMIT:SEMICONDUCTORS already 2 (AVGO, NVDA)"


def test_sector_limit_allows_other_sector_and_unknown():
    assert evaluate_sector_limit("COST", "CONSUMER_STAPLES", {"NVDA", "AVGO"}, sector_for, 2)[0]
    assert evaluate_sector_limit("ZZZ", "UNKNOWN", {"A", "B", "C"}, sector_for, 1)[0]


def test_sector_limit_off():
    assert evaluate_sector_limit("AMD", "SEMICONDUCTORS", {"NVDA", "AVGO", "MU"}, sector_for, 0)[0]
