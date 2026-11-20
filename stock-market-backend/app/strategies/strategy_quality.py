from __future__ import annotations

from collections import defaultdict


REAL_SOURCES = {"PRODUCTION_ANALYTICAL"}
TEST_SOURCES = {"ISOLATED_TEST"}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _quality_for_real_entries(entries: list[dict]) -> dict:
    total = len(entries)
    r_values = [e["realized_r"] for e in entries if e.get("realized_r") is not None]
    wins = [e for e in entries if e.get("outcome") == "WIN"]
    losses = [e for e in entries if e.get("outcome") == "LOSS"]
    breakeven = [e for e in entries if e.get("outcome") == "BREAKEVEN"]

    avg_r = sum(r_values) / len(r_values) if r_values else None
    gross_profit_r = sum(max(float(e.get("realized_r") or 0.0), 0.0) for e in entries)
    gross_loss_r = sum(abs(min(float(e.get("realized_r") or 0.0), 0.0)) for e in entries)
    profit_factor = gross_profit_r / gross_loss_r if gross_loss_r > 0 else None
    win_rate = (len(wins) * 100.0 / total) if total else 0.0

    # Score is deliberately conservative. Sample size is the largest component so
    # a tiny winning sample cannot be labeled a trustworthy strategy.
    sample_score = _clamp(total / 30.0 * 40.0, 0.0, 40.0)
    expectancy_score = 0.0 if avg_r is None else _clamp((avg_r + 0.25) / 1.25 * 30.0, 0.0, 30.0)
    if profit_factor is None:
        pf_score = 20.0 if total and not losses else 0.0
    else:
        pf_score = _clamp((profit_factor - 0.75) / 1.25 * 20.0, 0.0, 20.0)
    win_score = _clamp((win_rate - 35.0) / 30.0 * 10.0, 0.0, 10.0)
    score = round(sample_score + expectancy_score + pf_score + win_score, 2)

    if total < 5:
        confidence = "INSUFFICIENT_DATA"
    elif total < 15:
        confidence = "VERY_LOW"
    elif total < 30:
        confidence = "LOW"
    elif total < 60:
        confidence = "MODERATE"
    else:
        confidence = "HIGH"

    if total < 15:
        grade = "UNRATED"
    elif score >= 80:
        grade = "A"
    elif score >= 65:
        grade = "B"
    elif score >= 50:
        grade = "C"
    elif score >= 35:
        grade = "D"
    else:
        grade = "F"

    return {
        "real_trade_count": total,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(breakeven),
        "win_rate_pct": round(win_rate, 2),
        "average_r": round(avg_r, 4) if avg_r is not None else None,
        "profit_factor_r": round(profit_factor, 4) if profit_factor is not None else None,
        "sample_size_score": round(sample_score, 2),
        "expectancy_score": round(expectancy_score, 2),
        "profit_factor_score": round(pf_score, 2),
        "win_rate_score": round(win_score, 2),
        "quality_score": score,
        "quality_grade": grade,
        "confidence": confidence,
        "minimum_real_trades_for_grade": 15,
        "recommended_real_trades_for_confidence": 30,
    }


def calculate_strategy_quality(entries: list[dict]) -> dict:
    real_entries = [e for e in entries if e.get("source") in REAL_SOURCES]
    test_entries = [e for e in entries if e.get("source") in TEST_SOURCES]
    unknown_entries = [e for e in entries if e.get("source") not in REAL_SOURCES | TEST_SOURCES]

    q = _quality_for_real_entries(real_entries)
    if not real_entries:
        assessment = "NOT_EVALUABLE"
        note = "No completed production analytical trades are available. Isolated engineering tests are excluded from strategy quality scoring."
    elif q["real_trade_count"] < q["minimum_real_trades_for_grade"]:
        assessment = "INSUFFICIENT_REAL_SAMPLE"
        note = "Real analytical trades exist, but the sample is too small for a strategy quality grade."
    elif (q["average_r"] or 0.0) <= 0:
        assessment = "NEGATIVE_EXPECTANCY"
        note = "The available real analytical sample has non-positive average R."
    else:
        assessment = "EVALUATED"
        note = "Quality score uses only completed production analytical trades; isolated validation tests are reported separately."

    return {
        "assessment": assessment,
        "quality_note": note,
        "real_market_trade_count": len(real_entries),
        "isolated_test_trade_count": len(test_entries),
        "unknown_source_trade_count": len(unknown_entries),
        "test_trades_excluded_from_score": len(test_entries),
        **q,
    }


def calculate_quality_breakdown(entries: list[dict], field: str) -> list[dict]:
    groups = defaultdict(list)
    for entry in entries:
        if entry.get("source") in REAL_SOURCES:
            groups[entry[field]].append(entry)
    result = []
    for key in sorted(groups):
        row = _quality_for_real_entries(groups[key])
        result.append({"key": key, **row})
    return result
