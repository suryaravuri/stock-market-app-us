from __future__ import annotations

from collections import defaultdict

REAL_SOURCES = {"PRODUCTION_ANALYTICAL"}
TEST_SOURCES = {"ISOLATED_TEST"}


def _round(value: float | None, digits: int = 2):
    return round(value, digits) if value is not None else None


def _stats(entries: list[dict]) -> dict:
    total = len(entries)
    r_values = [float(e["realized_r"]) for e in entries if e.get("realized_r") is not None]
    wins = [e for e in entries if e.get("outcome") == "WIN"]
    losses = [e for e in entries if e.get("outcome") == "LOSS"]
    breakeven = [e for e in entries if e.get("outcome") == "BREAKEVEN"]
    avg_r = sum(r_values) / len(r_values) if r_values else None
    gross_win_r = sum(max(r, 0.0) for r in r_values)
    gross_loss_r = sum(abs(min(r, 0.0)) for r in r_values)
    pf = gross_win_r / gross_loss_r if gross_loss_r > 0 else None
    win_rate = len(wins) * 100.0 / total if total else 0.0
    stop_exits = sum(1 for e in entries if e.get("state") == "STOP_HIT")
    target2_exits = sum(1 for e in entries if e.get("state") == "TARGET_2_HIT")
    trailing_exits = sum(1 for e in entries if e.get("exit_reason") == "TRAILING_STOP")
    avg_hold = (
        sum(float(e.get("holding_minutes") or 0.0) for e in entries) / total
        if total else None
    )
    return {
        "trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(breakeven),
        "win_rate_pct": _round(win_rate),
        "average_r": _round(avg_r, 4),
        "profit_factor_r": _round(pf, 4),
        "stop_exit_rate_pct": _round(stop_exits * 100.0 / total if total else 0.0),
        "target_2_exit_rate_pct": _round(target2_exits * 100.0 / total if total else 0.0),
        "trailing_stop_exit_rate_pct": _round(trailing_exits * 100.0 / total if total else 0.0),
        "average_holding_minutes": _round(avg_hold),
    }


def _group_stats(entries: list[dict], field: str) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        key = entry.get(field)
        if key:
            groups[str(key)].append(entry)
    return [{"key": key, **_stats(group)} for key, group in sorted(groups.items())]


def _issue(priority: int, severity: str, code: str, title: str, evidence: str, recommendation: str) -> dict:
    return {
        "priority": priority,
        "severity": severity,
        "code": code,
        "title": title,
        "evidence": evidence,
        "recommendation": recommendation,
    }


def diagnose_strategy(entries: list[dict]) -> dict:
    """Explain weaknesses using production analytical outcomes only.

    Isolated engineering tests are counted for transparency but cannot create
    strengths, hide weaknesses, or affect recommendations.
    """
    real = [e for e in entries if e.get("source") in REAL_SOURCES]
    tests = [e for e in entries if e.get("source") in TEST_SOURCES]
    unknown = [e for e in entries if e.get("source") not in REAL_SOURCES | TEST_SOURCES]
    s = _stats(real)
    by_symbol = _group_stats(real, "symbol")
    by_timeframe = _group_stats(real, "timeframe")

    weaknesses: list[dict] = []
    strengths: list[str] = []

    if not real:
        weaknesses.append(_issue(
            1, "CRITICAL", "NO_REAL_TRADE_EVIDENCE", "No production analytical trade evidence",
            "0 completed production analytical trades are available.",
            "Continue collecting naturally gated production analytical positions; do not infer strategy quality from isolated tests.",
        ))
        status = "NOT_EVALUABLE"
    else:
        status = "DIAGNOSTICS_AVAILABLE"
        n = s["trades"]
        if n < 15:
            weaknesses.append(_issue(
                1, "HIGH", "INSUFFICIENT_SAMPLE", "Sample size is too small for reliable conclusions",
                f"Only {n} production analytical trade(s); at least 15 are required for a grade and 30 are preferred for confidence.",
                "Collect more naturally occurring analytical trades before changing strategy rules from these results.",
            ))
        elif n < 30:
            weaknesses.append(_issue(
                1, "MEDIUM", "LIMITED_SAMPLE", "Performance evidence is still limited",
                f"{n} production analytical trades are available; confidence improves materially at 30+ trades.",
                "Keep the current rules stable while the sample grows so later comparisons remain meaningful.",
            ))
        else:
            strengths.append(f"Sample size has reached {n} production analytical trades.")

        avg_r = s["average_r"]
        if avg_r is None:
            weaknesses.append(_issue(2, "HIGH", "R_DATA_INCOMPLETE", "R-multiple data is incomplete", "Average R cannot be calculated.", "Verify that every completed analytical position persists a valid initial risk per share."))
        elif avg_r <= 0:
            weaknesses.append(_issue(2, "CRITICAL", "NON_POSITIVE_EXPECTANCY", "Average trade expectancy is non-positive", f"Average outcome is {avg_r:+.4f}R per trade.", "Review entry quality and stop/target placement before considering any execution-mode expansion."))
        elif avg_r < 0.25:
            weaknesses.append(_issue(2, "HIGH", "WEAK_EXPECTANCY", "Positive expectancy is too thin", f"Average outcome is only {avg_r:+.4f}R per trade.", "Investigate low-quality entries and exits that give back too much favorable excursion."))
        elif avg_r >= 0.5:
            strengths.append(f"Average expectancy is positive at {avg_r:+.4f}R per trade.")

        pf = s["profit_factor_r"]
        if pf is None:
            if s["losses"] == 0:
                strengths.append("No losing production analytical trades are present yet; profit factor is undefined rather than infinite.")
        elif pf < 1.0:
            weaknesses.append(_issue(3, "CRITICAL", "PROFIT_FACTOR_BELOW_ONE", "Loss R exceeds winning R", f"Profit factor is {pf:.4f}.", "Prioritize reducing poor entries and large losing outcomes before optimizing win rate."))
        elif pf < 1.25:
            weaknesses.append(_issue(3, "HIGH", "THIN_PROFIT_FACTOR", "Profit factor has little margin", f"Profit factor is {pf:.4f}.", "Review losing setups by symbol/timeframe and tighten quality filters only where the evidence is repeatable."))
        elif pf >= 1.5:
            strengths.append(f"Profit factor is {pf:.4f}, providing a healthier gross-R margin over losses.")

        wr = s["win_rate_pct"]
        if wr < 35 and (avg_r is None or avg_r < 0.5):
            weaknesses.append(_issue(4, "HIGH", "LOW_WIN_RATE", "Win rate is low without enough payoff compensation", f"Win rate is {wr:.2f}% and average R is {avg_r if avg_r is not None else 'unavailable'}.", "Compare losing entries with breakout quality and follow-through conditions; do not raise win rate by weakening stops mechanically."))
        elif wr < 45 and (avg_r is None or avg_r < 0.25):
            weaknesses.append(_issue(4, "MEDIUM", "LOW_WIN_RATE_THIN_EDGE", "Win rate leaves little room for error", f"Win rate is {wr:.2f}% with thin average R.", "Inspect which setup conditions distinguish winners from losers before changing thresholds."))

        stop_rate = s["stop_exit_rate_pct"]
        if stop_rate >= 75 and n >= 5 and (avg_r is None or avg_r < 0.25):
            weaknesses.append(_issue(5, "MEDIUM", "STOP_EXIT_CONCENTRATION", "Most trades terminate through stops", f"{stop_rate:.2f}% of completed trades end in STOP_HIT.", "Compare initial-stop exits versus trailing-stop exits and review whether entries are too early or post-target trailing is too aggressive."))

        # Only flag subgroup weakness once there is enough evidence in that subgroup.
        weak_symbols = [r for r in by_symbol if r["trades"] >= 5 and r["average_r"] is not None and r["average_r"] < 0]
        if weak_symbols:
            worst = min(weak_symbols, key=lambda r: r["average_r"])
            weaknesses.append(_issue(6, "HIGH", "WEAK_SYMBOL_BUCKET", "A symbol bucket has negative expectancy", f"{worst['key']} has {worst['trades']} trades averaging {worst['average_r']:+.4f}R.", "Keep the symbol visible for analysis, but investigate its setup behavior separately before relying on it."))

        weak_tfs = [r for r in by_timeframe if r["trades"] >= 5 and r["average_r"] is not None and r["average_r"] < 0]
        if weak_tfs:
            worst = min(weak_tfs, key=lambda r: r["average_r"])
            weaknesses.append(_issue(7, "HIGH", "WEAK_TIMEFRAME_BUCKET", "A timeframe bucket has negative expectancy", f"{worst['key']} has {worst['trades']} trades averaging {worst['average_r']:+.4f}R.", "Analyze that timeframe independently rather than compensating with stronger results from other timeframes."))

    # #15H-6: severity is the primary ordering rule. The original rule
    # priority is retained only as a deterministic business-order tie breaker
    # within the same severity. Public priorities are then normalized to 1..N.
    severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    weaknesses.sort(
        key=lambda x: (
            severity_rank.get(x["severity"], 99),
            x["priority"],
            x["code"],
        )
    )
    for idx, item in enumerate(weaknesses, start=1):
        item["priority"] = idx

    if not real:
        overall = "No production analytical evidence yet; diagnostics are limited to the missing-evidence warning."
    elif weaknesses:
        overall = f"{len(weaknesses)} prioritized weakness(es) identified from {len(real)} production analytical trade(s)."
    else:
        overall = f"No material weakness crossed the current diagnostic thresholds across {len(real)} production analytical trade(s)."

    return {
        "diagnostic_status": status,
        "real_market_trade_count": len(real),
        "isolated_test_trade_count": len(tests),
        "unknown_source_trade_count": len(unknown),
        "test_trades_excluded_from_diagnostics": len(tests),
        "metrics": s,
        "weakness_count": len(weaknesses),
        "weaknesses": weaknesses,
        "strengths": strengths,
        "by_symbol": by_symbol,
        "by_timeframe": by_timeframe,
        "summary": overall,
    }
