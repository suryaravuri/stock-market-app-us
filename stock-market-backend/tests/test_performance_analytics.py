from datetime import date, datetime, timezone

import pytest

from app.analytics.performance import (
    Fill,
    aggregate_pnl,
    bucket_key,
    change_pct,
    group_by_sector,
    reference_close,
    round_trips,
)


def t(day, hour=15):
    return datetime(2026, 11, day, hour, tzinfo=timezone.utc)


def test_reference_close_periods():
    closes = [float(100 - i) for i in range(70)]  # newest first: 100 (yesterday), 99, ...
    assert reference_close(closes, "1D") == 100
    assert reference_close(closes, "1W") == 96
    assert reference_close(closes, "1M") == 80
    assert reference_close(closes, "3M") == 38
    assert reference_close(closes[:3], "1W") is None


def test_change_pct():
    assert change_pct(105, 100) == 5.0
    assert change_pct(None, 100) is None


def test_group_by_sector_sorted():
    rows = [
        {"symbol": "NVDA", "sector": "SEMI", "change_pct": -3.0},
        {"symbol": "AVGO", "sector": "SEMI", "change_pct": 1.0},
        {"symbol": "KO", "sector": "STAPLES", "change_pct": 0.5},
        {"symbol": "NEW", "sector": "STAPLES", "change_pct": None},
    ]
    out = group_by_sector(rows)
    assert [s["sector"] for s in out] == ["STAPLES", "SEMI"]
    semi = out[1]
    assert semi["avg_change_pct"] == -1.0 and semi["advancers"] == 1 and semi["decliners"] == 1
    assert [s["symbol"] for s in semi["stocks"]] == ["AVGO", "NVDA"]
    assert out[0]["stocks"][-1]["symbol"] == "NEW"   # unknown change last


def test_round_trips_from_real_orders():
    # Nov 16-18 paper fills
    fills = [
        Fill("NXPI", "buy", 7, 260.50, t(16, 18)), Fill("NXPI", "sell", 7, 259.03, t(16, 18)),
        Fill("NXPI", "buy", 7, 259.61, t(16, 19)), Fill("NXPI", "sell", 7, 258.83, t(16, 19)),
        Fill("ADBE", "buy", 8, 247.64625, t(16, 20)), Fill("ADBE", "sell", 8, 246.50, t(16, 20)),
        Fill("AVGO", "buy", 5, 349.928, t(18, 14)), Fill("AVGO", "sell", 5, 351.97, t(18, 15)),
    ]
    trades = round_trips(fills)
    pnl = {(x["symbol"], x["entry_price"]): x["pnl"] for x in trades}
    assert pnl[("NXPI", 260.50)] == pytest.approx(-10.29)
    assert pnl[("NXPI", 259.61)] == pytest.approx(-5.46)
    assert pnl[("ADBE", 247.64625)] == pytest.approx(-9.17)
    assert pnl[("AVGO", 349.928)] == pytest.approx(10.21)


def test_round_trips_partial_and_open():
    fills = [Fill("X", "buy", 10, 10, t(2)), Fill("X", "sell", 4, 12, t(3)), Fill("X", "buy", 5, 11, t(4))]
    trades = round_trips(fills)
    assert len(trades) == 1 and trades[0]["qty"] == 4 and trades[0]["pnl"] == 8.0


def test_bucket_keys():
    d = date(2026, 11, 18)  # Wednesday
    assert bucket_key(d, "day")[0] == "2026-11-18"
    assert bucket_key(d, "week") == ("2026-11-16", "Week of Nov 16")
    assert bucket_key(d, "month") == ("2026-11", "Nov 2026")


def test_aggregate_week():
    equity = [(date(2026, 11, 16), 99_970.0), (date(2026, 11, 17), 99_960.0),
              (date(2026, 11, 18), 99_980.0)]
    trades = [{"exit_time": t(16), "pnl": -10.0}, {"exit_time": t(18), "pnl": 10.0}]
    out = aggregate_pnl(equity, 100_000.0, trades, "week", lambda x: x.date())
    assert len(out) == 1
    b = out[0]
    assert b["account_pnl"] == -20.0 and b["realized_pnl"] == 0.0
    assert b["trades"] == 2 and b["win_rate"] == 50.0
    assert b["account_pnl_pct"] == -0.02
